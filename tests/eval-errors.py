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
