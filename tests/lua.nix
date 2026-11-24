{ pkgs }:
let
  build = pkgs.haxelib-purifier.buildHaxeProject {
    src = ./fixtures/lua42;
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
  module = build.lua.api;
  projection = module.projections.lua;
in
pkgs.runCommand "haxe-native-lua-consumer" { } ''
  export LUA_PATH="${projection.modulePath}/?.lua"
  export LUA_CPATH=""
  ${projection.runtime}/bin/lua -e 'local m=require("example_api"); assert(m.example.Api.answer()==[[{"answer":42}]]); assert(m.example.Api.codepoints()==2); assert(m.example.Api.matches("abc")); assert(not m.example.Api.matches("123")); print("native generated Lua42/utf8/regex")' > "$out"
''
