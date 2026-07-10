from novac.lexer import Lexer
from novac.parser import Parser
from novac.semantic import SemanticAnalyzer, INT, BOOL


def check(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse_program()
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(program)
    return program, errors


def messages(errors):
    return [e.message for e in errors]


def test_full_spec_program_has_no_semantic_errors():
    src = """
    func factorial(n: int) -> int {
        if (n <= 1) {
            return 1;
        } else {
            return n * factorial(n - 1);
        }
    }

    func main() -> int {
        let x: int = 10;
        let arr: int[5] = [1, 2, 3, 4, 5];
        let sum: int = 0;

        for (let i: int = 0; i < 5; i = i + 1) {
            sum = sum + arr[i];
        }

        print(factorial(x));
        print(sum);
        return 0;
    }
    """
    program, errors = check(src)
    assert messages(errors) == []


def test_annotates_literal_types():
    program, errors = check("func f() -> int { return 5; }")
    assert errors == []
    ret_val = program.functions[0].body.statements[0].value
    assert ret_val.type == INT


def test_undeclared_variable():
    _, errors = check("func f() -> int { return y; }")
    assert any("undeclared variable 'y'" in m for m in messages(errors))


def test_undeclared_function():
    _, errors = check("func f() -> int { return g(1); }")
    assert any("undeclared function 'g'" in m for m in messages(errors))


def test_no_implicit_int_float_conversion_in_var_decl():
    _, errors = check("func f() -> int { let x: float = 5; return 0; }")
    assert any("no implicit conversion" in m for m in messages(errors))


def test_no_implicit_conversion_in_binary_op():
    _, errors = check("func f() -> int { let x: int = 1; let y: float = 2.0; let z: int = x + y; return 0; }")
    assert any("no implicit conversion" in m or "requires int or float" in m for m in messages(errors))


def test_array_literal_size_mismatch():
    _, errors = check("func f() -> int { let a: int[3] = [1, 2]; return 0; }")
    assert any("expected 3" in m for m in messages(errors))


def test_array_element_type_mismatch():
    _, errors = check("func f() -> int { let a: int[2] = [1, true]; return 0; }")
    assert any("array element type mismatch" in m for m in messages(errors))


def test_array_bounds_check_on_literal_index():
    _, errors = check("func f() -> int { let a: int[3] = [1,2,3]; return a[5]; }")
    assert any("out of bounds" in m for m in messages(errors))


def test_array_bounds_not_checked_for_variable_index():
    src = """
    func f(i: int) -> int {
        let a: int[3] = [1, 2, 3];
        return a[i];
    }
    """
    _, errors = check(src)
    assert not any("out of bounds" in m for m in messages(errors))


def test_string_variable_declaration_disallowed():
    _, errors = check('func f() -> int { let s: string = "hi"; return 0; }')
    assert any("cannot have type string" in m for m in messages(errors))


def test_string_literal_outside_print_disallowed():
    _, errors = check('func f() -> int { let x: bool = "hi" == "hi"; return 0; }')
    assert any("print()" in m for m in messages(errors))


def test_string_literal_in_print_is_fine():
    _, errors = check('func f() -> int { print("hello"); return 0; }')
    assert errors == []


def test_print_wrong_arg_count():
    _, errors = check('func f() -> int { print(1, 2); return 0; }')
    assert any("expects exactly 1 argument" in m for m in messages(errors))


def test_print_array_argument_disallowed():
    _, errors = check("func f() -> int { let a: int[2] = [1,2]; print(a); return 0; }")
    assert any("cannot take an array argument" in m for m in messages(errors))


def test_print_as_subexpression_disallowed():
    _, errors = check("func f() -> int { let x: int = print(1); return 0; }")
    assert any("print()" in m for m in messages(errors))


def test_function_argument_count_mismatch():
    src = """
    func add(a: int, b: int) -> int { return a + b; }
    func f() -> int { return add(1); }
    """
    _, errors = check(src)
    assert any("expects 2 argument" in m for m in messages(errors))


def test_function_argument_type_mismatch():
    src = """
    func add(a: int, b: int) -> int { return a + b; }
    func f() -> int { return add(1, true); }
    """
    _, errors = check(src)
    assert any("argument type mismatch" in m for m in messages(errors))


def test_duplicate_variable_in_same_scope():
    _, errors = check("func f() -> int { let x: int = 1; let x: int = 2; return x; }")
    assert any("already declared in this scope" in m for m in messages(errors))


def test_shadowing_in_nested_block_is_allowed():
    src = """
    func f() -> int {
        let x: int = 1;
        if (true) {
            let x: int = 2;
            return x;
        }
        return x;
    }
    """
    _, errors = check(src)
    assert errors == []


def test_duplicate_parameter_name():
    _, errors = check("func f(a: int, a: int) -> int { return a; }")
    assert any("duplicate parameter" in m for m in messages(errors))


def test_unreachable_code_after_return():
    _, errors = check("func f() -> int { return 1; let x: int = 2; }")
    assert any("unreachable code" in m for m in messages(errors))


def test_unreachable_code_after_fully_returning_if_else():
    src = """
    func f(n: int) -> int {
        if (n > 0) {
            return 1;
        } else {
            return 0;
        }
        let x: int = 5;
        return x;
    }
    """
    _, errors = check(src)
    assert any("unreachable code" in m for m in messages(errors))


def test_missing_return_on_some_path():
    src = """
    func f(n: int) -> int {
        if (n > 0) {
            return 1;
        }
    }
    """
    _, errors = check(src)
    assert any("does not return a value on all code paths" in m for m in messages(errors))


def test_if_else_both_returning_satisfies_all_paths_check():
    src = """
    func f(n: int) -> int {
        if (n > 0) {
            return 1;
        } else {
            return 0;
        }
    }
    """
    _, errors = check(src)
    assert errors == []


def test_for_loop_variable_not_visible_after_loop():
    src = """
    func f() -> int {
        for (let i: int = 0; i < 5; i = i + 1) {
            print(i);
        }
        return i;
    }
    """
    _, errors = check(src)
    assert any("undeclared variable 'i'" in m for m in messages(errors))


def test_array_typed_parameter_disallowed():
    _, errors = check("func f(a: int[3]) -> int { return a[0]; }")
    assert any("cannot have an array type" in m for m in messages(errors))


def test_array_typed_return_disallowed():
    _, errors = check("func f() -> int[3] { let a: int[3] = [1,2,3]; return a; }")
    assert any("cannot be used as a return type" in m for m in messages(errors))


def test_mutual_recursion_resolves_via_forward_signatures():
    src = """
    func isEven(n: int) -> bool {
        if (n == 0) {
            return true;
        } else {
            return isOdd(n - 1);
        }
    }
    func isOdd(n: int) -> bool {
        if (n == 0) {
            return false;
        } else {
            return isEven(n - 1);
        }
    }
    """
    _, errors = check(src)
    assert errors == []


def test_max_errors_cap():
    lines = "\n".join(f"let x{i}: int = y{i};" for i in range(30))
    src = f"func f() -> int {{ {lines} return 0; }}"
    _, errors = check(src)
    assert len(errors) <= 20
