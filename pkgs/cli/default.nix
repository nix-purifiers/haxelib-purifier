{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  toolchain,
  nativeHaxelib,
  haxe,
  neko,
  cacert,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "haxelib-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/haxelib-purifier"
    cp -r haxelib_purifier pkgs lib-overlays "$out/lib/haxelib-purifier/"
    install -m755 bin/haxelib-purifier "$out/bin/haxelib-purifier"
    substituteInPlace "$out/lib/haxelib-purifier/pkgs/build-haxelib-project/realize.nix" \
      --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/haxelib-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set HAXELIB_PURIFIER_NATIVE_HAXE ${haxe}/bin/haxe \
      --set HAXELIB_PURIFIER_NATIVE_HAXELIB ${nativeHaxelib}/bin/haxelib \
      --set HAXELIB_PURIFIER_NATIVE_INSPECT ${nativeHaxelib}/bin/haxelib-purifier-inspect \
      --set HAXELIB_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set HAXELIB_PURIFIER_HAXE_VERSION ${haxe.version} \
      --set HAXELIB_PURIFIER_HAXELIB_VERSION ${nativeHaxelib.version} \
      --set HAXELIB_PURIFIER_NEKO_VERSION ${neko.version} \
      --set HAXELIB_PURIFIER_SDK "$out" --set HAXELIB_PURIFIER_TOOLCHAIN ${toolchain}
    for tool in haxe haxelib; do
      makeWrapper "$out/bin/haxelib-purifier" "$out/bin/$tool" --add-flags "--native --tool=$tool --"
    done
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native Haxe workflow with locked Nix-resolved libraries";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "haxelib-purifier";
  };
}
