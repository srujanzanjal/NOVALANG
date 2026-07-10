"""Dead code elimination: unreachable-block elimination (BFS reachability
from the entry block, transitively — stronger than a plain
no-predecessors check and just as cheap given link_preds_succs already
exists) plus dead-instruction elimination.

Dead-instruction elimination deliberately checks whole-function usage,
not just same-block usage, even though tac_spec.md originally described
this pass as purely per-block: a per-block-only check would be UNSOUND
here, because short-circuit && / || codegen (ir_gen.py) defines a temp in
one block and reassigns it in another before it's ever used in a third —
a same-block-only liveness check would incorrectly remove it. Only
BinOp/UnaryOp/Copy/ArrayLoad are eligible for removal; Call is never
removed even with an unused result (this project makes no purity/
termination analysis, so a call could still matter for recursion depth or
cost), and Print/ArrayStore have no removable result value at all.
"""

from .. import ir
from ._common import dest_of


def _operands_read_by(instr):
    if isinstance(instr, ir.BinOp):
        return [instr.left, instr.right]
    if isinstance(instr, ir.UnaryOp):
        return [instr.operand]
    if isinstance(instr, ir.Copy):
        return [instr.src]
    if isinstance(instr, ir.ArrayLoad):
        return [instr.array, instr.index]
    if isinstance(instr, ir.ArrayStore):
        return [instr.array, instr.index, instr.src]
    if isinstance(instr, ir.Call):
        return list(instr.args)
    if isinstance(instr, ir.Print):
        return [instr.value]
    if isinstance(instr, ir.CondBranch):
        return [instr.cond]
    if isinstance(instr, ir.Return):
        return [instr.value] if instr.value is not None else []
    if isinstance(instr, ir.Branch):
        return []
    raise AssertionError(f"DCE: unhandled instruction {type(instr).__name__}")


def _remove_unreachable_blocks(func: ir.Function) -> bool:
    func.link_preds_succs()
    reachable = set()
    stack = [func.entry]
    while stack:
        block = stack.pop()
        if block.label in reachable:
            continue
        reachable.add(block.label)
        stack.extend(block.succs)

    dead_labels = [label for label in func.blocks if label not in reachable]
    for label in dead_labels:
        del func.blocks[label]
    if dead_labels:
        func.link_preds_succs()
    return bool(dead_labels)


def _collect_used_names(func: ir.Function) -> set:
    used = set()
    for block in func.blocks.values():
        for instr in block.instructions:
            for operand in _operands_read_by(instr):
                if isinstance(operand, (ir.Var, ir.Temp)):
                    used.add(operand.name)
        if block.terminator is not None:
            for operand in _operands_read_by(block.terminator):
                if isinstance(operand, (ir.Var, ir.Temp)):
                    used.add(operand.name)
    return used


def _remove_dead_instructions(func: ir.Function) -> bool:
    used = _collect_used_names(func)
    changed = False
    for block in func.blocks.values():
        kept = []
        for instr in block.instructions:
            dest = dest_of(instr)
            if dest is not None and dest.name not in used:
                changed = True
                continue
            kept.append(instr)
        if len(kept) != len(block.instructions):
            block.instructions = kept
    return changed


def run(module: ir.Module) -> bool:
    """Removing one dead instruction can make another instruction dead in
    turn (e.g. `x = a + b;` where `x` is unused makes the `a + b` BinOp
    unused too, but that's only visible once the Copy that used it is
    gone) - so this iterates to a fixed point on its own rather than
    relying on the outer pass-manager loop, matching what a user running
    `--passes=dce` alone would expect."""
    changed_overall = False
    while True:
        changed = False
        for func in module.functions:
            changed |= _remove_unreachable_blocks(func)
            changed |= _remove_dead_instructions(func)
        if not changed:
            break
        changed_overall = True
    return changed_overall
