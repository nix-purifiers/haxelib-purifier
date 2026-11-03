"""Exercise native HXML discovery, external companions and empty graphs."""

import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.run(
            ["nix", "build", ".#default", "--no-link", "--print-out-paths"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    / "bin/haxelib-purifier"
)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "project"
    root.mkdir()
    (root / "config").mkdir()
    (root / "build.hxml").write_text("config/included.hxml\n")
    included = root / "config/included.hxml"
    included.write_text("# no dependencies\n")
    companion = Path(temporary) / "external.json"

    def call(*args):
        return subprocess.run(
            [cli, "--project", root, "--lock-file", companion, *args],
            check=True,
            capture_output=True,
            text=True,
        )

    call("lock")
    empty = json.loads(companion.read_text())
    assert empty["nodes"] == empty["entries"] == []
    assert "config/included.hxml" in empty["inputs"]
    assert empty["project"]["package"] is False
    call("prefetch")
    assert subprocess.run(
        [cli, "--project", root, "--lock-file", companion, "release"],
        capture_output=True,
    ).returncode
    included.write_text("-lib tink_json\n")
    assert subprocess.run(
        [cli, "--project", root, "--lock-file", companion, "prefetch"],
        capture_output=True,
    ).returncode
    call("lock", "--update")
    updated = json.loads(companion.read_text())
    assert {n["name"] for n in updated["nodes"]} == {
        "tink_json",
        "tink_typecrawler",
        "tink_macro",
        "tink_core",
    }
    assert updated["extraInputs"] == ["config/included.hxml"]
    call("prefetch")
    call("lock")
print("Native Haxelib capture/update and empty graph passed")
