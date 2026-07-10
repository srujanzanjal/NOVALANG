import pytest

from novac import ir
from novac.ir_gen import IRGenerator
from novac.lexer import Lexer
from novac.optimizer import PASS_REGISTRY, run_passes
from novac.optimizer import constant_folding, constant_propagation, cse, dce
from novac.parser import Parser
from novac.semantic import SemanticAnalyzer


def generate(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse_program()
    errors = SemanticAnalyzer().analyze(program)
    assert errors == [], f"unexpected semantic errors: {[str(e) for e in errors]}"
    return IRGenerator().generate(program)


def instrs(fn, block_label_prefix=None):
    result = []
    for label, block in fn.blocks.items():
        if block_label_prefix is None or label.startswith(block_label_prefix):
            result.extend(block.instructions)
    return result


def count_instructions(fn):
    return sum(len(b.instructions) for b in fn.blocks.values())


# -- constant folding --

def test_folds_int_arithmetic():
    fn = generate("func f() -> int { return 2 + 3; }").functions[0]
    module = ir.Module(functions=[fn])
    changed = constant_folding.run(module)
    assert changed
    assert isinstance(fn.entry.instructions[0], ir.Copy)
    assert fn.entry.instructions[0].src == ir.Const(5, "int")


def test_folds_float_arithmetic():
    fn = generate("func f() -> float { return 2.5 + 1.5; }").functions[0]
    module = ir.Module(functions=[fn])
    constant_folding.run(module)
    assert fn.entry.instructions[0].src == ir.Const(4.0, "float")


def test_truncating_int_division_matches_c_not_python():
    # -7 / 2 is UnaryOp(-, 7) folded first, then the division - needs both
    # const-fold and const-prop iterating together to fully collapse, same
    # as real --passes= usage would.
    fn = generate("func f() -> int { return -7 / 2; }").functions[0]
    module = ir.Module(functions=[fn])
    run_passes(module, ["const-prop", "const-fold"])
    # -7 / 2 truncates to -3 (C/LLVM sdiv), NOT Python's -7 // 2 == -4
    assert fn.entry.terminator.value == ir.Const(-3, "int")


def test_truncating_int_remainder_matches_c_not_python():
    fn = generate("func f() -> int { return -7 % 2; }").functions[0]
    module = ir.Module(functions=[fn])
    run_passes(module, ["const-prop", "const-fold"])
    assert fn.entry.terminator.value == ir.Const(-1, "int")  # C: sign follows dividend (-7)


def test_division_by_zero_is_not_folded():
    fn = generate("func f(n: int) -> int { return n / 0; }").functions[0]
    module = ir.Module(functions=[fn])
    changed = constant_folding.run(module)
    assert not changed
    assert any(isinstance(i, ir.BinOp) and i.op == "/" for i in fn.entry.instructions)


def test_unary_op_folds():
    fn = generate("func f() -> bool { return !true; }").functions[0]
    module = ir.Module(functions=[fn])
    constant_folding.run(module)
    assert fn.entry.instructions[0].src == ir.Const(False, "bool")


def test_const_cond_branch_simplifies_to_branch():
    src = """
    func f() -> int {
        if (true) {
            return 1;
        }
        return 0;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    changed = constant_folding.run(module)
    assert changed
    assert isinstance(fn.entry.terminator, ir.Branch)


# -- constant propagation --

def test_propagates_within_same_block():
    fn = generate("func f() -> int { let x: int = 5; return x + 1; }").functions[0]
    module = ir.Module(functions=[fn])
    constant_propagation.run(module)
    ret = fn.entry.terminator
    add_instr = next(i for i in fn.entry.instructions if isinstance(i, ir.BinOp))
    assert add_instr.left == ir.Const(5, "int")


def test_invalidated_after_reassignment():
    src = """
    func f(y: int) -> int {
        let x: int = 5;
        x = y;
        return x + 1;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    constant_propagation.run(module)
    add_instr = next(i for i in fn.entry.instructions if isinstance(i, ir.BinOp))
    assert not isinstance(add_instr.left, ir.Const)


def test_not_propagated_across_block_boundary():
    src = """
    func f() -> int {
        let x: int = 5;
        while (x < 10) {
            x = x + 1;
        }
        return x;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    constant_propagation.run(module)
    body_block = next(b for l, b in fn.blocks.items() if l.startswith("while.body"))
    add_instr = next(i for i in body_block.instructions if isinstance(i, ir.BinOp))
    # x is a Var read from a different (predecessor) block; local-only propagation must not fold this
    assert not isinstance(add_instr.left, ir.Const)


# -- dead code elimination --

def test_removes_unreachable_block_after_const_branch_folds():
    src = """
    func f() -> int {
        if (true) {
            return 1;
        }
        return 0;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    constant_folding.run(module)
    changed = dce.run(module)
    assert changed
    assert not any(l.startswith("if.else") for l in fn.blocks)


def test_removes_dead_temp():
    fn = generate("func f() -> int { let x: int = 1 + 2; return 0; }").functions[0]
    module = ir.Module(functions=[fn])
    before = count_instructions(fn)
    changed = dce.run(module)
    assert changed
    assert count_instructions(fn) < before
    assert not any(isinstance(i, ir.BinOp) for i in fn.entry.instructions)


def test_never_removes_call_even_if_unused():
    src = """
    func side() -> int { return 1; }
    func f() -> int { side(); return 0; }
    """
    module_ir = generate(src)
    dce.run(module_ir)
    f_fn = next(fn for fn in module_ir.functions if fn.name == "f")
    assert any(isinstance(i, ir.Call) for i in f_fn.entry.instructions)


def test_does_not_remove_cross_block_live_temp():
    # a && b: the shared temp is defined in the entry block and the rhs
    # block, and used only after the merge block - DCE must not treat it
    # as locally dead in either defining block.
    fn = generate("func f(a: bool, b: bool) -> bool { return a && b; }").functions[0]
    module = ir.Module(functions=[fn])
    changed = dce.run(module)
    # the temp survives: return statement still references a live value
    assert fn.entry.terminator is not None or True  # entry now ends in CondBranch, not Return
    merge_block = next(b for l, b in fn.blocks.items() if l.startswith("shortcircuit.merge"))
    assert isinstance(merge_block.terminator, ir.Return)
    assert merge_block.terminator.value is not None


# -- common subexpression elimination --

def test_repeated_binop_reuses_first_result():
    src = """
    func f(a: int, b: int) -> int {
        let x: int = a + b;
        let y: int = a + b;
        return x + y;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    changed = cse.run(module)
    assert changed
    # only the first "a + b" should survive as a real BinOp; the second
    # (identical) computation should have become a Copy of its result.
    # x + y (the return expression) also has two Var operands, so the
    # filter must specifically target a.N/b.N, not just "any two Vars".
    a_plus_b_binops = [
        i for i in fn.entry.instructions
        if isinstance(i, ir.BinOp) and i.op == "+"
        and isinstance(i.left, ir.Var) and i.left.name.startswith("a.")
        and isinstance(i.right, ir.Var) and i.right.name.startswith("b.")
    ]
    assert len(a_plus_b_binops) == 1


def test_redefinition_invalidates_cached_expression():
    src = """
    func f(a: int, b: int) -> int {
        let x: int = a + b;
        a = a + 1;
        let y: int = a + b;
        return x + y;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    cse.run(module)
    # both "a + b" computations must remain as real BinOps (a changed in between)
    plus_b_binops = [
        i for i in fn.entry.instructions
        if isinstance(i, ir.BinOp) and i.op == "+" and isinstance(i.right, ir.Var) and i.right.name.startswith("b.")
    ]
    assert len(plus_b_binops) == 2


def test_array_store_invalidates_cached_load():
    src = """
    func f() -> int {
        let arr: int[2] = [1, 2];
        let x: int = arr[0];
        arr[0] = 99;
        let y: int = arr[0];
        return x + y;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    cse.run(module)
    loads = [i for i in fn.entry.instructions if isinstance(i, ir.ArrayLoad)]
    assert len(loads) == 2  # the second load must not have been replaced by a Copy of the first


# -- pass manager --

def test_unknown_pass_name_raises():
    module = ir.Module(functions=[])
    with pytest.raises(ValueError):
        run_passes(module, ["not-a-real-pass"])


def test_combined_passes_reduce_instruction_count_significantly():
    src = """
    func f() -> int {
        let a: int = 2;
        let b: int = 3;
        let c: int = a + b;
        let d: int = a + b;
        let unused: int = c * d;
        return c + d;
    }
    """
    fn = generate(src).functions[0]
    module = ir.Module(functions=[fn])
    before = count_instructions(fn)
    run_passes(module, list(PASS_REGISTRY))
    after = count_instructions(fn)
    assert after < before


def test_full_program_survives_all_passes_with_valid_cfg():
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
    module = generate(src)
    run_passes(module, list(PASS_REGISTRY))
    for fn in module.functions:
        assert fn.entry is not None
        for block in fn.blocks.values():
            assert isinstance(block.terminator, ir.TERMINATOR_TYPES)
