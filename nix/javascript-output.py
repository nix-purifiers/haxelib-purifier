"""Select actual Haxe JavaScript output with compiler and bundler provenance."""
import hashlib,json,pathlib,shutil,sys
Path=pathlib.Path
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def resolve(root,name,directory=False):
    path=(root/name).resolve(strict=True)
    if not path.is_relative_to(root) or not (path.is_dir() if directory else path.is_file()):raise ValueError('JavaScript input escapes Haxe project: '+name)
    return path
if sys.argv[1]=='validate':
    root=Path(sys.argv[2]).resolve();spec=json.loads(Path(sys.argv[3]).read_text())
    for name in spec['classPaths']:resolve(root,name,True)
    for name in spec['assets'].values():resolve(root,name)
    sys.exit(0)
_,producer,spec_file,out,proof,name,environment=sys.argv[1:]
producer,out,proof=map(Path,[producer,out,proof]);spec=json.loads(Path(spec_file).read_text())
native=producer/'javascript-native'/name/'main.js'
bundled=producer/'javascript'/name/'main.js'
assert sha(bundled)==sha(out/'main.js')
bundle=json.loads((proof/'bundle.json').read_text())
capture=json.loads((Path(environment)/'capture.json').read_text())
owners=[((Path(environment)/'repository'/node['folder']/node['versionDir']).resolve(),node['name']+'-'+node['version']) for node in capture['nodes']]
inputs=[]
for input_name in bundle['inputs']:
    path=Path(input_name)
    if not path.is_absolute():path=producer/'source'/path
    path=path.resolve(strict=True)
    if path==native.resolve():owner='native Haxe compiler'
    elif path.is_relative_to((producer/'source').resolve()):owner='project source'
    else:
        matching=[label for root,label in owners if path.is_relative_to(root)]
        if len(matching)!=1:raise ValueError('bundled JavaScript lacks a captured source owner: '+str(path))
        owner=matching[0]
    inputs.append({'path':str(path),'sha256':sha(path),'owner':owner})
assert any(record['path']==str(native.resolve()) for record in inputs)
assert all(not row.get('imports') for row in bundle['outputs'].values()),bundle
files={'main.js':{'sha256':sha(bundled),'source':str(bundled),'nativeCompilerOutput':str(native),'nativeCompilerSha256':sha(native)}}
root=(producer/'source').resolve()
for destination,source in spec['assets'].items():
    original=resolve(root,source);target=out/destination
    if target.exists():raise ValueError('public asset collides with native Haxe JavaScript')
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
    files[destination]={'sha256':sha(original),'source':str(original)}
model={'kind':'native-haxe-javascript-browser','producer':str(producer),'target':spec,'compilerVersion':(proof/'haxe-version.txt').read_text().strip(),'bundlerVersion':(proof/'bundler-version.txt').read_text().strip(),'typedModelSha256':sha(proof/'typed.xml'),'bundleInputs':inputs,'files':files}
assert model['compilerVersion']==capture['toolVersions']['haxe'],'actual Haxe compiler differs from captured SDK'
model['sdk']=capture['toolVersions'];model['environment']=environment
(proof/'model.json').write_text(json.dumps(model,sort_keys=True,indent=2)+'\n')
