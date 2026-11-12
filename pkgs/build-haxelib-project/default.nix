{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  nativeHaxelib,
  toolchain,
  haxe,
  neko,
  sdkVersion,
  makeWrapper,
  esbuild,
}:
{
  src,
  lockFile ? src + "/haxelib-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  javascriptTargets ? { },
  pythonTargets ? { },
  doCheck ? true,
  buildCommand ? "haxe build.hxml",
  checkCommand ? "",
  installCommand ? "",
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".haxelib"
      ".haxelib-purifier"
      "result"
      "__pycache__"
    ]),
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; }
  );
  environment = import ./environment.nix {
    inherit
      lib
      runCommand
      fetchgit
      python3
      writeText
      purifier
      nativeHaxelib
      toolchain
      haxe
      neko
      sdkVersion
      ;
  } { inherit lock fetchers nativeBuildInputs; };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  manifest = writeText "haxe-project-capture.json" (builtins.toJSON lock.data);
  relative =
    path:
    builtins.isString path
    && path != ""
    && !(lib.hasPrefix "/" path)
    && !(lib.hasInfix "\\" path)
    && builtins.all (part: part != "" && part != "." && part != "..") (lib.splitString "/" path);
  coordinate =
    value: builtins.isString value && builtins.match "[A-Za-z0-9_][A-Za-z0-9_.-]*" value != null;
  effective = target: {
    inherit (target) main;
    classPaths = target.classPaths or [ ];
    libraries = target.libraries or (lib.optional lock.data.project.package lock.data.project.name);
    assets = target.assets or { };
  };
  valid =
    target:
    builtins.isAttrs target
    && builtins.all (
      key:
      builtins.elem key [
        "main"
        "classPaths"
        "libraries"
        "assets"
        "webjar"
      ]
    ) (builtins.attrNames target)
    && builtins.isString (target.main or null)
    && builtins.match "[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*" target.main != null
    && builtins.isList (target.classPaths or [ ])
    && builtins.all (path: path == "." || relative path) (target.classPaths or [ ])
    && builtins.isList (target.libraries or [ ])
    && builtins.all (
      name:
      builtins.isString name
      && (name == lock.data.project.name || builtins.any (node: node.name == name) lock.data.nodes)
    ) (target.libraries or [ ])
    && builtins.isAttrs (target.assets or { })
    && builtins.all (path: relative path && path != "main.js" && relative target.assets.${path}) (
      builtins.attrNames (target.assets or { })
    )
    && (
      (target.webjar or null) == null
      || (
        builtins.isAttrs target.webjar
        && builtins.all (
          key:
          builtins.elem key [
            "groupId"
            "artifactId"
            "version"
          ]
        ) (builtins.attrNames target.webjar)
        && coordinate (target.webjar.artifactId or null)
        && coordinate (target.webjar.version or null)
        && coordinate (target.webjar.groupId or "org.webjars.npm")
      )
    );
  validTargets =
    builtins.isAttrs javascriptTargets
    && builtins.all (name: coordinate name && valid javascriptTargets.${name}) (
      builtins.attrNames javascriptTargets
    );
  pythonEffective =
    target:
    target
    // {
      libraries = target.libraries or (lib.optional lock.data.project.package lock.data.project.name);
    };
  validPython =
    target:
    builtins.isAttrs target
    && builtins.all (
      key:
      builtins.elem key [
        "types"
        "classPaths"
        "libraries"
        "module"
        "distribution"
        "version"
        "requirements"
        "dependencies"
      ]
    ) (builtins.attrNames target)
    && builtins.isList (target.types or null)
    && target.types != [ ]
    && builtins.length target.types == builtins.length (lib.unique target.types)
    && builtins.all (
      name:
      builtins.isString name
      && builtins.match "[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*" name != null
    ) target.types
    && builtins.isList (target.classPaths or [ ])
    && builtins.all (path: path == "." || relative path) (target.classPaths or [ ])
    && builtins.isList (target.libraries or [ ])
    && builtins.all (
      name:
      builtins.isString name
      && (name == lock.data.project.name || builtins.any (node: node.name == name) lock.data.nodes)
    ) (target.libraries or [ ])
    && builtins.isString (target.module or null)
    && builtins.match "[A-Za-z_][A-Za-z0-9_]*" target.module != null
    && builtins.isString (target.distribution or null)
    && target.distribution != ""
    && builtins.isString (target.version or null)
    && target.version != ""
    && builtins.isList (target.requirements or [ ])
    && builtins.all builtins.isString (target.requirements or [ ])
    && builtins.isList (target.dependencies or [ ]);
  validPythonTargets =
    builtins.isAttrs pythonTargets
    && builtins.all (
      name:
      coordinate name && validPython pythonTargets.${name} && !(builtins.hasAttr name javascriptTargets)
    ) (builtins.attrNames pythonTargets);
  specs = lib.mapAttrs (
    name: target: writeText "haxe-javascript-${name}.json" (builtins.toJSON (effective target))
  ) javascriptTargets;
  javascriptBuild = lib.concatMapStringsSep "\n" (
    name:
    let
      target = effective javascriptTargets.${name};
    in
    ''
      mkdir -p "$out/javascript-native/${name}" "$out/javascript/${name}" "$out/javascript-proof/${name}"
      python3 ${./javascript-output.py} validate "$PWD" ${specs.${name}}
      ${haxe}/bin/haxe --version > "$out/javascript-proof/${name}/haxe-version.txt"
      ${haxe}/bin/haxe ${
        lib.escapeShellArgs (
          (lib.concatMap (path: [
            "-cp"
            path
          ]) target.classPaths)
          ++ (lib.concatMap (name: [
            "-lib"
            name
          ]) target.libraries)
          ++ [
            "-main"
            target.main
          ]
        )
      } \
        --js "$out/javascript-native/${name}/main.js" --xml "$out/javascript-proof/${name}/typed.xml"
      ${esbuild}/bin/esbuild "$out/javascript-native/${name}/main.js" --bundle --platform=browser --format=iife \
        --outfile="$out/javascript/${name}/main.js" --metafile="$out/javascript-proof/${name}/bundle.json"
      ${esbuild}/bin/esbuild --version > "$out/javascript-proof/${name}/bundler-version.txt"
    ''
  ) (builtins.attrNames javascriptTargets);
  rawProject =
    runCommand "purified-haxe-project"
      {
        nativeBuildInputs = [
          toolchain
          python3
          makeWrapper
        ]
        ++ nativeBuildInputs
        ++ lib.optionals (javascriptTargets != { }) [ esbuild ];
      }
      ''
        export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home"
        export HAXELIB_PATH="$out/repository/" HAXELIB_PURIFIER_REPOSITORY="$out/repository" HAXELIB_PURIFIER_FROZEN=1
        mkdir -p "$HOME" "$out/source" "$out/bin"
        cp -pr ${source}/. "$out/source/"
        chmod -R u+w "$out/source"
        python3 ${../../haxelib_purifier/prepare.py} ${environment}/capture.json ${environment} "$out/repository" "$out/source" \
          ${nativeHaxelib}/bin/haxelib ${nativeHaxelib}/bin/haxelib-purifier-inspect
        cd "$out/source"
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ${javascriptBuild}
        ${installCommand}
        for tool in haxe haxelib; do
          makeWrapper ${toolchain}/bin/$tool "$out/bin/$tool" \
            --prefix PATH : ${toolchain}/bin \
            --set HAXELIB_PATH "$out/repository/" --set HAXELIB_PURIFIER_REPOSITORY "$out/repository" --set HAXELIB_PURIFIER_FROZEN 1
        done
      '';
  javascript = lib.mapAttrs (
    name: target:
    let
      artifact =
        runCommand "haxe-javascript-${name}"
          {
            outputs = [
              "out"
              "proof"
            ];
            nativeBuildInputs = [ python3 ];
          }
          ''
                mkdir -p "$out" "$proof"
                cp ${rawProject}/javascript/${name}/main.js "$out/main.js"
                cp ${rawProject}/javascript-proof/${name}/* "$proof/"
            python3 ${./javascript-output.py} select ${rawProject} ${specs.${name}} "$out" "$proof" ${lib.escapeShellArg name} ${environment}
          '';
    in
    artifact
    // {
      projections =
        (purifier.resourceProjections {
          producer = artifact;
          roots."." = ".";
          inherit runCommand python3;
        })
        // lib.optionalAttrs ((target.webjar or null) != null) (
          purifier.webjarProjections (
            target.webjar
            // {
              producer = artifact;
              assets = artifact;
              inherit runCommand python3;
            }
          )
        );
    }
  ) javascriptTargets;
  python =
    import ./python-products.nix
      {
        inherit
          lib
          runCommand
          python3
          purifier
          haxe
          ;
      }
      {
        producer = rawProject;
        inherit environment;
        targets = lib.mapAttrs (_: pythonEffective) pythonTargets;
      };
  projections = lib.mapAttrs (_: artifact: artifact.projections) (javascript // python);
  project = rawProject // {
    inherit projections;
  };
  release =
    assert lib.assertMsg lock.data.project.package "Native Haxelib publication requires haxelib.json";
    runCommand "haxelib-source-release"
      {
        nativeBuildInputs = [
          toolchain
          python3
        ];
      }
      ''
        mkdir -p "$out" source
        cp -pr ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/haxelib-purifier.lock.json
        python3 ${../../haxelib_purifier/release.py} ${manifest} "$PWD/source" "$out" ${nativeHaxelib}/bin/haxelib-purifier-inspect
      '';
in
assert lock.problems == [ ];
assert lib.assertMsg validPythonTargets
  "haxelib-purifier: pythonTargets requires selected native types, relative class paths, captured libraries, Python module/distribution/version, explicit requirements and typed dependencies; target names must be distinct";
assert lib.assertMsg validTargets
  "haxelib-purifier: javascriptTargets requires a native Haxe main class, captured libraries, relative class paths/public assets and optional WebJar coordinates";
assert lib.assertMsg (
  lock.data.toolVersions == {
    sdk = sdkVersion;
    haxe = haxe.version;
    haxelib = nativeHaxelib.version;
    neko = neko.version;
  }
) "Haxe SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project environment;
  }
  // lib.mapAttrs' (name: artifact: lib.nameValuePair "javascript-${name}" artifact) javascript
  // lib.mapAttrs' (name: artifact: lib.nameValuePair "python-${name}" artifact) python;
  inherit javascript python projections;
  tests = project;
  inherit release;
  fetches = lock.entries;
}
