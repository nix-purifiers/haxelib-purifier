"""Capture native downloads and expose frozen repository checks."""

from pathlib import Path

p = Path("src/haxelib/client/Main.hx")
s = p.read_text()


def replace(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


replace(
    "\tfunction retry<R>(func:Void -> R, numTries:Int = 3) {",
    '\tfunction retry<R>(func:Void -> R, numTries:Int = 3) {\n        if (Sys.getEnv("HAXELIB_PURIFIER_FROZEN") != null) throw "Frozen Haxelib resolution: update the purifier lock";',
)
replace(
    "\tfunction getRepository():String {",
    """\tfunction getRepository():String {
        var purifier = Sys.getEnv("HAXELIB_PURIFIER_REPOSITORY");
        if (purifier != null) return Path.addTrailingSlash(purifier);
""",
)
replace(
    "\t\tdoInstallFile(rep, filepath, setcurrent);",
    """        var capture = Sys.getEnv("HAXELIB_PURIFIER_CAPTURE");
        if (capture != null) {
            if (!fileUrl.startsWith("https://lib.haxe.org:443/")) throw "Unsupported source registry";
            var saved = Path.join([capture, filename]);
            File.copy(filepath, saved);
            var records = File.append(Path.join([capture, "downloads.jsonl"]));
            records.writeString(haxe.Json.stringify({name:project,version:version,url:fileUrl,path:saved})+"\\n");
            records.close();
        }
\t\tdoInstallFile(rep, filepath, setcurrent);""",
)
replace(
    "\t\tif( settings.skipDependencies ) return;",
    """\t\tif( settings.skipDependencies ) return;
        if (Sys.getEnv("HAXELIB_PURIFIER_FROZEN") != null) {
            for (d in dependencies) {
                switch d.type {
                    case Haxelib: checkRec(rep, d.name, d.version == "" ? null : d.version, new List(), true);
                    default: throw "Frozen Haxelib sessions require registry dependencies";
                }
            }
            return;
        }""",
)
replace(
    '\t\tprint("Loading info about the required libraries");',
    """        if (Sys.getEnv("HAXELIB_PURIFIER_FROZEN") != null) {
            for (l in libsToInstall) {
                if (l.type != "haxelib") throw "Frozen Haxelib sessions require registry dependencies";
                checkRec(rep, l.name, l.version, new List(), true);
            }
            return;
        }
\t\tprint("Loading info about the required libraries");""",
)
replace(
    "\t\t\tvar hxml = normalizeHxml(sys.io.File.getContent(path));",
    """            var capture = Sys.getEnv("HAXELIB_PURIFIER_CAPTURE");
            if (capture != null) {
                var tracked = File.append(Path.join([capture, "inputs.jsonl"]));
                tracked.writeString(haxe.Json.stringify(FileSystem.fullPath(path))+"\\n");
                tracked.close();
            }
\t\t\tvar hxml = normalizeHxml(sys.io.File.getContent(path));""",
)
replace(
    "\tfunction download(fileUrl:String, outPath:String, maxRedirect = 20):Void {",
    '\tfunction download(fileUrl:String, outPath:String, maxRedirect = 20):Void {\n        if (Sys.getEnv("HAXELIB_PURIFIER_FROZEN") != null) throw "Frozen Haxelib sessions cannot download packages";',
)
p.write_text(s)
