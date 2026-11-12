# SPDX-License-Identifier: MIT
"""Package native Haxe Python library output with a native wheel backend."""
import hashlib
import json
import keyword
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(spec, output, proof):
    producer = Path(spec['producer']).resolve(strict=True)
    root = (producer / 'source').resolve(strict=True)
    sdk = Path(spec['sdk']).resolve(strict=True)
    target = spec['target']
    module = target['module']
    if not module.isidentifier() or keyword.iskeyword(module):
        raise ValueError('Python module must be a non-keyword identifier')
    canonicalize_name(target['distribution'], validate=True)
    Version(target['version'])
    for requirement in target.get('requirements', []):
        Requirement(requirement)
    for name in target.get('classPaths', []):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_dir():
            raise ValueError('Python target class path escapes project source')
    work = Path('python-source').resolve()
    work.mkdir()
    typed = (proof / 'typed.xml').resolve()
    generated = work / (module + '.py')
    command = [str(producer / 'bin/haxe'), '-v']
    for path in target.get('classPaths', []):
        command += ['-cp', path]
    for library in target['libraries']:
        command += ['-lib', library]
    command += target['types'] + ['--python', str(generated), '--xml', str(typed)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True)
    (proof / 'compiler.stdout').write_text(result.stdout)
    (proof / 'compiler.stderr').write_text(result.stderr)
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
    metadata = {
        'build-system': {'requires': ['setuptools', 'wheel'], 'build-backend': 'setuptools.build_meta'},
        'project': {'name': target['distribution'], 'version': target['version'],
                    'dependencies': target.get('requirements', [])},
        'tool': {'setuptools': {'py-modules': [module]}},
    }
    # JSON strings are valid TOML strings; retain native backend validation.
    text = '[build-system]\nrequires = ["setuptools", "wheel"]\nbuild-backend = "setuptools.build_meta"\n[project]\n'
    for key, value in metadata['project'].items():
        text += key + ' = ' + json.dumps(value) + '\n'
    text += '[tool.setuptools]\npy-modules = ' + json.dumps([module]) + '\n'
    (work / 'pyproject.toml').write_text(text)
    subprocess.run([sys.executable, '-m', 'build', '--no-isolation', '--wheel', '--outdir', str(output.resolve()), str(work)], check=True)
    wheels = list(output.glob('*.whl'))
    if len(wheels) != 1:
        raise ValueError('native backend did not produce exactly one wheel')
    with zipfile.ZipFile(wheels[0]) as wheel:
        if wheel.read(module + '.py') != generated.read_bytes():
            raise ValueError('native wheel changed generated Python source')
    shutil.copy(generated, proof / (module + '.py'))
    shutil.copy(work / 'pyproject.toml', proof / 'pyproject.toml')
    actual_version = subprocess.check_output([str(producer / 'bin/haxe'), '--version'], text=True).strip()
    if actual_version != capture['toolVersions']['haxe']:
        raise ValueError('native Haxe compiler differs from captured SDK')
    model = {'kind': 'native-haxe-python-wheel', 'producer': str(producer), 'sdk': str(sdk),
             'compilerVersion': actual_version, 'environment': spec['environment'], 'command': command, 'target': target,
             'sources': sources, 'typedModelSha256': sha(typed), 'generatedSha256': sha(generated),
             'wheel': wheels[0].name, 'wheelSha256': sha(wheels[0])}
    (proof / 'model.json').write_text(json.dumps(model, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    generate(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]), Path(sys.argv[3]))
