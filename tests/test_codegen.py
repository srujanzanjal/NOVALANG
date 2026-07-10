from novac.codegen import compile_and_run, generate_llvm_ir
from novac.ir_gen import IRGenerator
from novac.lexer import Lexer
from novac.optimizer import PASS_REGISTRY, run_passes
from novac.parser import Parser
from novac.semantic import SemanticAnalyzer


def run_source(src, entry="main", optimize=None):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse_program()
    errors = SemanticAnalyzer().analyze(program)
    assert errors == [], f"unexpected semantic errors: {[str(e) for e in errors]}"

    tac_module = IRGenerator().generate(program)
    if optimize:
        run_passes(tac_module, optimize)

    llvm_module = generate_llvm_ir(tac_module)
    return compile_and_run(llvm_module, entry)


def test_return_value_simple():
    assert run_source("func main() -> int { return 42; }").return_value == 42


def test_arithmetic_via_return():
    assert run_source("func main() -> int { return 2 + 3 * 4; }").return_value == 14


def test_recursion_factorial():
    src = """
    func factorial(n: int) -> int {
        if (n <= 1) { return 1; } else { return n * factorial(n - 1); }
    }
    func main() -> int { return factorial(6); }
    """
    assert run_source(src).return_value == 720


def test_mutual_recursion():
    src = """
    func isEven(n: int) -> bool {
        if (n == 0) { return true; } else { return isOdd(n - 1); }
    }
    func isOdd(n: int) -> bool {
        if (n == 0) { return false; } else { return isEven(n - 1); }
    }
    func main() -> int {
        if (isEven(10)) { return 1; } else { return 0; }
    }
    """
    assert run_source(src).return_value == 1


def test_loop_and_array_sum():
    src = """
    func main() -> int {
        let arr: int[5] = [1, 2, 3, 4, 5];
        let sum: int = 0;
        for (let i: int = 0; i < 5; i = i + 1) {
            sum = sum + arr[i];
        }
        return sum;
    }
    """
    assert run_source(src).return_value == 15


def test_while_loop():
    src = """
    func main() -> int {
        let i: int = 0;
        while (i < 100) {
            i = i + 1;
        }
        return i;
    }
    """
    assert run_source(src).return_value == 100


def test_negative_int_division_and_modulo_match_c_semantics():
    src = """
    func main() -> int {
        let neg: int = 0 - 7;
        let q: int = neg / 2;
        let r: int = neg % 2;
        return q * 100 + r;
    }
    """
    # -7/2 == -3 (truncating), -7%2 == -1 (sign follows dividend) => -300 + -1 == -301
    assert run_source(src).return_value == -301


def test_short_circuit_and_never_evaluates_rhs():
    # if && didn't short-circuit, this divides by zero and crashes/traps
    src = """
    func main() -> int {
        if (false && (1 / 0 > 0)) { return 1; }
        return 0;
    }
    """
    assert run_source(src).return_value == 0


def test_short_circuit_or_never_evaluates_rhs():
    src = """
    func main() -> int {
        if (true || (1 / 0 > 0)) { return 1; }
        return 0;
    }
    """
    assert run_source(src).return_value == 1


def test_print_int(capsys):
    run_source('func main() -> int { print(42); return 0; }')
    assert capsys.readouterr().out == "42\n"


def test_print_float(capsys):
    run_source('func main() -> int { print(3.5); return 0; }')
    assert capsys.readouterr().out == "3.500000\n"


def test_print_bool(capsys):
    run_source('func main() -> int { print(true); print(false); return 0; }')
    assert capsys.readouterr().out == "true\nfalse\n"


def test_print_string_literal(capsys):
    run_source('func main() -> int { print("hello world"); return 0; }')
    assert capsys.readouterr().out == "hello world\n"


def test_full_spec_example_output_matches(capsys):
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
    result = run_source(src)
    assert result.return_value == 0
    assert capsys.readouterr().out == "3628800\n15\n"


def test_optimized_and_unoptimized_produce_identical_results(capsys):
    src = """
    func factorial(n: int) -> int {
        if (n <= 1) { return 1; } else { return n * factorial(n - 1); }
    }
    func main() -> int {
        let a: int = 2;
        let b: int = 3;
        let redundant: int = a + b;
        let also_redundant: int = a + b;
        let unused: int = also_redundant * 1000;
        print(factorial(5));
        print(redundant + also_redundant);
        return redundant + also_redundant;
    }
    """
    unopt = run_source(src)
    unopt_out = capsys.readouterr().out

    opt = run_source(src, optimize=list(PASS_REGISTRY))
    opt_out = capsys.readouterr().out

    assert unopt.return_value == opt.return_value
    assert unopt_out == opt_out
