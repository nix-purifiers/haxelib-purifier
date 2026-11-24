# SPDX-License-Identifier: MIT
"""Exercise actual native compiler and Lua loader rejection paths."""
import json
from pathlib import Path
import subprocess
import sys

spec = json.loads(Path(sys.argv[1]).read_text())
results = []
for index, (name, diagnostic) in enumerate([
    ('missing-dependency', 'native Lua module load failed'),
    ('module-shadow', 'generated Lua module shadows a selected runtime dependency'),
    ('unexposed', 'native Haxe Lua library requires exposed exports'),
    ('export-collision', 'native Lua selected export paths collide'),
    ('sdk-shadow', 'Lua target shadows a native Haxe SDK type'),
]):
    root = Path.cwd() / str(index)
    root.mkdir()
    request = json.loads(json.dumps(spec['request']))
    if name == 'missing-dependency':
        request['runtime'] = spec['bareRuntime']
    elif name == 'module-shadow':
        request['target']['module'] = 'rex_pcre2'
    elif name == 'unexposed':
        request['target']['types'] = ['PurifierExample']
    elif name == 'export-collision':
        request['target']['types'] = ['LuaApi', 'DuplicateLuaApi']
    else:
        request['target'].update(types=['haxe.io.BytesBuffer'], classPaths=['shadow'])
    (root / 'request.json').write_text(json.dumps(request))
    (root / 'out').mkdir()
    (root / 'proof').mkdir()
    run = subprocess.run([sys.executable, spec['generator'], str(root / 'request.json'),
                          str(root / 'out'), str(root / 'proof')], cwd=root,
                         capture_output=True, text=True)
    assert run.returncode and diagnostic in run.stderr, name + ': ' + run.stdout + run.stderr
    record = {'name': name, 'diagnostic': diagnostic, 'exitCode': run.returncode}
    if name == 'sdk-shadow':
        record['nativeOrigins'] = json.loads((root / 'proof/sdk-shadow.json').read_text())
    results.append(record)
Path(sys.argv[2]).write_text(json.dumps(results, indent=2) + '\n')
