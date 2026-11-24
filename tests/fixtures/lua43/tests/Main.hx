class Main {
 static function main() {
  final value=PurifierExample.answer();
  if(value != '{"answer":43}') throw value;
  Sys.println(value);
 }
}
