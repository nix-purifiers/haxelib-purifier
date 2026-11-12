import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import zipfile

spec = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2]);out.mkdir()
results = []
for index, case in enumerate(spec['versions']):
    model = json.loads((Path(case['proof'])/'model.json').read_text())
    for row in model['sources']:
        assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256']
    assert any(row['owner']=='project source' and row['path'].endswith('/PythonApi.hx') for row in model['sources'])
    assert any(row['owner'].startswith('tink_json-') for row in model['sources'])
    assert any(row['owner']=='native Haxe SDK' for row in model['sources'])
    wheel = Path(case['wheel'])/model['wheel']
    assert hashlib.sha256(wheel.read_bytes()).hexdigest()==model['wheelSha256']
    raw = (Path(case['proof'])/'haxe_answer.py').read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read('haxe_answer.py')==raw
        assert all('private.txt' not in name and not name.endswith('.hx') for name in archive.namelist())
    destination = Path(f'installed-{index}').resolve()
    subprocess.run([sys.executable,'-m','pip','--isolated','install','--no-index','--no-compile','--find-links',case['repository'],'--target',str(destination),'haxe-answer'],check=True)
    program = '''import hashlib,importlib.metadata,json,sys
sys.path.insert(0,sys.argv[1])
import haxe_answer,foreign_answer
print(json.dumps({'answer':haxe_answer.PythonApi.answer(),'combined':haxe_answer.PythonApi.combined(),'sourceSha256':hashlib.sha256(open(haxe_answer.__file__,'rb').read()).hexdigest(),'foreignSha256':hashlib.sha256(open(foreign_answer.__file__,'rb').read()).hexdigest(),'version':importlib.metadata.version('haxe-answer'),'requirements':importlib.metadata.requires('haxe-answer'),'foreignVersion':importlib.metadata.version('foreign-answer')}))
'''
    actual=json.loads(subprocess.check_output([sys.executable,'-I','-c',program,str(destination)],text=True))
    assert actual['answer']==case['value'] and actual['combined']==case['value']+7+index, actual
    assert actual['sourceSha256']==model['generatedSha256']
    foreign=json.loads((Path(case['foreignProof'])/'model.json').read_text())
    assert actual['foreignSha256']==foreign['generatedSha256']
    assert '+nix' in actual['version'] and '+nix' in actual['foreignVersion']
    assert actual['foreignVersion'] in str(actual['requirements'])
    foreign_model=json.loads((Path(case['foreignProof'])/'model.json').read_text())
    # The supplied dependency projection must be retained byte-for-byte.
    supplied=[path for path in Path(case['repository']).glob('foreign_answer-*.whl')]
    assert len(supplied)==1
    assert supplied[0].read_bytes()==(Path(case['foreignRepository'])/supplied[0].name).read_bytes()
    with zipfile.ZipFile(supplied[0]) as archive:
        assert hashlib.sha256(archive.read('foreign_answer.py')).hexdigest()==foreign_model['generatedSha256']
    results.append({'case':case,'model':model,'actual':actual,'catalog':json.loads(Path(case['catalog']).read_text())})
assert results[0]['actual']['version']!=results[1]['actual']['version']
# A real offline installer must reject a missing selected runtime provider.
repository = Path(spec['versions'][0]['repository'])
missing = Path('missing-runtime');missing.mkdir()
for wheel in repository.glob('haxe_answer-*.whl'):
    shutil.copy(wheel, missing/wheel.name)
run = subprocess.run([sys.executable,'-m','pip','--isolated','install','--no-index','--no-compile','--find-links',str(missing),'--target',str(Path('unexpected-missing').resolve()),'haxe-answer'],text=True,capture_output=True)
assert run.returncode and 'foreign-answer' in run.stderr and 'No matching distribution found' in run.stderr
(out/'missing-runtime.stdout').write_text(run.stdout);(out/'missing-runtime.stderr').write_text(run.stderr)
# Use the same adapter and genuine native compiler for failure controls.
from importlib.util import spec_from_file_location, module_from_spec
loader=spec_from_file_location('generator',spec['generator']);generator=module_from_spec(loader);loader.loader.exec_module(generator)
case=spec['versions'][0];model=results[0]['model']
def attempt(name, target, producer=case['producer']):
    folder=Path(name).resolve();folder.mkdir();destination=folder/'wheel';proof=folder/'proof';destination.mkdir();proof.mkdir()
    prior=Path.cwd()
    try:
        os.chdir(folder)
        generator.generate({'producer':producer,'environment':model['environment'],'sdk':model['sdk'],'target':target},destination,proof)
    finally:os.chdir(prior)
# Compiler failure occurs before consulting the captured dependency manifest.
bad=dict(model['target']);bad['types']=['PurifierMissingSelectedType']
try:attempt('missing-type',bad)
except subprocess.CalledProcessError as error:
    assert 'Type not found' in error.stderr
    (out/'missing-type.stderr').write_text(error.stderr)
else:raise AssertionError('native compiler accepted absent selected type')
# Resolve a real symlink before any compiler invocation.
copy=Path('escaped-producer').resolve();shutil.copytree(case['producer'],copy,symlinks=True)
for path in copy.rglob('*'):
    if path.is_dir() and not path.is_symlink():path.chmod(0o755)
external=Path('outside-source').resolve();external.mkdir();(copy/'source/escaped').symlink_to(external,target_is_directory=True)
bad=dict(model['target']);bad['classPaths']=['escaped']
try:attempt('escaped-classpath',bad,str(copy))
except ValueError as error:assert 'class path escapes' in str(error)
else:raise AssertionError('accepted escaping native class path')
(out/'verification.json').write_text(json.dumps({'consumers':results,'missingRuntimeRejected':True,'missingTypeRejected':True,'escapingClassPathRejected':True},indent=2)+'\n')
