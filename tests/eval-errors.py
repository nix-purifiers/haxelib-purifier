"""Check lock validation with import-from-derivation disabled."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    source = Path(temporary) / "project"
    shutil.copytree(HERE / "examples/minimal", source)
    companion = source / "haxelib-purifier.lock.json"
    original = json.loads(companion.read_text())

    def problems():
        expression = f"""let
          f = builtins.getFlake {json.dumps(str(HERE))};
          lock = f.lib.haxelib-purifier.readLock {{src=/. + {json.dumps(str(source))};}};
          in {{inherit(lock) problems outputs;fetches=map(e: e.path) lock.entries;}}"""
        return json.loads(
            subprocess.run(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )

    valid = problems()
    assert valid["problems"] == [] and valid["outputs"]["packages"] == [
        "default",
        "environment",
        "project",
    ]
    companion.unlink()
    assert problems()["problems"]
    for mutate in [
        lambda d: d.update(purifier="other"),
        lambda d: d["nodes"][0].update(version="changed"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d.update(currents={}),
        lambda d: d["toolVersions"].update(sdk=None),
    ]:
        data = json.loads(json.dumps(original))
        mutate(data)
        companion.write_text(json.dumps(data))
        assert problems()["problems"]
    companion.write_text(json.dumps(original))
    (source / "haxelib.json").write_text("; stale\n")
    assert problems()["problems"]
print("Haxelib lock validation passed without IFD")

# A fresh, unbuilt producer must remain opaque, including its source subpath.
with tempfile.TemporaryDirectory(prefix="haxelib-derived-") as temporary:
    name = Path(temporary).name
    expression = f"""let
      f = builtins.getFlake {json.dumps(str(HERE))};
      system = builtins.currentSystem;
      pkgs = import f.inputs.nixpkgs {{ inherit system; overlays = [f.overlays.default]; }};
      source = pkgs.runCommand "{name}" {{}} "mkdir -p $out/source; cp -r {HERE / 'examples/minimal'}/. $out/source/";
      build = pkgs.haxelib-purifier.buildHaxeProject {{
        src = "${{source}}/source";
        lockFile = {HERE / 'examples/minimal/haxelib-purifier.lock.json'};
      }};
      in {{ source = source.outPath; project = build.packages.project.drvPath; release = build.release.drvPath; }}"""
    result = json.loads(subprocess.run(["nix", "eval", "--impure", "--json", "--option", "allow-import-from-derivation", "false", "--expr", expression], check=True, capture_output=True, text=True).stdout)
    assert not Path(result["source"]).exists()
    assert result["project"].endswith(".drv") and result["release"].endswith(".drv")
print("Fresh derived source and subpath evaluated without realization or IFD")
