{ lib }:
{
  src,
  lockFile ? src + "/haxelib-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  inputs = data.inputs or { };
  safe =
    s: builtins.isString s && s != "." && s != ".." && builtins.match "[A-Za-z0-9_.-]+" s != null;
  relative =
    s: builtins.isString s && !(lib.hasPrefix "/" s) && !(builtins.elem ".." (lib.splitString "/" s));
  dir = builtins.readDir src;
  requested = builtins.filter (n: n == "haxelib.json" || lib.hasSuffix ".hxml" n) (
    builtins.attrNames dir
  );
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "haxelib"
    && requested != [ ]
    && (data.requested or null) == requested
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs inputs
    &&
      builtins.attrNames inputs
      == builtins.sort builtins.lessThan (lib.unique (requested ++ data.extraInputs))
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs inputs.${name}
      && builtins.isString (inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && (builtins.readDir (dirOf (src + "/${name}"))).${baseNameOf name} == "regular"
      && builtins.hashFile "sha256" (src + "/${name}") == (inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" inputs.${name}.content == inputs.${name}.sha256
    ) (builtins.attrNames inputs)
    && builtins.isAttrs (data.project or null)
    && safe (data.project.name or null)
    && safe (data.project.version or null)
    && relative (data.project.classPath or null)
    && builtins.isBool (data.project.package or null)
    && data.project.package == (dir ? "haxelib.json")
    && builtins.isList entries
    && builtins.isList nodes
    && builtins.all (
      e:
      builtins.isAttrs e
      && builtins.isString (e.path or null)
      && lib.hasPrefix "archives/" e.path
      && relative e.path
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://lib.haxe.org:443/files/3.0/" e.url
      && (e.mirrors or null) == [ ]
      && !(e ? git)
    ) entries
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && safe (n.version or null)
      && (n.folder or null) == lib.replaceStrings [ "." ] [ "," ] n.name
      && (n.versionDir or null) == lib.replaceStrings [ "." ] [ "," ] n.version
      && relative (n.classPath or null)
      && (n.entry or null) == "archives/${n.folder}-${n.versionDir}.zip"
      && builtins.any (
        e: e.path == n.entry && lib.hasSuffix "/${n.folder}-${n.versionDir}.zip" e.url
      ) entries
    ) nodes
    && builtins.length entries == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.length (lib.unique (map (n: "${n.name}:${n.version}") nodes)) == builtins.length nodes
    && builtins.isAttrs (data.currents or null)
    &&
      builtins.attrNames data.currents
      == builtins.sort builtins.lessThan (lib.unique (map (n: n.folder) nodes))
    && builtins.all (
      folder: builtins.any (n: n.folder == folder && n.version == data.currents.${folder}) nodes
    ) (builtins.attrNames data.currents)
    && builtins.isAttrs (data.toolVersions or null)
    && builtins.all (k: builtins.isString (data.toolVersions.${k} or null)) [
      "sdk"
      "haxe"
      "haxelib"
      "neko"
    ];
in
{
  purifier = "haxelib";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Haxelib lock is missing, stale, or unsupported; run haxelib-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
