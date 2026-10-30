from . import ast_nodes as ast
from .tokens import Token, TokenType

MAX_ERRORS = 20

_SCALAR_TYPES = {
    TokenType.TYPE_INT: "int",
    TokenType.TYPE_FLOAT: "float",
    TokenType.TYPE_BOOL: "bool",
    TokenType.TYPE_STRING: "string",
}

# Tokens that plausibly begin a new statement/declaration — used as
# synchronization points during panic-mode recovery.
_STMT_START = {
    TokenType.LET, TokenType.IF, TokenType.WHILE, TokenType.FOR,
    TokenType.RETURN, TokenType.LBRACE, TokenType.FUNC,
}

_BINARY_OP_LEXEME = {
    TokenType.OR: "||", TokenType.AND: "&&",
    TokenType.EQ: "==", TokenType.NEQ: "!=",
    TokenType.LT: "<", TokenType.LE: "<=", TokenType.GT: ">", TokenType.GE: ">=",
    TokenType.PLUS: "+", TokenType.MINUS: "-",
    TokenType.STAR: "*", TokenType.SLASH: "/", TokenType.PERCENT: "%",
}


class ParseError(Exception):
    def __init__(self, message, line, col):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        return f"{self.line}:{self.col}: {self.message}"


class Parser:
    """Hand-written recursive-descent parser with panic-mode error
    recovery: a syntax error is recorded and parsing resynchronizes at the
    next likely statement/declaration boundary, rather than aborting on
    the first error (decisions.md philosophy, MAX_ERRORS cap per #6)."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errors: list[ParseError] = []

    # -- token stream helpers --

    def _peek(self, offset=0) -> Token:
        idx = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[idx]

    def _previous(self) -> Token:
        return self.tokens[self.pos - 1]

    def _check(self, *types) -> bool:
        return self._peek().type in types

    def _advance(self) -> Token:
        tok = self._peek()
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _match(self, *types) -> bool:
        if self._check(*types):
            self._advance()
            return True
        return False

    def _expect(self, type_, message) -> Token:
        if self._check(type_):
            return self._advance()
        tok = self._peek()
        raise ParseError(f"{message} (got {tok.type.name} {tok.lexeme!r})", tok.line, tok.col)

    def _record_error(self, err: ParseError):
        self.errors.append(err)

    def _synchronize(self):
        # skip the offending token, then advance until a plausible
        # statement/declaration boundary or EOF
        while not self._check(TokenType.EOF):
            if self._previous().type in (TokenType.SEMICOLON, TokenType.RBRACE):
                return
            if self._check(*_STMT_START):
                return
            self._advance()

    # -- entry point --

    def parse_program(self) -> ast.Program:
        functions = []
        while not self._check(TokenType.EOF):
            if len(self.errors) >= MAX_ERRORS:
                break
            try:
                functions.append(self._function())
            except ParseError as e:
                self._record_error(e)
                self._synchronize()
        return ast.Program(functions)

    # -- top level --

    def _function(self) -> ast.Function:
        tok = self._expect(TokenType.FUNC, "expected 'func'")
        name = self._expect(TokenType.IDENT, "expected function name").lexeme
        self._expect(TokenType.LPAREN, "expected '(' after function name")
        params = []
        if not self._check(TokenType.RPAREN):
            params.append(self._param())
            while self._match(TokenType.COMMA):
                params.append(self._param())
        self._expect(TokenType.RPAREN, "expected ')' after parameters")
        self._expect(TokenType.ARROW, "expected '->' before return type")
        return_type = self._type()
        body = self._block()
        return ast.Function(name, params, return_type, body, tok.line, tok.col)

    def _param(self) -> ast.Param:
        tok = self._peek()
        type_ = self._type()
        self._expect(TokenType.COLON, "expected ':' after parameter type")
        name = self._expect(TokenType.IDENT, "expected parameter name").lexeme
        return ast.Param(name, type_, tok.line, tok.col)

    def _type(self) -> ast.Type:
        tok = self._peek()
        if tok.type not in _SCALAR_TYPES:
            raise ParseError(f"expected a type, got {tok.type.name} {tok.lexeme!r}", tok.line, tok.col)
        self._advance()
        base = _SCALAR_TYPES[tok.type]
        array_size = None
        if self._match(TokenType.LBRACKET):
            size_tok = self._expect(TokenType.INT_LITERAL, "expected array size (integer literal)")
            array_size = size_tok.value
            self._expect(TokenType.RBRACKET, "expected ']' after array size")
        return ast.Type(base, array_size)

    # -- statements --

    def _block(self) -> ast.Block:
        tok = self._expect(TokenType.LBRACE, "expected '{'")
        statements = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            if len(self.errors) >= MAX_ERRORS:
                break
            try:
                statements.append(self._statement())
            except ParseError as e:
                self._record_error(e)
                self._synchronize()
        self._expect(TokenType.RBRACE, "expected '}'")
        return ast.Block(statements, tok.line, tok.col)

    def _statement(self) -> ast.Stmt:
        if self._check(TokenType.LET):
            return self._var_decl()
        if self._check(TokenType.IF):
            return self._if_stmt()
        if self._check(TokenType.WHILE):
            return self._while_stmt()
        if self._check(TokenType.FOR):
            return self._for_stmt()
        if self._check(TokenType.RETURN):
            return self._return_stmt()
        if self._check(TokenType.LBRACE):
            return self._block()
        return self._assign_or_expr_stmt()

    def _var_decl(self) -> ast.VarDecl:
        tok = self._expect(TokenType.LET, "expected 'let'")
        type_ = self._type()
        self._expect(TokenType.COLON, "expected ':' after variable type")
        name = self._expect(TokenType.IDENT, "expected variable name").lexeme
        init = None
        if self._match(TokenType.ASSIGN):
            init = self._expression()
        self._expect(TokenType.SEMICOLON, "expected ';' after variable declaration")
        return ast.VarDecl(name, type_, init, tok.line, tok.col)

    def _if_stmt(self) -> ast.If:
        tok = self._expect(TokenType.IF, "expected 'if'")
        self._expect(TokenType.LPAREN, "expected '(' after 'if'")
        cond = self._expression()
        self._expect(TokenType.RPAREN, "expected ')' after if condition")
        then_block = self._block()
        else_branch = None
        if self._match(TokenType.ELSE):
            else_branch = self._if_stmt() if self._check(TokenType.IF) else self._block()
        return ast.If(cond, then_block, else_branch, tok.line, tok.col)

    def _while_stmt(self) -> ast.While:
        tok = self._expect(TokenType.WHILE, "expected 'while'")
        self._expect(TokenType.LPAREN, "expected '(' after 'while'")
        cond = self._expression()
        self._expect(TokenType.RPAREN, "expected ')' after while condition")
        body = self._block()
        return ast.While(cond, body, tok.line, tok.col)

    def _for_stmt(self) -> ast.For:
        tok = self._expect(TokenType.FOR, "expected 'for'")
        self._expect(TokenType.LPAREN, "expected '(' after 'for'")

        if self._check(TokenType.LET):
            init = self._var_decl()  # consumes its own trailing ';'
        elif self._match(TokenType.SEMICOLON):
            init = None
        else:
            init = self._assign_stmt(consume_semicolon=True)

        cond = self._expression()
        self._expect(TokenType.SEMICOLON, "expected ';' after for-loop condition")

        update = self._assign_stmt(consume_semicolon=False)
        self._expect(TokenType.RPAREN, "expected ')' after for-loop clauses")
        body = self._block()
        return ast.For(init, cond, update, body, tok.line, tok.col)

    def _return_stmt(self) -> ast.Return:
        tok = self._expect(TokenType.RETURN, "expected 'return'")
        value = None
        if not self._check(TokenType.SEMICOLON):
            value = self._expression()
        self._expect(TokenType.SEMICOLON, "expected ';' after return statement")
        return ast.Return(value, tok.line, tok.col)

    def _assign_stmt(self, consume_semicolon: bool) -> ast.Assign:
        target = self._postfix()
        tok = self._expect(TokenType.ASSIGN, "expected '=' in assignment")
        value = self._expression()
        if consume_semicolon:
            self._expect(TokenType.SEMICOLON, "expected ';' after assignment")
        return ast.Assign(target, value, tok.line, tok.col)

    def _assign_or_expr_stmt(self) -> ast.Stmt:
        tok = self._peek()
        expr = self._expression()
        if self._match(TokenType.ASSIGN):
            value = self._expression()
            self._expect(TokenType.SEMICOLON, "expected ';' after assignment")
            return ast.Assign(expr, value, tok.line, tok.col)
        self._expect(TokenType.SEMICOLON, "expected ';' after expression")
        return ast.ExprStmt(expr, tok.line, tok.col)

    # -- expressions (lowest to highest precedence) --

    def _expression(self) -> ast.Expr:
        return self._logic_or()

    def _binary_left_assoc(self, next_level, *op_types):
        left = next_level()
        while self._check(*op_types):
            op_tok = self._advance()
            right = next_level()
            left = ast.BinaryOp(_BINARY_OP_LEXEME[op_tok.type], left, right, op_tok.line, op_tok.col)
        return left

    def _logic_or(self):
        return self._binary_left_assoc(self._logic_and, TokenType.OR)

    def _logic_and(self):
        return self._binary_left_assoc(self._equality, TokenType.AND)

    def _equality(self):
        return self._binary_left_assoc(self._relational, TokenType.EQ, TokenType.NEQ)

    def _relational(self):
        return self._binary_left_assoc(
            self._additive, TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE
        )

    def _additive(self):
        return self._binary_left_assoc(self._multiplicative, TokenType.PLUS, TokenType.MINUS)

    def _multiplicative(self):
        return self._binary_left_assoc(
            self._unary, TokenType.STAR, TokenType.SLASH, TokenType.PERCENT
        )

    def _unary(self) -> ast.Expr:
        if self._check(TokenType.NOT, TokenType.MINUS):
            op_tok = self._advance()
            op = "!" if op_tok.type == TokenType.NOT else "-"
            operand = self._unary()
            return ast.UnaryOp(op, operand, op_tok.line, op_tok.col)
        return self._postfix()

    def _postfix(self) -> ast.Expr:
        expr = self._primary()
        while self._check(TokenType.LBRACKET):
            tok = self._advance()
            index = self._expression()
            self._expect(TokenType.RBRACKET, "expected ']' after array index")
            expr = ast.ArrayIndex(expr, index, tok.line, tok.col)
        return expr

    def _primary(self) -> ast.Expr:
        tok = self._peek()

        if self._match(TokenType.INT_LITERAL):
            return ast.IntLiteral(tok.value, tok.line, tok.col)
        if self._match(TokenType.FLOAT_LITERAL):
            return ast.FloatLiteral(tok.value, tok.line, tok.col)
        if self._match(TokenType.BOOL_LITERAL):
            return ast.BoolLiteral(tok.value, tok.line, tok.col)
        if self._match(TokenType.STRING_LITERAL):
            return ast.StringLiteral(tok.value, tok.line, tok.col)

        if self._match(TokenType.IDENT):
            if self._check(TokenType.LPAREN):
                self._advance()
                args = []
                if not self._check(TokenType.RPAREN):
                    args.append(self._expression())
                    while self._match(TokenType.COMMA):
                        args.append(self._expression())
                self._expect(TokenType.RPAREN, "expected ')' after call arguments")
                return ast.Call(tok.lexeme, args, tok.line, tok.col)
            return ast.Identifier(tok.lexeme, tok.line, tok.col)

        if self._match(TokenType.LBRACKET):
            elements = []
            if not self._check(TokenType.RBRACKET):
                elements.append(self._expression())
                while self._match(TokenType.COMMA):
                    elements.append(self._expression())
            self._expect(TokenType.RBRACKET, "expected ']' after array literal")
            return ast.ArrayLiteral(elements, tok.line, tok.col)

        if self._match(TokenType.LPAREN):
            expr = self._expression()
            self._expect(TokenType.RPAREN, "expected ')' after expression")
            return expr

        raise ParseError(f"expected an expression, got {tok.type.name} {tok.lexeme!r}", tok.line, tok.col)
