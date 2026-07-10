from . import ast_nodes as ast

MAX_ERRORS = 20

INT = ast.Type("int")
FLOAT = ast.Type("float")
BOOL = ast.Type("bool")
STRING = ast.Type("string")

_ARITHMETIC_OPS = {"+", "-", "*", "/", "%"}
_RELATIONAL_OPS = {"<", "<=", ">", ">="}
_EQUALITY_OPS = {"==", "!="}
_LOGICAL_OPS = {"&&", "||"}


class SemanticError(Exception):
    def __init__(self, message, line, col):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        return f"{self.line}:{self.col}: {self.message}"


class FunctionSignature:
    def __init__(self, name, param_types, return_type):
        self.name = name
        self.param_types = param_types
        self.return_type = return_type


class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.symbols = {}

    def declare(self, name, type_) -> bool:
        if name in self.symbols:
            return False
        self.symbols[name] = type_
        return True

    def resolve(self, name):
        scope = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None


def always_returns(stmt) -> bool:
    """True iff control cannot fall off the end of `stmt` without hitting a
    return. Conservative: while/for are never assumed to return (no static
    trip-count analysis), so a return only after a loop is what's required.
    """
    if isinstance(stmt, ast.Return):
        return True
    if isinstance(stmt, ast.Block):
        return any(always_returns(s) for s in stmt.statements)
    if isinstance(stmt, ast.If):
        if stmt.else_branch is None:
            return False
        return always_returns(stmt.then_block) and always_returns(stmt.else_branch)
    return False


