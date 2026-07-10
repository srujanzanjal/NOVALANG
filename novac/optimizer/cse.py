"""Common subexpression elimination, local to a single basic block
(decisions.md #1 — cross-block CSE needs dominance info and is a stretch
goal). If the same BinOp/UnaryOp/ArrayLoad expression is computed again
later in the same block with the same operands, the later instruction is
replaced with a Copy from the first computation's result.

Arrays can never cross a function boundary (decisions.md #11), so a Call
can never mutate an array visible in the current function — the only
aliasing hazard CSE has to guard against is an ArrayStore to the same
array invalidating any cached load of it.
"""

from .. import ir
from ._common import dest_of


def _key_for(instr):
    if isinstance(instr, ir.BinOp):
        return ("binop", instr.op, instr.left, instr.right)
    if isinstance(instr, ir.UnaryOp):
        return ("unaryop", instr.op, instr.operand)
    if isinstance(instr, ir.ArrayLoad):
        return ("aload", instr.array, instr.index)
    return None


def _names_in_key(key):
    names = set()
    for part in key[1:]:
        if isinstance(part, (ir.Var, ir.Temp)):
            names.add(part.name)
    return names


def _invalidate_by_name(available, name):
    for key in [k for k in available if name in _names_in_key(k)]:
        del available[key]


def _cse_in_block(block: ir.BasicBlock) -> bool:
    changed = False
    available = {}  # expression key -> operand holding its previously computed value
    new_instructions = []

    for instr in block.instructions:
        key = _key_for(instr)

        if key is not None and key in available:
            new_instructions.append(ir.Copy(instr.dest, available[key]))
            changed = True
        else:
            new_instructions.append(instr)
            if key is not None:
                available[key] = instr.dest

        if isinstance(instr, ir.ArrayStore):
            _invalidate_by_name(available, instr.array.name)

        dest = dest_of(instr)
        if dest is not None:
            _invalidate_by_name(available, dest.name)

    block.instructions = new_instructions
    return changed


def run(module: ir.Module) -> bool:
    changed = False
    for func in module.functions:
        for block in func.blocks.values():
            changed |= _cse_in_block(block)
    return changed
