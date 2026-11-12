# haxelib-purifier

Locked, Nix-resolved libraries for Haxe.

## Quickstart

Start in a project with `haxelib.json` or native `.hxml` build descriptions.

```sh
nix shell 'github:nix-purifiers/haxelib-purifier'
haxelib-purifier lock
haxelib install build.hxml
haxe build.hxml
```

The shell supplies `haxe` and `haxelib` wrappers. Each project gets a private
Haxelib repository under `.haxelib-purifier/`. Library sources come from readonly
Nix outputs; a package's own source uses Haxelib's native development-directory
integration. An existing `.haxelib/` and your global repository remain separate.

Without a companion lockfile, wrappers warn and run the ordinary native tool.
Stale or invalid locks fail. Commit `haxelib-purifier.lock.json`; refresh it after
changing dependency metadata:

```sh
haxelib-purifier lock --update
```

Source edits do not require relocking. Root `.hxml` files, their native includes
and `haxelib.json` are tracked automatically. Use `lock --input path` to track
other files that affect selection. `prefetch` prepares the immutable repository.
Wrappers can also be installed using your normal Nix configuration.

## Resolution

The pinned native Haxelib client selects versions and transitive dependencies.
The companion records its selected repository versions and current selections,
SDK identity and hashes of the exact downloaded ZIPs. Nix verifies those bytes;
Haxelib's native reader installs them and checks package names, versions and
class paths. Frozen native commands validate dependencies against that prepared
repository. They cannot resolve additional packages from the network.

This integration currently supports registry ZIPs from `lib.haxe.org`, Haxe
4.3 and Haxelib 4.1. Git, Mercurial and arbitrary package servers are outside
its current scope. Packages requiring additional native toolchains need those
supplied as Nix build inputs. SDK changes require relocking.

## Commands

```sh
haxelib-purifier exec -- haxe build.hxml
haxelib-purifier release
haxelib-purifier publish \
  --repo owner/project --tag v0.1.0
```

For packages with `haxelib.json`, `release` produces a reproducible native ZIP.
Its declared name, version and class path must match the lock. An ordinary
Haxelib user can install that ZIP. `publish` creates or updates a GitHub release
with the same bytes. Projects described only by HXML can build and run; native
package publication requires `haxelib.json`.

Use `--project` and `--lock-file` to select an external companion. Native commands
also accept `HAXELIB_PURIFIER_PROJECT` and `HAXELIB_PURIFIER_LOCK`. Environment
profiles retain both dependencies and the wrapper SDK as garbage collector roots.

## Building with Nix

An optional project Nix definition can call the overlay's
`haxelib-purifier.buildHaxeProject` through `callPackage`:

```nix
pkgs.haxelib-purifier.buildHaxeProject {
  src = ./.;
  buildCommand = "haxe build.hxml";
  checkCommand = "haxe tests.hxml";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packages.environment` contains the dependency repository;
`packages.project` builds the application. Override `buildCommand`,
`checkCommand`, `installCommand`, `doCheck` or `nativeBuildInputs` for the project.
The default build command is `haxe build.hxml`; the default check command is empty.

## JavaScript browser projections

Declare a browser entrypoint independently of the project's normal HXML target:

```nix
project = pkgs.haxelib-purifier.buildHaxeProject {
  src = ./.;
  javascriptTargets.site = {
    main = "BrowserMain";
    classPaths = [ "web" ];
    assets = { "index.html" = "web/index.html"; "style.css" = "web/style.css"; };
    webjar = { groupId = "org.webjars.haxe"; artifactId = "my-site"; version = "1.0.0"; };
  };
};
```

The native Haxe compiler builds the selected main class using the frozen
Haxelib repository. For a package project, the project's own `-lib` selection
includes its native class path and declared dependencies. Optional `libraries`
can select other captured libraries explicitly. New or version-overridden
libraries require relocking.

`javascript.site` and `packages.javascript-site` contain the browser bundle
and explicitly selected public assets. Esbuild uses its browser target and
rejects unresolved imports, including Node built-ins. Native compiler output,
typed XML, bundle input ownership/hashes and compiler versions remain in the
separate `.proof` output. Public assets and class paths must stay inside the
project source.

`projections.site.web` exposes a static document root and Java resource JAR.
Optional WebJar coordinates add `.maven` and `.ivy` projections; their
publication identities retain the producing build. Existing native Haxe
builds and source releases keep their normal interfaces.

The checks build two genuine browser revisions with locked `tink_json`,
execute them in Chromium from the native tree and HTTP resources, and resolve
their WebJars through ordinary offline Gradle. A Java HTTP server serves the
resolved JAR through an isolated ClassLoader, with exact origin/hash checks.
Missing scripts, compiled replacements, private-resource exposure, invalid
main classes, system-only targets, escaping assets and Node-only imports
have separate controls.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
