import haxelib.Data;
import haxe.zip.Reader;
import sys.io.File;
class PurifierInspect {
 static function main() {
  final args=Sys.args();
  final info=if(args[0]=="json") Data.readData(File.getContent(args[1]),false)
   else { final input=File.read(args[1]); final zip=Reader.readZip(input); input.close(); Data.readInfos(zip,false); };
  Sys.println(haxe.Json.stringify({name:info.name,version:info.version,classPath:info.classPath}));
 }
}
