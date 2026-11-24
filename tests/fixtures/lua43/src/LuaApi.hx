@:expose("example.Api")
class LuaApi {
  public static function answer():String { return PurifierExample.answer(); }
  public static function codepoints():Int { return lua.lib.luautf8.Utf8.len("λ雪"); }
  public static function matches(value:String):Bool { return ~/^[a-z]+$/.match(value); }
}
