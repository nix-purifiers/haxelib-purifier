{
  symlinkJoin,
  nativeHaxelib,
  haxe,
  neko,
  git,
  curl,
  cacert,
  unzip,
  zip,
  coreutils,
  findutils,
}:
symlinkJoin {
  name = "haxelib-purifier-toolchain";
  paths = [
    nativeHaxelib
    haxe
    neko
    git
    curl
    cacert
    unzip
    zip
    coreutils
    findutils
  ];
}
