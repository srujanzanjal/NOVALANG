import io

import pytest

from novac.cli import main

FACTORIAL_SRC = """
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


@pytest.fixture
def nova_file(tmp_path):
    def _write(src, name="prog.nova"):
        path = tmp_path / name
        path.write_text(src)
        return str(path)
    return _write


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    code = main(args, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_missing_file_reports_error(tmp_path):
    code, out, err = run_cli([str(tmp_path / "does_not_exist.nova")])
    assert code == 1
    assert "cannot read" in err


def test_compiles_successfully_with_no_flags(nova_file):
    path = nova_file(FACTORIAL_SRC)
    code, out, err = run_cli([path])
    assert code == 0
    assert err == ""
    assert "compiled successfully" in out


def test_run_executes_and_returns_exit_code(nova_file, capsys):
    # the executed program's print() output is the program's own stdout
    # (exactly like a real compiled binary's), not the CLI tool's out
    # stream — so it shows up via capsys, not run_cli()'s injected out.
    path = nova_file(FACTORIAL_SRC)
    code, out, err = run_cli([path, "--run"])
    assert code == 0
    assert capsys.readouterr().out == "3628800\n15\n"


def test_dump_stage_tokens(nova_file):
    path = nova_file("func main() -> int { return 0; }")
    code, out, err = run_cli([path, "--dump-stage=tokens"])
    assert code == 0
    assert "FUNC" in out and "IDENT" in out and "EOF" in out


def test_dump_stage_ast(nova_file):
    path = nova_file("func main() -> int { return 0; }")
    code, out, err = run_cli([path, "--dump-stage=ast"])
    assert code == 0
    assert "Program" in out
    assert "Function" in out
    assert "Return" in out


def test_dump_stage_tac_shows_basic_blocks(nova_file):
    path = nova_file(FACTORIAL_SRC)
    code, out, err = run_cli([path, "--dump-stage=tac"])
    assert code == 0
    assert "func factorial" in out
    assert "func main" in out
    assert "if.then" in out


def test_dump_stage_optimized_tac_defaults_to_o2(nova_file):
    src = "func main() -> int { let x: int = 2 + 3; return 0; }"
    path = nova_file(src)
    code, out, err = run_cli([path, "--dump-stage=optimized-tac"])
    assert code == 0
    # constant folding (part of the implied -O2 default for this stage) should have run
    assert "2 + 3" not in out


def test_dump_stage_tac_is_not_optimized_by_default(nova_file):
    src = "func main() -> int { let x: int = 2 + 3; return 0; }"
    path = nova_file(src)
    code, out, err = run_cli([path, "--dump-stage=tac"])
    assert code == 0
    assert "2 + 3" in out


def test_dump_stage_llvm_ir(nova_file):
    path = nova_file("func main() -> int { return 0; }")
    code, out, err = run_cli([path, "--dump-stage=llvm-ir"])
    assert code == 0
    assert "define i32" in out
    assert '@"main"' in out


def test_explicit_passes_flag(nova_file):
    src = "func main() -> int { let x: int = 2 + 3; return 0; }"
    path = nova_file(src)
    code, out, err = run_cli([path, "--passes=const-fold", "--dump-stage=optimized-tac"])
    assert code == 0
    assert "2 + 3" not in out


def test_unknown_pass_name_reports_error(nova_file):
    path = nova_file("func main() -> int { return 0; }")
    code, out, err = run_cli([path, "--passes=not-a-real-pass"])
    assert code == 2
    assert "unknown optimization pass" in err


def test_lexer_error_reported_and_nonzero_exit(nova_file):
    path = nova_file('func main() -> int { let s: string = "unterminated; return 0; }')
    code, out, err = run_cli([path])
    assert code == 1
    assert "error:" in err


def test_multiple_parse_errors_all_reported(nova_file):
    src = """
    func a() -> int {
        let x: int = ;
    }
    func b() -> int {
        return +;
    }
    func c() -> int {
        return 0;
    }
    """
    path = nova_file(src)
    code, out, err = run_cli([path])
    assert code == 1
    assert err.count("error:") >= 2


def test_semantic_error_reported(nova_file):
    path = nova_file("func main() -> int { return y; }")
    code, out, err = run_cli([path])
    assert code == 1
    assert "undeclared variable" in err


def test_run_without_main_reports_clear_error(nova_file):
    path = nova_file("func f() -> int { return 0; }")
    code, out, err = run_cli([path, "--run"])
    assert code == 1
    assert "main" in err


def test_o0_o1_o2_are_mutually_exclusive_with_passes(nova_file):
    path = nova_file("func main() -> int { return 0; }")
    with pytest.raises(SystemExit):
        run_cli([path, "-O2", "--passes=dce"])
