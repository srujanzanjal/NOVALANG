from .tokens import KEYWORDS, Token, TokenType

MAX_ERRORS = 20

_SINGLE_CHAR = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
    ";": TokenType.SEMICOLON,
}


class LexError(Exception):
    def __init__(self, message, line, col):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        return f"{self.line}:{self.col}: {self.message}"


class Lexer:
    """Hand-written character-by-character scanner. Never raises on bad
    input mid-scan: invalid input produces an ERROR token (with a message
    and line/col) and scanning continues, up to MAX_ERRORS (decisions.md #6)."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.errors: list[LexError] = []

    def tokenize(self) -> list[Token]:
        tokens = []
        while True:
            tok = self._next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
            if tok.type == TokenType.ERROR and len(self.errors) >= MAX_ERRORS:
                # always terminate the stream with EOF, even on early exit,
                # so downstream consumers (the parser) can rely on it being present
                tokens.append(Token(TokenType.EOF, "", None, self.line, self.col))
                break
        return tokens

    # -- character stream helpers --

    def _peek(self, offset=0):
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ""

    def _advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _match(self, expected):
        if self._peek() == expected:
            self._advance()
            return True
        return False

    def _error(self, message, line, col):
        err = LexError(message, line, col)
        self.errors.append(err)
        return Token(TokenType.ERROR, message, None, line, col)

    def _skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                while self.pos < len(self.source) and self._peek() != "\n":
                    self._advance()
            else:
                break

    def _next_token(self) -> Token:
        self._skip_whitespace_and_comments()

        if self.pos >= len(self.source):
            return Token(TokenType.EOF, "", None, self.line, self.col)

        start_line, start_col = self.line, self.col
        ch = self._advance()

        if ch.isalpha() or ch == "_":
            return self._scan_ident_or_keyword(ch, start_line, start_col)
        if ch.isdigit():
            return self._scan_number(ch, start_line, start_col)
        if ch == '"':
            return self._scan_string(start_line, start_col)

        # multi-char operators (check before single-char fallback)
        if ch == "<":
            matched = self._match("=")
            return Token(TokenType.LE if matched else TokenType.LT, "<=" if matched else "<", None, start_line, start_col)
        if ch == ">":
            matched = self._match("=")
            return Token(TokenType.GE if matched else TokenType.GT, ">=" if matched else ">", None, start_line, start_col)
        if ch == "=":
            matched = self._match("=")
            return Token(TokenType.EQ if matched else TokenType.ASSIGN, "==" if matched else "=", None, start_line, start_col)
        if ch == "!":
            matched = self._match("=")
            return Token(TokenType.NEQ if matched else TokenType.NOT, "!=" if matched else "!", None, start_line, start_col)
        if ch == "&":
            if self._match("&"):
                return Token(TokenType.AND, "&&", None, start_line, start_col)
            return self._error("unexpected character '&' (did you mean '&&'?)", start_line, start_col)
        if ch == "|":
            if self._match("|"):
                return Token(TokenType.OR, "||", None, start_line, start_col)
            return self._error("unexpected character '|' (did you mean '||'?)", start_line, start_col)
        if ch == "-" and self._peek() == ">":
            self._advance()
            return Token(TokenType.ARROW, "->", None, start_line, start_col)

        if ch in _SINGLE_CHAR:
            return Token(_SINGLE_CHAR[ch], ch, None, start_line, start_col)

        return self._error(f"unexpected character '{ch}'", start_line, start_col)

    def _scan_ident_or_keyword(self, first_char, line, col) -> Token:
        chars = [first_char]
        while self._peek().isalnum() or self._peek() == "_":
            chars.append(self._advance())
        text = "".join(chars)
        if text in KEYWORDS:
            tok_type = KEYWORDS[text]
            value = True if text == "true" else False if text == "false" else None
            return Token(tok_type, text, value, line, col)
        return Token(TokenType.IDENT, text, text, line, col)

    def _scan_number(self, first_digit, line, col) -> Token:
        digits = [first_digit]
        while self._peek().isdigit():
            digits.append(self._advance())

        is_float = False
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            digits.append(self._advance())  # consume '.'
            while self._peek().isdigit():
                digits.append(self._advance())

        text = "".join(digits)

        # malformed numeric literal: a letter immediately following, e.g. "12x"
        if self._peek().isalpha() or self._peek() == "_":
            bad_start_col = self.col
            bad_chars = [text]
            while self._peek().isalnum() or self._peek() == "_":
                bad_chars.append(self._advance())
            return self._error(
                f"malformed numeric literal '{''.join(bad_chars)}'", line, col
            )

        if is_float:
            return Token(TokenType.FLOAT_LITERAL, text, float(text), line, col)
        return Token(TokenType.INT_LITERAL, text, int(text), line, col)

    def _scan_string(self, line, col) -> Token:
        chars = []
        while True:
            if self.pos >= len(self.source):
                return self._error("unterminated string literal", line, col)
            ch = self._peek()
            if ch == "\n":
                return self._error("unterminated string literal", line, col)
            if ch == '"':
                self._advance()
                break
            chars.append(self._advance())
        return Token(TokenType.STRING_LITERAL, "".join(chars), "".join(chars), line, col)