class SemanticAnalyzer:
    """Walks the AST once function signatures are collected (so recursion
    and forward references resolve regardless of source order, mirroring
    the codegen two-pass approach — decisions.md #5). Never raises: each
    error is recorded with line/col and analysis continues locally,
    capped at MAX_ERRORS (decisions.md #6)."""

    def __init__(self):
        self.errors: list[SemanticError] = []
        self.functions: dict[str, FunctionSignature] = {}
        self.current_return_type = None

    def analyze(self, program: ast.Program) -> list[SemanticError]:
        for fn in program.functions:
            if fn.name in self.functions:
                self._error(f"function '{fn.name}' is already defined", fn.line, fn.col)
                continue
            self.functions[fn.name] = FunctionSignature(
                fn.name, [p.type for p in fn.params], fn.return_type
            )

        for fn in program.functions:
            if len(self.errors) >= MAX_ERRORS:
                break
            self._check_function(fn)

        return self.errors

    def _error(self, message, line, col):
        self.errors.append(SemanticError(message, line, col))

    def _capped(self) -> bool:
        return len(self.errors) >= MAX_ERRORS

    # -- top level --

    def _check_function(self, fn: ast.Function):
        if fn.return_type.base == "string":
            self._error(
                f"function '{fn.name}': string cannot be used as a return type "
                "(strings are print()-literal-only; see decisions.md #2)",
                fn.line, fn.col,
            )

        scope = Scope()
        for p in fn.params:
            if p.type.base == "string":
                self._error(
                    f"function '{fn.name}': parameter '{p.name}' cannot have type string "
                    "(strings are print()-literal-only; see decisions.md #2)",
                    p.line, p.col,
                )
            if not scope.declare(p.name, p.type):
                self._error(f"duplicate parameter name '{p.name}'", p.line, p.col)

        prev_return_type = self.current_return_type
        self.current_return_type = fn.return_type
        self._check_block(fn.body, scope)
        self.current_return_type = prev_return_type

        if not always_returns(fn.body):
            self._error(
                f"function '{fn.name}' does not return a value on all code paths",
                fn.body.line, fn.body.col,
            )

    # -- statements --

    def _check_block(self, block: ast.Block, parent_scope: Scope) -> Scope:
        scope = Scope(parent_scope)
        seen_return = False
        for stmt in block.statements:
            if self._capped():
                break
            if seen_return:
                self._error("unreachable code after return statement", stmt.line, stmt.col)
                break
            self._check_stmt(stmt, scope)
            if always_returns(stmt):
                seen_return = True
        return scope

    def _check_stmt(self, stmt: ast.Stmt, scope: Scope):
        if isinstance(stmt, ast.VarDecl):
            self._check_var_decl(stmt, scope)
        elif isinstance(stmt, ast.Assign):
            self._check_assign(stmt, scope)
        elif isinstance(stmt, ast.If):
            self._check_if(stmt, scope)
        elif isinstance(stmt, ast.While):
            self._check_while(stmt, scope)
        elif isinstance(stmt, ast.For):
            self._check_for(stmt, scope)
        elif isinstance(stmt, ast.Return):
            self._check_return(stmt, scope)
        elif isinstance(stmt, ast.ExprStmt):
            self._check_expr_stmt(stmt, scope)
        elif isinstance(stmt, ast.Block):
            self._check_block(stmt, scope)

    def _check_var_decl(self, stmt: ast.VarDecl, scope: Scope):
        if stmt.type.base == "string":
            self._error(
                f"variable '{stmt.name}' cannot have type string "
                "(strings are print()-literal-only; see decisions.md #2)",
                stmt.line, stmt.col,
            )

        if stmt.init is not None:
            if stmt.type.is_array():
                self._check_array_init(stmt, scope)
            else:
                init_type = self._check_expr(stmt.init, scope)
                if init_type is not None and init_type != stmt.type:
                    self._error(
                        f"cannot initialize '{stmt.name}' of type {stmt.type} with {init_type} "
                        "(no implicit conversion)",
                        stmt.init.line, stmt.init.col,
                    )

        if not scope.declare(stmt.name, stmt.type):
            self._error(f"variable '{stmt.name}' already declared in this scope", stmt.line, stmt.col)

    def _check_array_init(self, stmt: ast.VarDecl, scope: Scope):
        if not isinstance(stmt.init, ast.ArrayLiteral):
            self._error(
                f"array variable '{stmt.name}' must be initialized with an array literal",
                stmt.init.line, stmt.init.col,
            )
            return
        literal = stmt.init
        if len(literal.elements) != stmt.type.array_size:
            self._error(
                f"array literal has {len(literal.elements)} elements, "
                f"expected {stmt.type.array_size}",
                literal.line, literal.col,
            )
        elem_type = ast.Type(stmt.type.base)
        for el in literal.elements:
            el_type = self._check_expr(el, scope)
            if el_type is not None and el_type != elem_type:
                self._error(
                    f"array element type mismatch: expected {elem_type}, got {el_type}",
                    el.line, el.col,
                )
        literal.type = stmt.type

    def _check_assign(self, stmt: ast.Assign, scope: Scope):
        if isinstance(stmt.target, ast.Identifier):
            target_type = scope.resolve(stmt.target.name)
            if target_type is None:
                self._error(f"undeclared variable '{stmt.target.name}'", stmt.target.line, stmt.target.col)
            stmt.target.type = target_type
        elif isinstance(stmt.target, ast.ArrayIndex):
            target_type = self._check_array_index(stmt.target, scope)
        else:
            self._error("invalid assignment target", stmt.target.line, stmt.target.col)
            target_type = None

        value_type = self._check_expr(stmt.value, scope)
        if target_type is not None and value_type is not None and target_type != value_type:
            self._error(
                f"cannot assign {value_type} to target of type {target_type} (no implicit conversion)",
                stmt.value.line, stmt.value.col,
            )

    def _check_if(self, stmt: ast.If, scope: Scope):
        cond_type = self._check_expr(stmt.cond, scope)
        if cond_type is not None and cond_type != BOOL:
            self._error(f"if condition must be bool, got {cond_type}", stmt.cond.line, stmt.cond.col)
        self._check_block(stmt.then_block, scope)
        if isinstance(stmt.else_branch, ast.If):
            self._check_if(stmt.else_branch, scope)
        elif stmt.else_branch is not None:
            self._check_block(stmt.else_branch, scope)

    def _check_while(self, stmt: ast.While, scope: Scope):
        cond_type = self._check_expr(stmt.cond, scope)
        if cond_type is not None and cond_type != BOOL:
            self._error(f"while condition must be bool, got {cond_type}", stmt.cond.line, stmt.cond.col)
        self._check_block(stmt.body, scope)

    def _check_for(self, stmt: ast.For, scope: Scope):
        for_scope = Scope(scope)
        if stmt.init is not None:
            self._check_stmt(stmt.init, for_scope)
        cond_type = self._check_expr(stmt.cond, for_scope)
        if cond_type is not None and cond_type != BOOL:
            self._error(f"for condition must be bool, got {cond_type}", stmt.cond.line, stmt.cond.col)
        self._check_stmt(stmt.update, for_scope)
        self._check_block(stmt.body, for_scope)

    def _check_return(self, stmt: ast.Return, scope: Scope):
        if stmt.value is None:
            self._error(
                f"function must return a value of type {self.current_return_type}",
                stmt.line, stmt.col,
            )
            return
        value_type = self._check_expr(stmt.value, scope)
        if value_type is not None and value_type != self.current_return_type:
            self._error(
                f"return type mismatch: expected {self.current_return_type}, got {value_type}",
                stmt.value.line, stmt.value.col,
            )

    def _check_expr_stmt(self, stmt: ast.ExprStmt, scope: Scope):
        if isinstance(stmt.expr, ast.Call) and stmt.expr.name == "print":
            self._check_print_call(stmt.expr, scope)
        else:
            self._check_expr(stmt.expr, scope)

    def _check_print_call(self, call: ast.Call, scope: Scope):
        if len(call.args) != 1:
            self._error(f"print() expects exactly 1 argument, got {len(call.args)}", call.line, call.col)
            return
        arg_type = self._check_expr(call.args[0], scope, allow_string=True)
        if arg_type is not None and arg_type.is_array():
            self._error("print() cannot take an array argument", call.args[0].line, call.args[0].col)

    # -- expressions --

    def _check_array_index(self, node: ast.ArrayIndex, scope: Scope):
        if not isinstance(node.array, ast.Identifier):
            self._error("only array variables can be indexed", node.array.line, node.array.col)
            return None
        array_type = scope.resolve(node.array.name)
        if array_type is None:
            self._error(f"undeclared variable '{node.array.name}'", node.array.line, node.array.col)
            return None
        node.array.type = array_type
        if not array_type.is_array():
            self._error(f"'{node.array.name}' is not an array", node.array.line, node.array.col)
            return None

        index_type = self._check_expr(node.index, scope)
        if index_type is not None and index_type != INT:
            self._error(f"array index must be int, got {index_type}", node.index.line, node.index.col)

        if isinstance(node.index, ast.IntLiteral):
            idx = node.index.value
            if idx < 0 or idx >= array_type.array_size:
                self._error(
                    f"array index {idx} out of bounds for array of size {array_type.array_size}",
                    node.index.line, node.index.col,
                )

        result_type = ast.Type(array_type.base)
        node.type = result_type
        return result_type

    def _check_expr(self, expr: ast.Expr, scope: Scope, allow_string=False):
        if isinstance(expr, ast.IntLiteral):
            expr.type = INT
            return INT
        if isinstance(expr, ast.FloatLiteral):
            expr.type = FLOAT
            return FLOAT
        if isinstance(expr, ast.BoolLiteral):
            expr.type = BOOL
            return BOOL
        if isinstance(expr, ast.StringLiteral):
            if not allow_string:
                self._error(
                    "string literals may only be used as a direct argument to print() "
                    "(see decisions.md #2)",
                    expr.line, expr.col,
                )
            expr.type = STRING
            return STRING
        if isinstance(expr, ast.Identifier):
            type_ = scope.resolve(expr.name)
            if type_ is None:
                self._error(f"undeclared variable '{expr.name}'", expr.line, expr.col)
            expr.type = type_
            return type_
        if isinstance(expr, ast.ArrayLiteral):
            self._error(
                "array literals may only be used to initialize an array variable declaration",
                expr.line, expr.col,
            )
            return None
        if isinstance(expr, ast.ArrayIndex):
            return self._check_array_index(expr, scope)
        if isinstance(expr, ast.UnaryOp):
            return self._check_unary_op(expr, scope)
        if isinstance(expr, ast.BinaryOp):
            return self._check_binary_op(expr, scope)
        if isinstance(expr, ast.Call):
            return self._check_call(expr, scope)
        raise AssertionError(f"unhandled expression node type: {type(expr).__name__}")

    def _check_unary_op(self, expr: ast.UnaryOp, scope: Scope):
        operand_type = self._check_expr(expr.operand, scope)
        if operand_type is None:
            return None
        if expr.op == "-":
            if operand_type not in (INT, FLOAT):
                self._error(f"unary '-' requires int or float, got {operand_type}", expr.line, expr.col)
                return None
            expr.type = operand_type
            return operand_type
        if expr.op == "!":
            if operand_type != BOOL:
                self._error(f"unary '!' requires bool, got {operand_type}", expr.line, expr.col)
                return None
            expr.type = BOOL
            return BOOL
        raise AssertionError(f"unhandled unary operator: {expr.op}")

    def _check_binary_op(self, expr: ast.BinaryOp, scope: Scope):
        left_type = self._check_expr(expr.left, scope)
        right_type = self._check_expr(expr.right, scope)
        if left_type is None or right_type is None:
            return None

        op = expr.op
        if op in _ARITHMETIC_OPS:
            if left_type not in (INT, FLOAT) or right_type not in (INT, FLOAT):
                self._error(
                    f"operator '{op}' requires int or float operands, got {left_type} and {right_type}",
                    expr.line, expr.col,
                )
                return None
            if left_type != right_type:
                self._error(
                    f"type mismatch: {left_type} {op} {right_type} (no implicit conversion)",
                    expr.line, expr.col,
                )
                return None
            expr.type = left_type
            return left_type

        if op in _RELATIONAL_OPS:
            if left_type not in (INT, FLOAT) or right_type not in (INT, FLOAT):
                self._error(
                    f"operator '{op}' requires int or float operands, got {left_type} and {right_type}",
                    expr.line, expr.col,
                )
                return None
            if left_type != right_type:
                self._error(
                    f"type mismatch: {left_type} {op} {right_type} (no implicit conversion)",
                    expr.line, expr.col,
                )
                return None
            expr.type = BOOL
            return BOOL

        if op in _EQUALITY_OPS:
            if left_type.is_array() or right_type.is_array() or left_type == STRING or right_type == STRING:
                self._error(f"operator '{op}' does not support {left_type}/{right_type}", expr.line, expr.col)
                return None
            if left_type != right_type:
                self._error(
                    f"type mismatch: {left_type} {op} {right_type} (no implicit conversion)",
                    expr.line, expr.col,
                )
                return None
            expr.type = BOOL
            return BOOL

        if op in _LOGICAL_OPS:
            if left_type != BOOL or right_type != BOOL:
                self._error(
                    f"operator '{op}' requires bool operands, got {left_type} and {right_type}",
                    expr.line, expr.col,
                )
                return None
            expr.type = BOOL
            return BOOL

        raise AssertionError(f"unhandled binary operator: {op}")

    def _check_call(self, expr: ast.Call, scope: Scope):
        if expr.name == "print":
            self._error("print() can only be used as a statement, not as an expression", expr.line, expr.col)
            return None

        sig = self.functions.get(expr.name)
        if sig is None:
            self._error(f"undeclared function '{expr.name}'", expr.line, expr.col)
            for arg in expr.args:
                self._check_expr(arg, scope)
            return None

        if len(expr.args) != len(sig.param_types):
            self._error(
                f"function '{expr.name}' expects {len(sig.param_types)} argument(s), got {len(expr.args)}",
                expr.line, expr.col,
            )

        for arg, expected_type in zip(expr.args, sig.param_types):
            arg_type = self._check_expr(arg, scope)
            if arg_type is not None and arg_type != expected_type:
                self._error(
                    f"function '{expr.name}': argument type mismatch, expected {expected_type}, got {arg_type}",
                    arg.line, arg.col,
                )
        # any extra args beyond the expected count are still type-checked for their own sake
        for arg in expr.args[len(sig.param_types):]:
            self._check_expr(arg, scope)

        expr.type = sig.return_type
        return sig.return_type
