"""TAC / CFG data model — implements docs/tac_spec.md as real Python
classes (decisions.md #9), not strings. Not SSA: named variables and
temporaries are plain reassignable operands (decisions.md philosophy of
keeping IR generation simple; see tac_spec.md header)."""

from dataclasses import dataclass, field


# -- operands --

@dataclass(frozen=True)
class Temp:
    name: str

    def __str__(self):
        return self.name


@dataclass(frozen=True)
class Var:
    name: str

    def __str__(self):
        return self.name


@dataclass(frozen=True)
class Const:
    value: object
    type: str  # "int" | "float" | "bool" | "string"

    def __str__(self):
        return repr(self.value) if self.type == "string" else str(self.value)


# -- value-producing instructions --

@dataclass
class BinOp:
    dest: Temp
    op: str
    left: object
    right: object

    def __str__(self):
        return f"{self.dest} = {self.left} {self.op} {self.right}"


@dataclass
class UnaryOp:
    dest: Temp
    op: str
    operand: object

    def __str__(self):
        return f"{self.dest} = {self.op}{self.operand}"


@dataclass
class Copy:
    dest: object
    src: object

    def __str__(self):
        return f"{self.dest} = {self.src}"


@dataclass
class ArrayLoad:
    dest: Temp
    array: Var
    index: object

    def __str__(self):
        return f"{self.dest} = {self.array}[{self.index}]"


@dataclass
class ArrayStore:
    array: Var
    index: object
    src: object

    def __str__(self):
        return f"{self.array}[{self.index}] = {self.src}"


@dataclass
class Call:
    dest: object  # Temp | None
    func_name: str
    args: list

    def __str__(self):
        args_str = ", ".join(str(a) for a in self.args)
        prefix = f"{self.dest} = " if self.dest is not None else ""
        return f"{prefix}call {self.func_name}({args_str})"


@dataclass
class Print:
    value: object

    def __str__(self):
        return f"print {self.value}"


# -- terminators --

@dataclass
class Branch:
    target: str

    def __str__(self):
        return f"br {self.target}"


@dataclass
class CondBranch:
    cond: object
    true_target: str
    false_target: str

    def __str__(self):
        return f"br {self.cond} {self.true_target} {self.false_target}"


@dataclass
class Return:
    value: object  # operand | None

    def __str__(self):
        return f"ret {self.value}" if self.value is not None else "ret"


TERMINATOR_TYPES = (Branch, CondBranch, Return)


class BasicBlock:
    def __init__(self, label: str):
        self.label = label
        self.instructions: list = []
        self.terminator = None
        self.preds: list["BasicBlock"] = []
        self.succs: list["BasicBlock"] = []

    def __repr__(self):
        return f"BasicBlock({self.label!r}, {len(self.instructions)} instrs)"


class Function:
    def __init__(self, name: str, params: list, return_type):
        self.name = name
        self.params = params  # list of (ir_var_name: str, Type)
        self.return_type = return_type
        self.entry: BasicBlock | None = None
        self.blocks: dict[str, BasicBlock] = {}
        self.locals: dict[str, object] = {}  # ir_var_name -> Type, includes params

    def add_block(self, block: BasicBlock):
        self.blocks[block.label] = block
        if self.entry is None:
            self.entry = block

    def link_preds_succs(self):
        """Derive preds/succs for every block from its terminator. Called
        once IR generation for the function is complete."""
        for block in self.blocks.values():
            block.succs = []
            block.preds = []
        for block in self.blocks.values():
            term = block.terminator
            if isinstance(term, Branch):
                targets = [term.target]
            elif isinstance(term, CondBranch):
                targets = [term.true_target, term.false_target]
            else:
                targets = []
            for target_label in targets:
                target = self.blocks.get(target_label)
                if target is not None:
                    block.succs.append(target)
                    target.preds.append(block)


@dataclass
class Module:
    functions: list = field(default_factory=list)
