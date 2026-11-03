"""Retain exact native ZIP downloads and the repository's native selections."""

import base64
import hashlib
import json
from pathlib import Path
import re
import tempfile

from .common import STATE, clean_env, inputs, load, native, run, versions


def capture(root, companion, update=False, extra=(), name=None):
    if companion.exists() and not update:
        previous = load(root, companion)
        if extra and sorted(set(extra)) != previous["extraInputs"]:
            raise ValueError("Changed --input requires lock --update")
        if name and name != previous["project"]["name"]:
            raise ValueError("Changed --name requires lock --update")
        return
    old = json.loads(companion.read_text()) if companion.exists() else {}
    extra = sorted(set(extra or old.get("extraInputs", [])))
    requested = [
        p
        for p in ["haxelib.json", *sorted(p.name for p in root.glob("*.hxml"))]
        if (root / p).is_file()
    ]
    requested = sorted(requested)
    if not requested:
        raise ValueError("Provide haxelib.json or a native .hxml build description")
    state = root / STATE
    state.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capture-", dir=state) as temporary:
        work = Path(temporary).resolve()
        env = clean_env(work)
        repository = work / "repository"
        repository.mkdir()
        retained = work / "downloads"
        retained.mkdir()
        env.update(
            HAXELIB_PATH=str(repository) + "/",
            HAXELIB_PURIFIER_REPOSITORY=str(repository),
            HAXELIB_PURIFIER_CAPTURE=str(retained),
        )
        for filename in requested:
            run([native("haxelib"), "install", filename, "--always"], cwd=root, env=env)
        discovered = []
        if (retained / "inputs.jsonl").exists():
            for line in (retained / "inputs.jsonl").read_text().splitlines():
                path = Path(json.loads(line)).resolve()
                if not path.is_relative_to(root):
                    raise ValueError(
                        "Included HXML must be inside the project: " + str(path)
                    )
                relative = str(path.relative_to(root))
                if relative not in requested:
                    discovered.append(relative)
        extra = sorted(set(extra + discovered))
        recorded = inputs(root, extra)
        nodes = {}
        records = (
            (retained / "downloads.jsonl").read_text().splitlines()
            if (retained / "downloads.jsonl").exists()
            else []
        )
        for line in records:
            record = json.loads(line)
            info = json.loads(
                run(
                    [native("inspect"), "zip", record["path"]],
                    capture_output=True,
                    text=True,
                ).stdout
            )
            if (info["name"], info["version"]) != (record["name"], record["version"]):
                raise ValueError(
                    "Downloaded native package identity differs from selected registry identity"
                )
            if not all(
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", record[k])
                for k in ("name", "version")
            ):
                raise ValueError("Unsupported package identity")
            folder = record["name"].replace(".", ",")
            version_dir = record["version"].replace(".", ",")
            payload = Path(record["path"]).read_bytes()
            digest = (
                "sha256-" + base64.b64encode(hashlib.sha256(payload).digest()).decode()
            )
            entry = "archives/" + Path(record["path"]).name
            nodes[(record["name"], record["version"])] = {
                "name": record["name"],
                "version": record["version"],
                "folder": folder,
                "versionDir": version_dir,
                "classPath": info["classPath"],
                "entry": entry,
                "fetch": {
                    "path": entry,
                    "url": record["url"],
                    "hash": digest,
                    "mirrors": [],
                },
            }
        currents = {}
        known = {n["folder"] for n in nodes.values()}
        for folder in repository.iterdir():
            if not folder.is_dir():
                continue
            if (
                folder.name not in known
                or (folder / ".dev").exists()
                or (folder / "git").exists()
                or (folder / "hg").exists()
            ):
                raise ValueError("Only registry ZIP dependencies are supported")
            currents[folder.name] = (folder / ".current").read_text().strip()
        if (root / "haxelib.json").is_file():
            project = json.loads(
                run(
                    [native("inspect"), "json", root / "haxelib.json"],
                    capture_output=True,
                    text=True,
                ).stdout
            )
            project["package"] = True
        else:
            project = {
                "name": name or "application",
                "version": "0.0.0",
                "classPath": "",
                "package": False,
            }
        if name and name != project["name"]:
            raise ValueError("--name differs from the native package name")
        data = {
            "version": 1,
            "purifier": "haxelib",
            "toolVersions": versions(),
            "inputs": recorded,
            "extraInputs": extra,
            "requested": requested,
            "project": project,
            "currents": currents,
            "nodes": [
                {k: v for k, v in n.items() if k != "fetch"}
                for _, n in sorted(nodes.items())
            ],
            "entries": [n["fetch"] for _, n in sorted(nodes.items())],
        }
    companion.parent.mkdir(parents=True, exist_ok=True)
    pending = companion.with_name(companion.name + ".tmp")
    pending.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    pending.replace(companion)
