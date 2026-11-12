{
  project,
  companion,
  target ? "environment",
  sdk ? null,
  profile ? false,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativeHaxelib = pkgs.callPackage ./native.nix { };
  toolchain = pkgs.callPackage ./toolchain.nix { inherit nativeHaxelib; };
  sdkVersion = import ./sdk-version.nix { inherit nixpkgsSrc; };
  args = {
    src = /. + project;
    lockFile = /. + companion;
  };
  lock = import ../../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } args;
  output =
    if target == "environment" then
      pkgs.callPackage ./environment.nix {
        inherit
          purifier
          nativeHaxelib
          toolchain
          sdkVersion
          ;
      } { inherit lock; }
    else if target == "release" then
      (pkgs.callPackage ./default.nix {
        inherit
          purifier
          nativeHaxelib
          toolchain
          sdkVersion
          ;
      } args).release
    else
      throw "haxelib-purifier: unknown target";
in
if profile then
  pkgs.writeText "haxelib-${target}-profile.json" (
    builtins.toJSON {
      inherit output;
      sdk = builtins.storePath sdk;
    }
  )
else
  output
