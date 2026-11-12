{ nixpkgsSrc }:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    inspect = builtins.hashFile "sha256" ../../haxelib_purifier/PurifierInspect.hx;
    patch = builtins.hashFile "sha256" ../../haxelib_purifier/patch-sdk.py;
    native = builtins.hashFile "sha256" ./native.nix;
  }
)
