from novac import ir
from novac.ir_gen import IRGenerator
from novac.lexer import Lexer
from novac.parser import Parser
from novac.semantic import SemanticAnalyzer


def generate(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse_program()
    errors = SemanticAnalyzer().analyze(program)
    assert errors == [], f"unexpected semantic errors: {[str(e) for e in errors]}"
    return IRGenerator().generate(program)


def test_simple_function_single_block():
    fn = generate("func main() -> int { return 0; }").functions[0]
    assert len(fn.blocks) == 1
    assert isinstance(fn.entry.terminator, ir.Return)
    assert fn.entry.terminator.value == ir.Const(0, "int")


def test_var_decl_and_return_chain_through_copy():
    fn = generate("func f() -> int { let x: int = 5; return x; }").functions[0]
    entry = fn.entry
    assert isinstance(entry.instructions[0], ir.Copy)
    assert entry.instructions[0].src == ir.Const(5, "int")
    assert entry.terminator.value == entry.instructions[0].dest


def test_binary_op_generates_temp():
    fn = generate("func f() -> int { return 1 + 2; }").functions[0]
    entry = fn.entry
    assert isinstance(entry.instructions[0], ir.BinOp)
    assert entry.instructions[0].op == "+"
    assert entry.terminator.value == entry.instructions[0].dest


def test_if_else_both_returning_has_no_merge_block():
    src = """
    func f(n: int) -> int {
        if (n > 0) { return 1; } else { return 0; }
    }
    """
    fn = generate(src).functions[0]
    labels = set(fn.blocks.keys())
    assert any(l.startswith("if.then") for l in labels)
    assert any(l.startswith("if.else") for l in labels)
    assert not any(l.startswith("if.merge") for l in labels)
    assert isinstance(fn.entry.terminator, ir.CondBranch)


def test_if_without_else_creates_merge_block():
    src = """
    func f(n: int) -> int {
        if (n > 0) {
            return 1;
        }
        return 0;
    }
    """
    fn = generate(src).functions[0]
    labels = set(fn.blocks.keys())
    assert any(l.startswith("if.merge") for l in labels)
    merge_block = next(b for l, b in fn.blocks.items() if l.startswith("if.merge"))
    assert isinstance(merge_block.terminator, ir.Return)


def test_cfg_preds_succs_linked_for_if_without_else():
    src = """
    func f(n: int) -> int {
        if (n > 0) {
            return 1;
        }
        return 0;
    }
    """
    fn = generate(src).functions[0]
    merge_block = next(b for l, b in fn.blocks.items() if l.startswith("if.merge"))
    then_block = next(b for l, b in fn.blocks.items() if l.startswith("if.then"))
    assert merge_block.preds == [fn.entry]
    assert then_block in fn.entry.succs
    assert merge_block in fn.entry.succs


def test_while_loop_structure():
    src = """
    func f() -> int {
        let i: int = 0;
        while (i < 5) {
            i = i + 1;
        }
        return i;
    }
    """
    fn = generate(src).functions[0]
    labels = set(fn.blocks.keys())
    assert any(l.startswith("while.cond") for l in labels)
    assert any(l.startswith("while.body") for l in labels)
    assert any(l.startswith("while.after") for l in labels)

    cond_block = next(b for l, b in fn.blocks.items() if l.startswith("while.cond"))
    body_block = next(b for l, b in fn.blocks.items() if l.startswith("while.body"))
    assert isinstance(cond_block.terminator, ir.CondBranch)
    assert isinstance(body_block.terminator, ir.Branch)
    assert body_block.terminator.target == cond_block.label  # loop back edge


def test_for_loop_variable_is_scoped_and_distinct():
    src = """
    func f() -> int {
        let sum: int = 0;
        for (let i: int = 0; i < 5; i = i + 1) {
            sum = sum + i;
        }
        return sum;
    }
    """
    fn = generate(src).functions[0]
    names = list(fn.locals.keys())
    assert any(n.startswith("i.") for n in names)
    assert any(n.startswith("sum.") for n in names)


def test_array_store_and_load():
    src = """
    func f() -> int {
        let arr: int[3] = [1, 2, 3];
        return arr[1];
    }
    """
    fn = generate(src).functions[0]
    entry = fn.entry
    stores = [i for i in entry.instructions if isinstance(i, ir.ArrayStore)]
    loads = [i for i in entry.instructions if isinstance(i, ir.ArrayLoad)]
    assert len(stores) == 3
    assert [s.index for s in stores] == [ir.Const(0, "int"), ir.Const(1, "int"), ir.Const(2, "int")]
    assert len(loads) == 1
    assert loads[0].index == ir.Const(1, "int")


def test_temps_are_typed_in_func_locals():
    # codegen needs an LLVM type for every temp to alloca a stack slot for
    # it, so ir_gen must record temp types in func.locals just like vars.
    from novac.ast_nodes import Type

    fn = generate("func f() -> int { return 1 + 2; }").functions[0]
    binop = next(i for i in fn.entry.instructions if isinstance(i, ir.BinOp))
    assert fn.locals[binop.dest.name] == Type("int")


def test_shadowed_variables_get_distinct_ir_names():
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
    fn = generate(src).functions[0]
    x_names = [n for n in fn.locals.keys() if n.startswith("x.")]
    assert len(x_names) == 2
    assert x_names[0] != x_names[1]


def test_short_circuit_and_creates_rhs_and_merge_blocks():
    fn = generate("func f(a: bool, b: bool) -> bool { return a && b; }").functions[0]
    labels = set(fn.blocks.keys())
    assert any(l.startswith("shortcircuit.rhs") for l in labels)
    assert any(l.startswith("shortcircuit.merge") for l in labels)
    # short-circuit-on-false: true branch of the CondBranch goes to rhs
    rhs_label = next(l for l in labels if l.startswith("shortcircuit.rhs"))
    assert fn.entry.terminator.true_target == rhs_label


def test_short_circuit_or_branches_opposite_of_and():
    fn = generate("func f(a: bool, b: bool) -> bool { return a || b; }").functions[0]
    labels = set(fn.blocks.keys())
    rhs_label = next(l for l in labels if l.startswith("shortcircuit.rhs"))
    # short-circuit-on-true: false target of the CondBranch goes to rhs
    assert fn.entry.terminator.false_target == rhs_label


def test_recursive_factorial_and_main_generate_without_crashing():
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
    assert [f.name for f in module.functions] == ["factorial", "main"]

    factorial_fn = module.functions[0]
    calls = [
        instr
        for block in factorial_fn.blocks.values()
        for instr in block.instructions
        if isinstance(instr, ir.Call)
    ]
    assert any(c.func_name == "factorial" for c in calls)

    main_fn = module.functions[1]
    prints = [
        instr
        for block in main_fn.blocks.values()
        for instr in block.instructions
        if isinstance(instr, ir.Print)
    ]
    assert len(prints) == 2


def test_every_block_has_exactly_one_terminator():
    src = """
    func factorial(n: int) -> int {
        if (n <= 1) {
            return 1;
        } else {
            return n * factorial(n - 1);
        }
    }
    func main() -> int {
        let sum: int = 0;
        for (let i: int = 0; i < 5; i = i + 1) {
            if (i == 2) {
                sum = sum + 100;
            }
            sum = sum + i;
        }
        return sum;
    }
    """
    module = generate(src)
    for fn in module.functions:
        for block in fn.blocks.values():
            assert block.terminator is not None, f"{fn.name}:{block.label} has no terminator"
            assert isinstance(block.terminator, ir.TERMINATOR_TYPES)
