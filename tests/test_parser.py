import novac.ast_nodes as ast
from novac.lexer import Lexer
from novac.parser import Parser


def parse(src):
    tokens = Lexer(src).tokenize()
    parser = Parser(tokens)
    program = parser.parse_program()
    return program, parser.errors


def test_minimal_function_parses():
    program, errors = parse("func main() -> int { return 0; }")
    assert errors == []
    assert len(program.functions) == 1
    fn = program.functions[0]
    assert fn.name == "main"
    assert fn.params == []
    assert fn.return_type == ast.Type("int")
    assert len(fn.body.statements) == 1
    assert isinstance(fn.body.statements[0], ast.Return)
    assert isinstance(fn.body.statements[0].value, ast.IntLiteral)
    assert fn.body.statements[0].value.value == 0


def test_params_and_array_type():
    program, errors = parse("func f(int: n, int[5]: arr) -> bool { return true; }")
    assert errors == []
    fn = program.functions[0]
    assert fn.params[0].name == "n" and fn.params[0].type == ast.Type("int")
    assert fn.params[1].name == "arr" and fn.params[1].type == ast.Type("int", 5)


def test_var_decl_with_and_without_init():
    program, errors = parse("""
    func f() -> int {
        let int: x = 5;
        let int: y;
        return x;
    }
    """)
    assert errors == []
    stmts = program.functions[0].body.statements
    assert isinstance(stmts[0], ast.VarDecl) and stmts[0].init.value == 5
    assert isinstance(stmts[1], ast.VarDecl) and stmts[1].init is None


def test_if_else_if_chain():
    program, errors = parse("""
    func f(int: n) -> int {
        if (n < 0) {
            return -1;
        } else if (n == 0) {
            return 0;
        } else {
            return 1;
        }
    }
    """)
    assert errors == []
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.If)
    assert isinstance(stmt.else_branch, ast.If)
    assert isinstance(stmt.else_branch.else_branch, ast.Block)


def test_while_loop():
    program, errors = parse("""
    func f() -> int {
        let int: i = 0;
        while (i < 10) {
            i = i + 1;
        }
        return i;
    }
    """)
    assert errors == []
    while_stmt = program.functions[0].body.statements[1]
    assert isinstance(while_stmt, ast.While)
    assert isinstance(while_stmt.body.statements[0], ast.Assign)


def test_for_loop_matches_spec_example():
    program, errors = parse("""
    func f() -> int {
        let int: sum = 0;
        let int[5]: arr = [1, 2, 3, 4, 5];
        for (let int: i = 0; i < 5; i = i + 1) {
            sum = sum + arr[i];
        }
        return sum;
    }
    """)
    assert errors == []
    for_stmt = program.functions[0].body.statements[2]
    assert isinstance(for_stmt, ast.For)
    assert isinstance(for_stmt.init, ast.VarDecl) and for_stmt.init.name == "i"
    assert isinstance(for_stmt.cond, ast.BinaryOp) and for_stmt.cond.op == "<"
    assert isinstance(for_stmt.update, ast.Assign)
    body_stmt = for_stmt.body.statements[0]
    assert isinstance(body_stmt, ast.Assign)
    assert isinstance(body_stmt.value, ast.BinaryOp) and body_stmt.value.op == "+"
    assert isinstance(body_stmt.value.right, ast.ArrayIndex)


def test_array_literal():
    program, errors = parse("func f() -> int { let int[3]: a = [1, 2, 3]; return 0; }")
    assert errors == []
    decl = program.functions[0].body.statements[0]
    assert isinstance(decl.init, ast.ArrayLiteral)
    assert [e.value for e in decl.init.elements] == [1, 2, 3]


def test_call_expression_statement():
    program, errors = parse('func f() -> int { print(42); return 0; }')
    assert errors == []
    expr_stmt = program.functions[0].body.statements[0]
    assert isinstance(expr_stmt, ast.ExprStmt)
    assert isinstance(expr_stmt.expr, ast.Call)
    assert expr_stmt.expr.name == "print"
    assert expr_stmt.expr.args[0].value == 42


def test_recursive_call_factorial_example():
    src = """
    func factorial(int: n) -> int {
        if (n <= 1) {
            return 1;
        } else {
            return n * factorial(n - 1);
        }
    }
    """
    program, errors = parse(src)
    assert errors == []
    fn = program.functions[0]
    else_return = fn.body.statements[0].else_branch.statements[0]
    assert isinstance(else_return, ast.Return)
    mult = else_return.value
    assert isinstance(mult, ast.BinaryOp) and mult.op == "*"
    assert isinstance(mult.right, ast.Call) and mult.right.name == "factorial"


def test_operator_precedence_mult_before_add():
    program, errors = parse("func f() -> int { return 1 + 2 * 3; }")
    assert errors == []
    expr = program.functions[0].body.statements[0].value
    assert isinstance(expr, ast.BinaryOp) and expr.op == "+"
    assert isinstance(expr.right, ast.BinaryOp) and expr.right.op == "*"
    assert isinstance(expr.left, ast.IntLiteral) and expr.left.value == 1


def test_logic_precedence_and_before_or():
    program, errors = parse("func f() -> bool { return true || false && true; }")
    assert errors == []
    expr = program.functions[0].body.statements[0].value
    assert isinstance(expr, ast.BinaryOp) and expr.op == "||"
    assert isinstance(expr.right, ast.BinaryOp) and expr.right.op == "&&"


def test_unary_and_parens():
    program, errors = parse("func f() -> int { return -(1 + 2); }")
    assert errors == []
    expr = program.functions[0].body.statements[0].value
    assert isinstance(expr, ast.UnaryOp) and expr.op == "-"
    assert isinstance(expr.operand, ast.BinaryOp) and expr.operand.op == "+"


def test_full_program_from_spec():
    src = """
    func factorial(int: n) -> int {
        if (n <= 1) {
            return 1;
        } else {
            return n * factorial(n - 1);
        }
    }

    func main() -> int {
        let int: x = 10;
        let int[5]: arr = [1, 2, 3, 4, 5];
        let int: sum = 0;

        for (let int: i = 0; i < 5; i = i + 1) {
            sum = sum + arr[i];
        }

        print(factorial(x));
        print(sum);
        return 0;
    }
    """
    program, errors = parse(src)
    assert errors == []
    assert [f.name for f in program.functions] == ["factorial", "main"]


# -- panic-mode recovery --

def test_missing_semicolon_recovers_and_reports_one_error():
    program, errors = parse("""
    func f() -> int {
        let int: x = 5
        return x;
    }
    """)
    assert len(errors) == 1
    # recovery continues: the function itself is still produced
    assert len(program.functions) == 1


def test_multiple_independent_errors_are_all_reported():
    src = """
    func a() -> int {
        let int: x = ;
    }

    func b() -> int {
        return +;
    }

    func c() -> int {
        return 0;
    }
    """
    program, errors = parse(src)
    assert len(errors) >= 2
    # parser recovers far enough to still find function c
    assert any(f.name == "c" for f in program.functions)


def test_max_errors_cap_stops_parsing():
    src = "func f() -> int { " + "@ " * 30 + "}"
    tokens = Lexer(src).tokenize()  # lexer itself will cap and/or emit ERROR tokens
    parser = Parser(tokens)
    parser.parse_program()
    assert len(parser.errors) <= 20
