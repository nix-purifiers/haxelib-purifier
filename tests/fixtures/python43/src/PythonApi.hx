@:pythonImport("foreign_answer", "ForeignApi")
extern class ForeignBinding { public static function answer():Int; }
class PythonApi {
 public static function answer():Int { return haxe.Json.parse(PurifierExample.answer()).answer; }
 public static function combined():Int { return answer() + ForeignBinding.answer(); }
}
