import pytest

from novac.lexer import Lexer
from novac.tokens import TokenType


def types_of(tokens):
    return [t.type for t in tokens]


def test_empty_source_yields_only_eof():
    tokens = Lexer("").tokenize()
    assert types_of(tokens) == [TokenType.EOF]


def test_keywords_and_identifiers():
    tokens = Lexer("func factorial n").tokenize()
    assert types_of(tokens) == [TokenType.FUNC, TokenType.IDENT, TokenType.IDENT, TokenType.EOF]
    assert tokens[1].lexeme == "factorial"


def test_bool_literals_carry_python_bool_value():
    tokens = Lexer("true false").tokenize()
    assert tokens[0].type == TokenType.BOOL_LITERAL and tokens[0].value is True
    assert tokens[1].type == TokenType.BOOL_LITERAL and tokens[1].value is False


def test_int_and_float_literals():
    tokens = Lexer("10 3.14").tokenize()
    assert tokens[0].type == TokenType.INT_LITERAL and tokens[0].value == 10
    assert tokens[1].type == TokenType.FLOAT_LITERAL and tokens[1].value == 3.14


def test_string_literal():
    tokens = Lexer('print("hello")').tokenize()
    string_tok = tokens[2]
    assert string_tok.type == TokenType.STRING_LITERAL
    assert string_tok.value == "hello"


def test_all_operators():
    src = "+ - * / % < <= > >= == != = && || !"
    tokens = Lexer(src).tokenize()
    expected = [
        TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH, TokenType.PERCENT,
        TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE, TokenType.EQ, TokenType.NEQ,
        TokenType.ASSIGN, TokenType.AND, TokenType.OR, TokenType.NOT, TokenType.EOF,
    ]
    assert types_of(tokens) == expected


def test_punctuation_and_arrow():
    tokens = Lexer("( ) { } [ ] , : ; ->").tokenize()
    expected = [
        TokenType.LPAREN, TokenType.RPAREN, TokenType.LBRACE, TokenType.RBRACE,
        TokenType.LBRACKET, TokenType.RBRACKET, TokenType.COMMA, TokenType.COLON,
        TokenType.SEMICOLON, TokenType.ARROW, TokenType.EOF,
    ]
    assert types_of(tokens) == expected


def test_line_comment_is_stripped():
    tokens = Lexer("let x: int = 1; // this is a comment\nlet y: int = 2;").tokenize()
    # no ERROR tokens, and both statements' tokens are present
    assert TokenType.ERROR not in types_of(tokens)
    idents = [t.lexeme for t in tokens if t.type == TokenType.IDENT]
    assert idents == ["x", "y"]


def test_line_and_column_tracking_across_newlines():
    src = "let x: int = 1;\nlet y: int = 2;"
    tokens = Lexer(src).tokenize()
    # 'y' is on line 2
    y_tok = next(t for t in tokens if t.type == TokenType.IDENT and t.lexeme == "y")
    assert y_tok.line == 2


def test_full_factorial_function_tokenizes_without_errors():
    src = """
    func factorial(n: int) -> int {
        if (n <= 1) {
            return 1;
        } else {
            return n * factorial(n - 1);
        }
    }
    """
    tokens = Lexer(src).tokenize()
    assert TokenType.ERROR not in types_of(tokens)
    assert tokens[-1].type == TokenType.EOF


def test_unterminated_string_produces_error_not_crash():
    tokens = Lexer('print("unterminated').tokenize()
    error_tok = next(t for t in tokens if t.type == TokenType.ERROR)
    assert "unterminated string" in error_tok.lexeme


def test_unterminated_string_stops_at_newline():
    tokens = Lexer('let s = "oops\nlet x: int = 1;').tokenize()
    assert types_of(tokens)[0:2] == [TokenType.LET, TokenType.IDENT]
    error_toks = [t for t in tokens if t.type == TokenType.ERROR]
    assert len(error_toks) == 1
    assert error_toks[0].line == 1
    # scanning recovers and continues to lex the next line
    assert any(t.lexeme == "x" for t in tokens)


def test_invalid_character_produces_error_and_recovers():
    tokens = Lexer("let x @ int = 1;").tokenize()
    error_toks = [t for t in tokens if t.type == TokenType.ERROR]
    assert len(error_toks) == 1
    assert "@" in error_toks[0].lexeme
    # lexing continues after the bad character
    assert any(t.type == TokenType.TYPE_INT for t in tokens)


def test_malformed_numeric_literal():
    tokens = Lexer("let x: int = 12x;").tokenize()
    error_toks = [t for t in tokens if t.type == TokenType.ERROR]
    assert len(error_toks) == 1
    assert "12x" in error_toks[0].lexeme


def test_max_errors_cap_stops_tokenizing():
    src = "@" * 50
    tokens = Lexer(src).tokenize()
    error_count = sum(1 for t in tokens if t.type == TokenType.ERROR)
    assert error_count == 20  # MAX_ERRORS
    # does not necessarily reach EOF since scanning stopped early
    assert error_count <= 20


def test_lone_ampersand_and_pipe_give_helpful_errors():
    tokens = Lexer("a & b").tokenize()
    error_tok = next(t for t in tokens if t.type == TokenType.ERROR)
    assert "&&" in error_tok.lexeme

    tokens2 = Lexer("a | b").tokenize()
    error_tok2 = next(t for t in tokens2 if t.type == TokenType.ERROR)
    assert "||" in error_tok2.lexeme
