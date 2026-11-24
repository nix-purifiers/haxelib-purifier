{ pkgs }:
let
  source = pkgs.runCommand "haxe-derived-source" { } ''
    mkdir "$out"
    cp -r ${../examples/minimal}/. "$out/"
  '';
  build = pkgs.haxelib-purifier.buildHaxeProject {
    src = source;
    lockFile = ../examples/minimal/haxelib-purifier.lock.json;
  };
in
pkgs.runCommand "haxe-derived-source-consumer" { nativeBuildInputs = [ pkgs.python3 ]; } ''
  test -d ${build.packages.project}/source
  test -f ${build.release}/*.zip
  cp -r ${source} stale
  chmod -R u+w stale
  printf '\n' >> stale/haxelib.json
  for phase in prepare release; do
    args=()
    if [ "$phase" = prepare ]; then
      args+=("$TMPDIR/environment" "$TMPDIR/repository")
    fi
    if python3 ${../haxelib_purifier}/$phase.py \
      ${../examples/minimal/haxelib-purifier.lock.json} \
      "''${args[@]}" \
      "$PWD/stale" "$TMPDIR" /deliberately-unavailable-inspector > rejected 2>&1; then
      echo "stale derived metadata was accepted by $phase" >&2
      exit 1
    fi
    grep -F 'Haxe metadata changed' rejected
  done
  touch "$out"
''
