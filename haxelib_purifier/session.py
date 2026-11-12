"""Activate a private native repository backed by immutable dependencies."""

import hashlib
import json
import os
from pathlib import Path
import sys

from .common import HERE, STATE, clean_env, load, native, run


def realize(root, companion, target="environment"):
    state = root / STATE
    state.mkdir(exist_ok=True)
    profile = state / (target + ".json")
    run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            HERE / "pkgs/build-haxelib-project/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "target",
            target,
            "--arg",
            "profile",
            "true",
            "--argstr",
            "sdk",
            os.environ["HAXELIB_PURIFIER_SDK"],
            "--out-link",
            profile,
        ],
        stdout=sys.stderr,
    )
    return Path(json.loads(profile.read_text())["output"])


def execute(root, companion, args, tool=None):
    command = [native(tool), *args] if tool else args
    if not companion.exists():
        if os.environ.get("HAXELIB_PURIFIER_LOCK"):
            raise ValueError("Selected lockfile does not exist")
        print(
            "warning: no haxelib-purifier lockfile; using ordinary impure resolution",
            file=sys.stderr,
        )
        os.execvpe(str(command[0]), list(map(str, command)), os.environ.copy())
    data = load(root, companion)
    environment = realize(root, companion)
    signature = hashlib.sha256(companion.read_bytes()).hexdigest()
    state = root / STATE / "session" / signature
    env = clean_env(state)
    repository = state / "repository"
    env.update(
        HAXELIB_PATH=str(repository) + "/",
        HAXELIB_PURIFIER_REPOSITORY=str(repository),
        HAXELIB_PURIFIER_FROZEN="1",
        HAXELIB_PURIFIER_PROJECT=str(root),
        HAXELIB_PURIFIER_LOCK=str(companion),
    )
    env["PATH"] = os.environ["HAXELIB_PURIFIER_SDK"] + "/bin:" + env["PATH"]
    run(
        [
            sys.executable,
            HERE / "haxelib_purifier/prepare.py",
            environment / "capture.json",
            environment,
            repository,
            root,
            native("haxelib"),
            native("inspect"),
        ],
        env=env,
        stdout=sys.stderr,
    )
    if tool == "haxelib":
        if args[:1] in (
            [name]
            for name in (
                "update",
                "remove",
                "set",
                "git",
                "hg",
                "dev",
                "setup",
                "newrepo",
                "deleterepo",
                "selfupdate",
            )
        ):
            raise ValueError(
                "This changes dependency selection; edit metadata and run haxelib-purifier lock --update"
            )
        if args[:1] == ["install"]:
            positional = [a for a in args[1:] if not a.startswith("-")]
            if not positional:
                raise ValueError(
                    "Use haxelib install with a locked .hxml file or haxelib.json"
                )
            if positional == ["all"]:
                pass
            elif len(positional) != 1 or (Path.cwd() / positional[0]).resolve() not in [
                (root / p).resolve() for p in data["requested"]
            ]:
                raise ValueError(
                    "Locked sessions install only recorded project metadata"
                )
    os.execvpe(str(command[0]), list(map(str, command)), env)
