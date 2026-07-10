"""Constant propagation: if `dest = Const`, later uses of `dest` in the
SAME block (before it's redefined) are replaced with that Const directly.
Scoped to a single basic block, matching CSE's local scope (decisions.md
#1) - proving a value is still constant across a block boundary needs real
dataflow analysis (reaching definitions), which is out of scope here."""

from .. import ir
from ._common import dest_of


def _substitute(operand, known):
    if isinstance(operand, (ir.Var, ir.Temp)) and operand.name in known:
        return known[operand.name]
    return operand


def _substitute_operands(instr, known):
    if isinstance(instr, ir.BinOp):
        return ir.BinOp(instr.dest, instr.op, _substitute(instr.left, known), _substitute(instr.right, known))
    if isinstance(instr, ir.UnaryOp):
        return ir.UnaryOp(instr.dest, instr.op, _substitute(instr.operand, known))
    if isinstance(instr, ir.Copy):
        return ir.Copy(instr.dest, _substitute(instr.src, known))
    if isinstance(instr, ir.ArrayLoad):
        # instr.array itself is never substituted - arrays aren't foldable values
        return ir.ArrayLoad(instr.dest, instr.array, _substitute(instr.index, known))
    if isinstance(instr, ir.ArrayStore):
        return ir.ArrayStore(instr.array, _substitute(instr.index, known), _substitute(instr.src, known))
    if isinstance(instr, ir.Call):
        return ir.Call(instr.dest, instr.func_name, [_substitute(a, known) for a in instr.args])
    if isinstance(instr, ir.Print):
        return ir.Print(_substitute(instr.value, known))
    if isinstance(instr, ir.CondBranch):
        return ir.CondBranch(_substitute(instr.cond, known), instr.true_target, instr.false_target)
    if isinstance(instr, ir.Return):
        return instr if instr.value is None else ir.Return(_substitute(instr.value, known))
    if isinstance(instr, ir.Branch):
        return instr
    raise AssertionError(f"constant propagation: unhandled instruction {type(instr).__name__}")


def _propagate_in_block(block: ir.BasicBlock) -> bool:
    changed = False
    known = {}  # ir var/temp name -> Const
    new_instructions = []

    for instr in block.instructions:
        new_instr = _substitute_operands(instr, known)
        changed |= new_instr is not instr
        new_instructions.append(new_instr)

        dest = dest_of(new_instr)
        if dest is not None:
            if isinstance(new_instr, ir.Copy) and isinstance(new_instr.src, ir.Const):
                known[dest.name] = new_instr.src
            else:
                known.pop(dest.name, None)
    block.instructions = new_instructions

    if block.terminator is not None:
        new_term = _substitute_operands(block.terminator, known)
        changed |= new_term is not block.terminator
        block.terminator = new_term

    return changed


def run(module: ir.Module) -> bool:
    changed = False
    for func in module.functions:
        for block in func.blocks.values():
            changed |= _propagate_in_block(block)
    return changed
