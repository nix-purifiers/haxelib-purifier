{
  stdenvNoCC,
  haxe,
  neko,
  python3,
  makeWrapper,
  lib,
}:
stdenvNoCC.mkDerivation {
  pname = "haxelib-purifier-sdk";
  version = "4.1.1";
  src = haxe.src;
  nativeBuildInputs = [
    haxe
    python3
    makeWrapper
  ];
  dontConfigure = true;
  buildPhase = ''
    cd extra/haxelib_src
    python ${../haxelib_purifier/patch-sdk.py}
    haxe client.hxml
    cp ${../haxelib_purifier/PurifierInspect.hx} PurifierInspect.hx
    haxe -cp src -cp hx3compat/std -cp . -main PurifierInspect -neko inspect.n
  '';
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/haxelib-purifier"
    cp run.n inspect.n "$out/lib/haxelib-purifier/"
    makeWrapper ${neko}/bin/neko "$out/bin/haxelib-purifier-inspect" \
      --add-flags "$out/lib/haxelib-purifier/inspect.n"
    makeWrapper ${neko}/bin/neko "$out/bin/haxelib" \
      --add-flags "$out/lib/haxelib-purifier/run.n"
    test "$("$out/bin/haxelib" version)" = 4.1.1
  '';
  meta = {
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
