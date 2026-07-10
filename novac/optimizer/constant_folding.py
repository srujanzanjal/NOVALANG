"""Constant folding: BinOp/UnaryOp instructions whose operands are both
compile-time constants are replaced with a Copy of the computed value. A
CondBranch whose condition folds to a constant is simplified to an
unconditional Branch, which typically hands DCE's unreachable-block
elimination a whole dead branch to remove.

Integer division/modulo use C-truncating semantics to exactly match what
Phase 6 emits at runtime (LLVM sdiv/srem) - see decisions.md #12. Getting
this wrong would mean -O2 silently computes a different answer than -O0
for negative operands, which is a correctness bug hiding inside the
project's headline "measurable, behavior-preserving optimization" claim.
"""

import math

from .. import ir

_REL_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}
_EQ_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _c_trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _c_trunc_rem(a, b):
    return a - _c_trunc_div(a, b) * b


def _eval_binop(op, left: ir.Const, right: ir.Const):
    a, b = left.value, right.value
    t = left.type  # left.type == right.type is guaranteed by semantic analysis

    if op == "+":
        return ir.Const(a + b, t)
    if op == "-":
        return ir.Const(a - b, t)
    if op == "*":
        return ir.Const(a * b, t)
    if op == "/":
        if b == 0:
            return None  # leave division by zero unfolded; it fails at runtime either way
        return ir.Const(_c_trunc_div(a, b), "int") if t == "int" else ir.Const(a / b, "float")
    if op == "%":
        if b == 0:
            return None
        return ir.Const(_c_trunc_rem(a, b), "int") if t == "int" else ir.Const(math.fmod(a, b), "float")
    if op in _REL_OPS:
        return ir.Const(_REL_OPS[op](a, b), "bool")
    if op in _EQ_OPS:
        return ir.Const(_EQ_OPS[op](a, b), "bool")
    raise AssertionError(f"constant folding: unhandled binary operator {op!r}")


def _eval_unaryop(op, operand: ir.Const):
    if op == "-":
        return ir.Const(-operand.value, operand.type)
    if op == "!":
        return ir.Const(not operand.value, "bool")
    raise AssertionError(f"constant folding: unhandled unary operator {op!r}")


def run(module: ir.Module) -> bool:
    changed = False
    for func in module.functions:
        for block in func.blocks.values():
            for i, instr in enumerate(block.instructions):
                folded = None
                if isinstance(instr, ir.BinOp) and isinstance(instr.left, ir.Const) and isinstance(instr.right, ir.Const):
                    folded = _eval_binop(instr.op, instr.left, instr.right)
                elif isinstance(instr, ir.UnaryOp) and isinstance(instr.operand, ir.Const):
                    folded = _eval_unaryop(instr.op, instr.operand)
                if folded is not None:
                    block.instructions[i] = ir.Copy(instr.dest, folded)
                    changed = True

            term = block.terminator
            if isinstance(term, ir.CondBranch) and isinstance(term.cond, ir.Const):
                block.terminator = ir.Branch(term.true_target if term.cond.value else term.false_target)
                changed = True

    if changed:
        for func in module.functions:
            func.link_preds_succs()
    return changed
