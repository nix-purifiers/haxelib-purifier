{
  lib,
  runCommand,
  python3,
  haxe,
  purifier,
  lua5_4,
}:
{
  producer,
  environment,
  targets,
}:
lib.mapAttrs (
  name: target:
  let
    lua = target.lua or lua5_4;
    dependencies = target.runtimeDependencies or [ ];
    runtime = lua.withPackages (_: dependencies);
    original = builtins.removeAttrs target [
      "lua"
      "runtimeDependencies"
    ];
    artifact =
      assert lib.assertMsg (builtins.all (
        dependency: dependency ? lua && purifier.inputIdentity dependency.lua == purifier.inputIdentity lua
      ) dependencies) "Lua runtime dependencies must use the original selected Lua interpreter";
      runCommand "haxe-lua-${name}"
        {
          outputs = [
            "out"
            "proof"
          ];
          nativeBuildInputs = [ python3 ];
          spec = builtins.toJSON {
            producer = toString producer;
            environment = toString environment;
            sdk = toString haxe;
            runtime = toString runtime;
            runtimeOutputs = map toString runtime.paths;
            abi = lua.luaversion;
            luaVersion = lua.version;
            target = original;
            checker = ./lua-load.lua;
          };
          passAsFile = [ "spec" ];
        }
        ''
          export HOME="$TMPDIR/home"
          mkdir -p "$HOME" "$out" "$proof"
          python3 ${./lua-products.py} "$specPath" "$out" "$proof"
        '';
  in
  artifact
  // {
    projections.lua = {
      producer = artifact;
      inherit runtime;
      module = target.module;
      abi = lua.luaversion;
      modulePath = "${artifact}/share/lua/${lua.luaversion}";
    };
  }
) targets
