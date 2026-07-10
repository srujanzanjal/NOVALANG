from .. import ir


def dest_of(instr):
    """The value-producing instruction's destination operand, or None for
    instructions with no removable/substitutable result (Call/Print/
    ArrayStore/terminators)."""
    if isinstance(instr, (ir.BinOp, ir.UnaryOp, ir.Copy, ir.ArrayLoad)):
        return instr.dest
    return None
