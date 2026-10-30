const KEYWORD = new Set([
  "FUNC", "LET", "IF", "ELSE", "WHILE", "FOR", "RETURN",
  "TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING",
]);
const LITERAL = new Set(["INT_LITERAL", "FLOAT_LITERAL", "BOOL_LITERAL", "STRING_LITERAL"]);
const OPERATOR = new Set([
  "PLUS", "MINUS", "STAR", "SLASH", "PERCENT", "LT", "LE", "GT", "GE",
  "EQ", "NEQ", "ASSIGN", "AND", "OR", "NOT",
]);
const PUNCTUATION = new Set([
  "LPAREN", "RPAREN", "LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
  "COMMA", "COLON", "SEMICOLON", "ARROW",
]);

export function tokenCategory(type) {
  if (type === "IDENT") return "ident";
  if (type === "EOF" || type === "ERROR") return "meta";
  if (KEYWORD.has(type)) return "keyword";
  if (LITERAL.has(type)) return "literal";
  if (OPERATOR.has(type)) return "operator";
  if (PUNCTUATION.has(type)) return "punctuation";
  return "meta";
}
