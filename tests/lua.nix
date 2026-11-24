{ pkgs }:
let
  build =
    src:
    pkgs.haxelib-purifier.buildHaxeProject {
      src = pkgs.runCommand "haxe-lua-input-with-invalid-shadow-control" { } ''
        mkdir -p "$out/shadow/haxe/io"
        cp -r ${src}/. "$out/"
        cp ${pkgs.haxe}/lib/haxe/std/haxe/io/BytesBuffer.hx "$out/shadow/haxe/io/BytesBuffer.hx"
      '';
      lockFile = src + "/haxelib-purifier.lock.json";
      luaTargets.api = {
        types = [ "LuaApi" ];
        module = "example_api";
        runtimeDependencies = with pkgs.lua54Packages; [
          bit32
          luautf8
          lrexlib-pcre2
          luv
        ];
      };
    };
  first = (build ./fixtures/lua42).lua.api;
  second = (build ./fixtures/lua43).lua.api;
  consumer =
    artifact: answer:
    pkgs.runCommand "haxe-native-lua-consumer-${toString answer}" { } ''
      export LUA_PATH="${artifact.projections.lua.modulePath}/?.lua"
      export LUA_CPATH=""
      ${artifact.projections.lua.runtime}/bin/lua -e 'local m=require("example_api"); assert(m.example.Api.answer()==[[{"answer":${toString answer}}]]); assert(m.example.Api.codepoints()==2); assert(m.example.Api.matches("abc")); assert(not m.example.Api.matches("123")); print("native generated Lua${toString answer}/utf8/regex")' > "$out"
    '';
  a = consumer first 42;
  b = consumer second 43;
  badABI = pkgs.haxelib-purifier.buildHaxeProject {
    src = ./fixtures/lua42;
    luaTargets.api = {
      types = [ "LuaApi" ];
      module = "example_api";
      runtimeDependencies = [ pkgs.lua51Packages.bit32 ];
    };
  };
in
assert !(builtins.tryEval badABI.lua.api.drvPath).success;
pkgs.runCommand "haxe-native-lua-consumers"
  {
    nativeBuildInputs = [ pkgs.python3 ];
    controls = builtins.toJSON {
      request = builtins.fromJSON (builtins.unsafeDiscardStringContext first.spec);
      generator = ../pkgs/build-haxelib-project/lua-products.py;
      bareRuntime = toString pkgs.lua5_4;
    };
    # Preserve the complete original declaration contexts after parsing its JSON.
    nativeInputs = first.spec;
    passAsFile = [ "controls" ];
  }
  ''
    mkdir "$out"
    cp ${a} "$out/first.txt"
    cp ${b} "$out/second.txt"
    cp ${first.proof}/model.json "$out/first-model.json"
    cp ${second.proof}/model.json "$out/second-model.json"
    python3 ${./lua-negative.py} "$controlsPath" "$out/rejections.json"
  ''
