from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # literals
    INT_LITERAL = auto()
    FLOAT_LITERAL = auto()
    BOOL_LITERAL = auto()
    STRING_LITERAL = auto()
    IDENT = auto()

    # keywords
    FUNC = auto()
    LET = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    TYPE_INT = auto()
    TYPE_FLOAT = auto()
    TYPE_BOOL = auto()
    TYPE_STRING = auto()

    # operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    EQ = auto()
    NEQ = auto()
    ASSIGN = auto()
    AND = auto()
    OR = auto()
    NOT = auto()

    # punctuation
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    COLON = auto()
    SEMICOLON = auto()
    ARROW = auto()

    EOF = auto()
    ERROR = auto()


KEYWORDS = {
    "func": TokenType.FUNC,
    "let": TokenType.LET,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "return": TokenType.RETURN,
    "int": TokenType.TYPE_INT,
    "float": TokenType.TYPE_FLOAT,
    "bool": TokenType.TYPE_BOOL,
    "string": TokenType.TYPE_STRING,
    "true": TokenType.BOOL_LITERAL,
    "false": TokenType.BOOL_LITERAL,
}


@dataclass
class Token:
    type: TokenType
    lexeme: str
    value: object
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.lexeme!r}, line={self.line}, col={self.col})"
