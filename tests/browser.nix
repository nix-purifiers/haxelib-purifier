{ pkgs }:
let
  build =
    src:
    pkgs.haxelib-purifier.buildHaxeProject {
      inherit src;
      javascriptTargets.site = {
        main = "BrowserMain";
        classPaths = [ "web" ];
        assets = {
          "index.html" = "web/index.html";
          "style.css" = "web/style.css";
        };
        webjar = {
          groupId = "org.webjars.haxe";
          artifactId = "answer";
          version = "1.0.0";
        };
      };
    };
  record = built: value: {
    inherit value;
    artifact = toString built.javascript.site;
    proof = toString built.javascript.site.proof;
    web = toString built.projections.site.web;
    maven = toString built.projections.site.maven;
  };
  reject =
    target:
    !(builtins.tryEval
      (pkgs.haxelib-purifier.buildHaxeProject {
        src = ./fixtures/browser42;
        javascriptTargets.site = target;
      }).packages.project.drvPath
    ).success;
in
assert (pkgs.haxelib-purifier.buildHaxeProject { src = ./fixtures/browser42; }).projections == { };
assert reject { main = "../Main"; };
assert reject {
  main = "BrowserMain";
  classPaths = [ "../web" ];
};
assert reject {
  main = "BrowserMain";
  libraries = [ "unlocked" ];
};
assert reject {
  main = "BrowserMain";
  assets."main.js" = "web/style.css";
};
pkgs.runCommand "haxe-browser-consumers"
  {
    nativeBuildInputs = [
      pkgs.python3
      pkgs.jdk
      pkgs.gradle
      pkgs.chromium
    ];
    spec = builtins.toJSON {
      versions = [
        (record (build ./fixtures/browser42) 42)
        (record (build ./fixtures/browser43) 43)
      ];
      chromium = "${pkgs.chromium}/bin/chromium";
    };
    passAsFile = [ "spec" ];
  }
  ''
    export HOME="$TMPDIR/home" GRADLE_USER_HOME="$TMPDIR/gradle-home"
    mkdir -p "$HOME"
    python3 ${./browser}/proof.py "$specPath" "$out"
  ''
