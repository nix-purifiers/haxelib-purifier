"""Install captured archives through Haxelib, then verify native identities."""

import json
import os
from pathlib import Path
import subprocess
import sys

manifest, sources, output, installer, inspector = map(Path, sys.argv[1:])
data = json.loads(manifest.read_text())
repository = output / "repository"
repository.mkdir(parents=True, exist_ok=True)
env = {
    **os.environ,
    "HAXELIB_PATH": str(repository) + "/",
    "HAXELIB_PURIFIER_REPOSITORY": str(repository),
    "HAXELIB_PURIFIER_FROZEN": "1",
}
for node in data["nodes"]:
    archive = sources / node["entry"]
    identity = json.loads(
        subprocess.check_output([inspector, "zip", archive], text=True)
    )
    assert identity == {k: node[k] for k in ("name", "version", "classPath")}, (
        "Native ZIP identity differs from lock"
    )
    subprocess.run(
        [installer, "install", archive, "--always", "--skip-dependencies"],
        env=env,
        check=True,
    )
    installed = repository / node["folder"] / node["versionDir"] / "haxelib.json"
    actual = json.loads(
        subprocess.check_output([inspector, "json", installed], text=True)
    )
    assert actual == identity, "Native installed metadata differs from archive"
for folder, version in data["currents"].items():
    (repository / folder / ".current").write_text(version)
