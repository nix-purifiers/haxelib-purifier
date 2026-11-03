"""Project native repository configuration beside readonly library sources."""

import json
from pathlib import Path
import subprocess
import sys

manifest, environment, repository, source, installer, inspector = map(
    Path, sys.argv[1:]
)
data = json.loads(manifest.read_text())
repository.mkdir(parents=True, exist_ok=True)
for node in data["nodes"]:
    folder = repository / node["folder"]
    folder.mkdir(exist_ok=True)
    version = folder / node["versionDir"]
    target = environment / "repository" / node["folder"] / node["versionDir"]
    if version.is_symlink() and version.resolve() != target.resolve():
        version.unlink()
    if not version.exists():
        version.symlink_to(target, target_is_directory=True)
    elif not version.is_symlink():
        raise ValueError(
            "Private repository has an unexpected mutable dependency: " + str(version)
        )
for folder, version in data["currents"].items():
    (repository / folder / ".current").write_text(version)
if data["project"]["package"]:
    identity = json.loads(
        subprocess.check_output([inspector, "json", source / "haxelib.json"], text=True)
    )
    if identity != {k: data["project"][k] for k in ("name", "version", "classPath")}:
        raise ValueError("Native project identity differs from the lock")
    if data["project"]["name"].replace(".", ",") in data["currents"]:
        raise ValueError("Project and dependency use the same package identity")
    dev = repository / data["project"]["name"].replace(".", ",") / ".dev"
    if not dev.is_file() or Path(dev.read_text().strip()).resolve() != source.resolve():
        subprocess.run([installer, "dev", data["project"]["name"], source], check=True)
