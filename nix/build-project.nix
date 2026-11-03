{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  nativeHaxelib,
  toolchain,
  haxe,
  neko,
  sdkVersion,
  makeWrapper,
}:
{
  src,
  lockFile ? src + "/haxelib-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  doCheck ? true,
  buildCommand ? "haxe build.hxml",
  checkCommand ? "",
  installCommand ? "",
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".haxelib"
      ".haxelib-purifier"
      "result"
      "__pycache__"
    ]),
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  environment = import ./environment.nix {
    inherit
      lib
      runCommand
      fetchgit
      python3
      writeText
      purifier
      nativeHaxelib
      toolchain
      haxe
      neko
      sdkVersion
      ;
  } { inherit lock fetchers nativeBuildInputs; };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  manifest = writeText "haxe-project-capture.json" (builtins.toJSON lock.data);
  project =
    runCommand "purified-haxe-project"
      {
        nativeBuildInputs = [
          toolchain
          python3
          makeWrapper
        ]
        ++ nativeBuildInputs;
      }
      ''
        export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home"
        export HAXELIB_PATH="$out/repository/" HAXELIB_PURIFIER_REPOSITORY="$out/repository" HAXELIB_PURIFIER_FROZEN=1
        mkdir -p "$HOME" "$out/source" "$out/bin"
        cp -pr ${source}/. "$out/source/"
        chmod -R u+w "$out/source"
        python3 ${../haxelib_purifier/prepare.py} ${environment}/capture.json ${environment} "$out/repository" "$out/source" \
          ${nativeHaxelib}/bin/haxelib ${nativeHaxelib}/bin/haxelib-purifier-inspect
        cd "$out/source"
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ${installCommand}
        for tool in haxe haxelib; do
          makeWrapper ${toolchain}/bin/$tool "$out/bin/$tool" \
            --prefix PATH : ${toolchain}/bin \
            --set HAXELIB_PATH "$out/repository/" --set HAXELIB_PURIFIER_REPOSITORY "$out/repository" --set HAXELIB_PURIFIER_FROZEN 1
        done
      '';
  release =
    assert lib.assertMsg lock.data.project.package "Native Haxelib publication requires haxelib.json";
    runCommand "haxelib-source-release"
      {
        nativeBuildInputs = [
          toolchain
          python3
        ];
      }
      ''
        mkdir -p "$out" source
        cp -pr ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/haxelib-purifier.lock.json
        python3 ${../haxelib_purifier/release.py} ${manifest} "$PWD/source" "$out" ${nativeHaxelib}/bin/haxelib-purifier-inspect
      '';
in
assert lock.problems == [ ];
assert lib.assertMsg (
  lock.data.toolVersions == {
    sdk = sdkVersion;
    haxe = haxe.version;
    haxelib = nativeHaxelib.version;
    neko = neko.version;
  }
) "Haxe SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project environment;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
