#!/usr/bin/env python3
"""Actual compiler/bundler/source-boundary rejections for Haxe browser output."""
from pathlib import Path
import json,os,shutil,subprocess,tempfile
repo=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='haxe-browser-negative-') as temporary:
    src=Path(temporary)/'source';shutil.copytree(repo/'tests/fixtures/browser42',src)
    (src/'web/outside.css').symlink_to('/etc/passwd')
    (src/'web/NodeMain.hx').write_text('class NodeMain {static function main(){js.Syntax.code("require(\'node:fs\')");}}\n')
    cases=[
      ('missing-main',dict(main='NoSuchMain',classPaths=['web']),'NoSuchMain'),
      ('system-only-main',dict(main='Main',classPaths=['tests']),'system platform'),
      ('escaping-asset',dict(main='BrowserMain',classPaths=['web'],assets={'outside.css':'web/outside.css'}),'JavaScript input escapes Haxe project'),
      ('node-only-import',dict(main='NodeMain',classPaths=['web']),'node:fs'),
    ]
    rows=[]
    for name,target,error in cases:
      expression='let f=builtins.getFlake '+json.dumps(str(repo))+';p=import f.inputs.nixpkgs {system=builtins.currentSystem;overlays=[f.overlays.default];};in (p.haxelib-purifier.buildHaxeProject {src=/. + '+json.dumps(str(src))+';javascriptTargets.site=builtins.fromJSON '+json.dumps(json.dumps(target))+';}).javascript.site'
      result=subprocess.run(['nix','build','--impure','--no-link','-L','--expr',expression],capture_output=True,text=True)
      print(result.stderr);assert result.returncode and error in result.stderr,(name,result)
      rows.append(dict(case=name,rejected=True))
    if os.environ.get('HAXE_BROWSER_NEGATIVE_EVIDENCE'):Path(os.environ['HAXE_BROWSER_NEGATIVE_EVIDENCE']).write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows))
