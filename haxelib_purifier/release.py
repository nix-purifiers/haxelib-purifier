"""Create a deterministic native ZIP and verify it with Haxelib's reader."""

import json
from pathlib import Path
import subprocess
import sys
import zipfile

manifest, source, output, inspector = map(Path, sys.argv[1:])
data = json.loads(manifest.read_text())
expected = {k: data["project"][k] for k in ("name", "version", "classPath")}
actual = json.loads(
    subprocess.check_output([inspector, "json", source / "haxelib.json"], text=True)
)
if actual != expected:
    raise ValueError("Native project identity differs from lock")
archive = output / (expected["name"] + "-" + expected["version"] + ".zip")
with zipfile.ZipFile(
    archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
) as target:
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(
                "Native package source must use regular files: " + str(path)
            )
        if path.is_file():
            entry = zipfile.ZipInfo(
                str(path.relative_to(source)), (1980, 1, 1, 0, 0, 0)
            )
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(entry, path.read_bytes())
verified = json.loads(subprocess.check_output([inspector, "zip", archive], text=True))
if verified != expected:
    raise ValueError("Native ZIP identity differs from lock")
