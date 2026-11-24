# SPDX-License-Identifier: MIT
"""Preserve native Haxe Lua exports and verify native runtime module ownership."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(spec, output, proof):
    producer = Path(spec['producer']).resolve(strict=True)
    root = (producer / 'source').resolve(strict=True)
    sdk = Path(spec['sdk']).resolve(strict=True)
    target = spec['target']
    module = target['module']
    for name in target.get('classPaths', []):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_dir():
            raise ValueError('Lua target class path escapes project source')
    work = Path('lua-source').resolve()
    work.mkdir()
    typed = (proof / 'typed.xml').resolve()
    generated = work / (module.replace('.', '/') + '.lua')
    generated.parent.mkdir(parents=True, exist_ok=True)
    command = [str(producer / 'bin/haxe'), '-v']
    for path in target.get('classPaths', []):
        command += ['-cp', path]
    for library in target['libraries']:
        command += ['-lib', library]
    command += target['types'] + ['--lua', str(generated), '--xml', str(typed), '-D', 'lua-ver=' + spec['abi']]
    if target.get('vanilla', False):
        command += ['-D', 'lua-vanilla']
    compiler_command = list(command)
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    (proof / 'compiler.stdout').write_text(result.stdout)
    (proof / 'compiler.stderr').write_text(result.stderr)
    if result.returncode:
        raise ValueError('native Haxe Lua compile failed: ' + result.stderr)
    capture = json.loads((Path(spec['environment']) / 'capture.json').read_text())
    owners = [(root, 'project source', None), (sdk, 'native Haxe SDK', None)]
    for node in capture['nodes']:
        relative = Path(node['folder']) / node['versionDir']
        owners.append(((producer / 'repository' / relative).resolve(strict=True),
                       node['name'] + '-' + node['version'],
                       (Path(spec['environment']) / 'repository' / relative).resolve(strict=True)))
    paths = set()
    for line in result.stdout.splitlines():
        if line.startswith('Parsed '):
            paths.add((root / line[len('Parsed '):]).resolve(strict=True))
    typed_model = ET.parse(typed)
    declared_types = {node.get('path') for node in typed_model.iter() if node.tag in ('class', 'enum', 'abstract', 'typedef')}
    if not set(target['types']) <= declared_types:
        raise ValueError('native typed model omitted a selected type')
    for node in typed_model.iter():
        if node.get('path') and node.get('file'):
            actual = (root / node.get('file')).resolve(strict=True)
            module_file = Path(*node.get('path').split('.')).with_suffix('.hx')
            for standard in [sdk / 'lib/haxe/std/lua/_std', sdk / 'lib/haxe/std']:
                original = standard / module_file
                if original.is_file() and not actual.is_relative_to(sdk):
                    (proof / 'sdk-shadow.json').write_text(json.dumps({
                        'type': node.get('path'), 'actual': str(actual),
                        'original': str(original), 'originalSha256': sha(original)
                    }, indent=2) + '\n')
                    raise ValueError('Lua target shadows a native Haxe SDK type')
    for node in typed_model.iter():
        if node.get('file'):
            paths.add((root / node.get('file')).resolve(strict=True))
    sources = []
    for path in sorted(paths):
        matches = [(base, owner, captured) for base, owner, captured in owners if path.is_relative_to(base)]
        if len(matches) != 1:
            raise ValueError('native compiler source lacks a unique captured/SDK owner: ' + str(path))
        base, owner, captured = matches[0]
        digest = sha(path)
        if captured is not None and digest != sha(captured / path.relative_to(base)):
            raise ValueError('compiler library source differs from captured dependency: ' + str(path))
        sources.append({'path': str(path), 'owner': owner, 'sha256': digest})
    if not sources or not any(row['owner'] == 'project source' for row in sources):
        raise ValueError('no project source in native compiler input evidence')
    exports = []
    for selected in target['types']:
        node = next(node for node in typed_model.iter() if node.get('path') == selected and node.tag in ('class', 'enum', 'abstract', 'typedef'))
        expose = node.find("./meta/m[@n=':expose']")
        if expose is None:
            raise ValueError('native Haxe Lua library requires exposed exports: ' + selected)
        expressions = expose.findall('e')
        export = json.loads(expressions[0].text) if expressions else selected
        if not isinstance(export, str) or not export or any(not part for part in export.split('.')):
            raise ValueError('native Lua expose metadata has an unsupported export path')
        exports.append(export)
    if len(exports) != len(set(exports)):
        raise ValueError('native Lua selected export paths collide')
    export_file = proof / 'exports.txt'
    export_file.write_text('\n'.join(exports) + '\n')
    installed = output / 'share/lua' / spec['abi'] / (module.replace('.', '/') + '.lua')
    installed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated, installed)
    env = dict(os.environ, LUA_PATH='', LUA_CPATH='')
    lua_version = subprocess.run([spec['runtime'] + '/bin/lua', '-v'], capture_output=True, text=True, check=True)
    lua_version = (lua_version.stdout + lua_version.stderr).strip()
    if not re.match(r'Lua ' + re.escape(spec['luaVersion']) + r'(?:\s|$)', lua_version):
        raise ValueError('native Lua interpreter differs from its original selected Nix input')
    trace = proof / 'native-load.tsv'
    checker = Path(spec['checker'])
    command = [spec['runtime'] + '/bin/lua', str(checker), module, str(output / 'share/lua' / spec['abi']), str(trace), spec['abi'], str(export_file)]
    load = subprocess.run(command, capture_output=True, text=True, env=env)
    (proof / 'native-load.stdout').write_text(load.stdout)
    (proof / 'native-load.stderr').write_text(load.stderr)
    if load.returncode:
        raise ValueError('native Lua module load failed: ' + load.stderr)
    native_owners = [(output.resolve(), 'generated module')]
    native_owners += [(Path(path).resolve(strict=True), path) for path in spec['runtimeOutputs']]
    native_sources = []
    for line in trace.read_text().splitlines():
        name, path = line.split('\t')
        path = Path(path).resolve(strict=True)
        matches = [(base, owner) for base, owner in native_owners if path.is_relative_to(base)]
        if len(matches) != 1:
            raise ValueError('native Lua module lacks a unique selected producer: ' + str(path))
        native_sources.append({'module': name, 'path': str(path), 'owner': matches[0][1], 'sha256': sha(path)})
    if not any(row['module'] == module and row['owner'] == 'generated module' for row in native_sources):
        raise ValueError('native Lua did not load the installed generated module')
    if generated.read_bytes() != installed.read_bytes():
        raise ValueError('installed Lua module changed native compiler output')
    actual_version = subprocess.check_output([str(producer / 'bin/haxe'), '--version'], text=True).strip()
    if actual_version != capture['toolVersions']['haxe']:
        raise ValueError('native Haxe compiler differs from captured SDK')
    model = {'kind': 'native-haxe-lua-module', 'producer': str(producer), 'sdk': str(sdk),
             'compilerVersion': actual_version, 'compilerCommand': compiler_command, 'nativeLoadCommand': command, 'runtime': spec['runtime'], 'abi': spec['abi'], 'luaVersion': lua_version,
             'target': target, 'exports': exports, 'sources': sources, 'nativeModules': native_sources,
             'typedModelSha256': sha(typed), 'generatedSha256': sha(generated), 'installed': str(installed)}
    (proof / 'model.json').write_text(json.dumps(model, indent=2) + '\n')


if __name__ == '__main__':
    generate(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]), Path(sys.argv[3]))
