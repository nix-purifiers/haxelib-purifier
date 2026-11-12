{ pkgs }:
let
  build =
    src:
    let
      built = pkgs.haxelib-purifier.buildHaxeProject {
        inherit src;
        pythonTargets.foreign = {
          types = [ "ForeignApi" ];
          module = "foreign_answer";
          distribution = "foreign-answer";
          version = "1.0.0";
        };
        pythonTargets.library = {
          types = [ "PythonApi" ];
          module = "haxe_answer";
          distribution = "haxe-answer";
          version = "1.0.0";
          requirements = [ "foreign-answer == 1.0.0" ];
          dependencies = [ built.python.foreign ];
        };
      };
      raw = pkgs.haxelib-purifier.buildHaxeProject { inherit src; };
    in
    assert raw.packages.project.drvPath == built.packages.project.drvPath;
    built;
  reject =
    target:
    !(builtins.tryEval
      (pkgs.haxelib-purifier.buildHaxeProject {
        src = ./fixtures/python42;
        pythonTargets.library = target;
      }).packages.project.drvPath
    ).success;
  valid = {
    types = [ "PythonApi" ];
    module = "haxe_answer";
    distribution = "haxe-answer";
    version = "1.0.0";
  };
  record =
    value:
    let
      built = build (./fixtures + "/python${toString value}");
    in
    {
      inherit value;
      producer = toString built.packages.project;
      wheel = toString built.python.library;
      proof = toString built.python.library.proof;
      repository = toString built.projections.library.python;
      catalog = built.projections.library.python.catalog;
      foreign = toString built.python.foreign;
      foreignRepository = toString built.projections.foreign.python;
      foreignProof = toString built.python.foreign.proof;
    };
in
assert (pkgs.haxelib-purifier.buildHaxeProject { src = ./fixtures/python42; }).projections == { };
assert reject (valid // { types = [ "../Api" ]; });
assert reject (
  valid
  // {
    types = [
      "PythonApi"
      "PythonApi"
    ];
  }
);
assert reject (valid // { classPaths = [ "../src" ]; });
assert reject (valid // { libraries = [ "unlocked" ]; });
assert reject (valid // { module = "bad.module"; });
pkgs.runCommand "haxe-python-native-consumers"
  {
    nativeBuildInputs = [
      (pkgs.python3.withPackages (p: [
        p.pip
        p.packaging
        p.build
        p.setuptools
        p.wheel
      ]))
    ];
    spec = builtins.toJSON {
      versions = [
        (record 42)
        (record 43)
      ];
      generator = ../pkgs/build-haxelib-project/python-products.py;
    };
    passAsFile = [ "spec" ];
  }
  ''
    export HOME="$TMPDIR/home" PYTHONDONTWRITEBYTECODE=1
    mkdir -p "$HOME"
    python ${./python/consume.py} "$specPath" "$out"
  ''
