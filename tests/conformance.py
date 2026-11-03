"""Verify the native Haxe workflow and ordinary Haxelib ZIP consumers."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def output(name):
    return Path(
        run(
            ["nix", "build", ".#" + name, "--no-link", "--print-out-paths"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    )


cli, sdk = output("default"), output("sdk")
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    root = directory / "renamed-project"
    shutil.copytree(
        HERE / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".haxelib-purifier", ".haxelib"),
    )
    old_repository = root / ".haxelib"
    old_repository.mkdir()
    (old_repository / "preserve.txt").write_text("existing repository\n")
    helper = cli / "bin/haxelib-purifier"
    run([helper, "--project", root, "prefetch"])
    env = {
        **os.environ,
        "PATH": str(cli / "bin") + ":" + os.environ["PATH"],
        "HAXELIB_PATH": "/poisoned/repository",
        "HAXE_STD_PATH": "/poisoned/standard",
        "NEKOPATH": "/poisoned/neko",
    }
    for filename in ("haxelib.json", "build.hxml"):
        run([cli / "bin/haxelib", "install", filename, "--always"], cwd=root, env=env)
    result = run(
        [cli / "bin/haxe", "build.hxml"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == '{"answer":42}'
    source = root / "src/PurifierExample.hx"
    query = (
        str(source) + "@" + str(source.read_text().index("stringify") + 3) + "@position"
    )
    definition = run(
        [cli / "bin/haxe", "-cp", "src", "-lib", "tink_json", "--display", query],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (
        "/nix/store/" in definition.stdout + definition.stderr
        and "/src/tink/Json.hx:" in definition.stdout + definition.stderr
    )
    companion = root / "haxelib-purifier.lock.json"
    original_lock = companion.read_bytes()
    run([helper, "--project", root, "lock"])
    assert companion.read_bytes() == original_lock
    original_source = source.read_text()
    source.write_text(original_source.replace("answer:42", "answer:43"))
    negative = subprocess.run(
        [cli / "bin/haxe", "build.hxml"], cwd=root, env=env, capture_output=True
    )
    assert negative.returncode and b"43" in negative.stderr
    source.write_text(original_source)
    run([cli / "bin/haxe", "build.hxml"], cwd=root, env=env)
    assert (old_repository / "preserve.txt").read_text() == "existing repository\n"
    profile = root / ".haxelib-purifier/environment.json"
    prepared = json.loads(profile.read_text())
    references = run(
        ["nix-store", "--query", "--references", profile],
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert prepared["output"] in references and prepared["sdk"] in references
    release = Path(
        run(
            [helper, "--project", root, "release"], capture_output=True, text=True
        ).stdout.strip()
    )
    archive = release / "purifier-example-0.1.0.zip"
    consumer_repository = directory / "consumer-repository"
    consumer_repository.mkdir()
    for item in (Path(prepared["output"]) / "repository").iterdir():
        (consumer_repository / item.name).symlink_to(item, target_is_directory=True)
    native_env = {
        **os.environ,
        "PATH": str(sdk / "bin") + ":" + os.environ["PATH"],
        "HAXELIB_PATH": str(consumer_repository) + "/",
        "HAXELIB_PURIFIER_REPOSITORY": str(consumer_repository),
        "HAXELIB_PURIFIER_FROZEN": "1",
    }
    run(
        [sdk / "bin/haxelib", "install", archive, "--always", "--skip-dependencies"],
        env=native_env,
    )
    consumer = directory / "Consumer.hx"
    consumer.write_text(
        "class Consumer { static function main() { final v=PurifierExample.answer(); if(v != '{\"answer\":42}') throw v; Sys.println(v); }}\n"
    )
    run(
        [
            sdk / "bin/haxe",
            "-cp",
            directory,
            "-lib",
            "purifier-example",
            "--run",
            "Consumer",
        ],
        cwd=directory,
        env=native_env,
    )
    fake = directory / "gh"
    log = directory / "gh.jsonl"
    uploaded = directory / "uploaded.zip"
    fake.write_text(
        '#!/usr/bin/env python3\nimport json,os,sys,shutil\nwith open(os.environ["GH_TEST_LOG"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\nif sys.argv[1:3]==["release","view"]: sys.exit(1 if os.environ.get("GH_TEST_CREATE") else 0)\nfor arg in sys.argv[3:]:\n if arg.endswith(".zip"): shutil.copyfile(arg,os.environ["GH_TEST_BYTES"])\n'
    )
    fake.chmod(0o755)
    for create in (True, False):
        publish_env = {
            **os.environ,
            "HAXELIB_PURIFIER_GH": str(fake),
            "GH_TEST_LOG": str(log),
            "GH_TEST_BYTES": str(uploaded),
        }
        if create:
            publish_env["GH_TEST_CREATE"] = "1"
        run(
            [
                helper,
                "--project",
                root,
                "publish",
                "--repo",
                "example/project",
                "--tag",
                "v0.1.0",
            ],
            env=publish_env,
        )
        assert uploaded.read_bytes() == archive.read_bytes()
    assert [json.loads(line)[1] for line in log.read_text().splitlines()] == [
        "view",
        "create",
        "view",
        "upload",
    ]
    data = json.loads(original_lock)
    data["project"]["version"] = "9.9.9"
    companion.write_text(json.dumps(data))
    mismatch = subprocess.run(
        [helper, "--project", root, "release"], capture_output=True
    )
    assert mismatch.returncode and b"differs from lock" in mismatch.stderr
    companion.write_bytes(original_lock)
    external = directory / "external.json"
    companion.rename(external)
    external_env = {
        **env,
        "HAXELIB_PURIFIER_PROJECT": str(root),
        "HAXELIB_PURIFIER_LOCK": str(external),
    }
    run([cli / "bin/haxe", "build.hxml"], cwd=root, env=external_env)
    external.rename(companion)
    (root / "build.hxml").write_text(
        (root / "build.hxml").read_text() + "\n# metadata changed\n"
    )
    stale = subprocess.run(
        [cli / "bin/haxe", "build.hxml"], cwd=root, env=env, capture_output=True
    )
    assert stale.returncode and b"metadata changed" in stale.stderr
    plain = directory / "plain"
    plain.mkdir()
    (plain / "Exit.hx").write_text(
        'class Exit { static function main() { Sys.print(Sys.stdin().readLine()); Sys.stderr().writeString("native-stderr\\n"); Sys.exit(7); }}'
    )
    fallback = subprocess.run(
        [cli / "bin/haxe", "--run", "Exit"],
        cwd=plain,
        input=b"ordinary-input\n",
        capture_output=True,
    )
    assert fallback.returncode == 7 and fallback.stdout == b"ordinary-input"
    assert (
        b"ordinary impure resolution" in fallback.stderr
        and b"native-stderr" in fallback.stderr
    )
print("Haxe native conformance passed")
