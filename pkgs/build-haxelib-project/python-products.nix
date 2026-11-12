# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  python3,
  purifier,
  haxe,
}:
{
  producer,
  environment,
  targets,
}:
let
  backend = python3.withPackages (p: [
    p.build
    p.setuptools
    p.wheel
    p.packaging
  ]);
  build =
    name: target:
    let
      wheel =
        runCommand "haxe-python-${name}"
          {
            outputs = [
              "out"
              "proof"
            ];
            nativeBuildInputs = [ backend ];
            spec = builtins.toJSON {
              producer = toString producer;
              environment = toString environment;
              sdk = toString haxe;
              inherit target;
            };
            passAsFile = [ "spec" ];
          }
          ''
            export HOME="$TMPDIR/home" SOURCE_DATE_EPOCH=315532800 PYTHONHASHSEED=0
            mkdir -p "$HOME" "$out" "$proof"
            python ${./python-products.py} "$specPath" "$out" "$proof"
          '';
    in
    wheel
    // {
      projections = purifier.pythonProjections {
        repository = wheel;
        producer = wheel;
        dependencies = targets.${name}.dependencies or [ ];
        inherit runCommand python3;
      };
    };
in
lib.mapAttrs (name: target: build name (builtins.removeAttrs target [ "dependencies" ])) targets
