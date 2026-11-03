{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  toolchain,
  nativeHaxelib,
  haxe,
  neko,
  sdkVersion,
}:
{
  lock,
  fetchers ? { },
  nativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "locked-haxelib-archives";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  manifest = writeText "haxelib-capture.json" (builtins.toJSON checked.data);
in
assert checked.problems == [ ];
assert lib.assertMsg (
  checked.data.toolVersions == {
    sdk = sdkVersion;
    haxe = haxe.version;
    haxelib = nativeHaxelib.version;
    neko = neko.version;
  }
) "Haxe SDK changed; update the lock";
runCommand "purified-haxelib-environment"
  {
    nativeBuildInputs = [
      toolchain
      python3
    ]
    ++ nativeBuildInputs;
  }
  ''
    export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home"
    mkdir -p "$HOME" "$out"
    python3 ${../haxelib_purifier/stage.py} ${manifest} ${sources} "$out" \
      ${nativeHaxelib}/bin/haxelib ${nativeHaxelib}/bin/haxelib-purifier-inspect
    cp ${manifest} "$out/capture.json"
    ln -s ${sources} "$out/sources"
  ''
