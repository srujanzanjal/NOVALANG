from dataclasses import dataclass, field


@dataclass
class Type:
    base: str  # "int" | "float" | "bool" | "string"
    array_size: int | None = None  # None => scalar; else fixed-size array

    def is_array(self):
        return self.array_size is not None

    def __str__(self):
        return f"{self.base}[{self.array_size}]" if self.is_array() else self.base


# -- Expressions --

class Expr:
    line: int
    col: int


@dataclass
class IntLiteral(Expr):
    value: int
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class FloatLiteral(Expr):
    value: float
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class BoolLiteral(Expr):
    value: bool
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class StringLiteral(Expr):
    value: str
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class Identifier(Expr):
    name: str
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class ArrayLiteral(Expr):
    elements: list
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class ArrayIndex(Expr):
    array: Expr
    index: Expr
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class BinaryOp(Expr):
    op: str
    left: Expr
    right: Expr
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr
    line: int
    col: int
    type: "Type | None" = None


@dataclass
class Call(Expr):
    name: str
    args: list
    line: int
    col: int
    type: "Type | None" = None


# -- Statements --

class Stmt:
    line: int
    col: int


@dataclass
class VarDecl(Stmt):
    name: str
    type: Type
    init: Expr | None
    line: int
    col: int


@dataclass
class Assign(Stmt):
    target: Expr  # Identifier or ArrayIndex; validated as an lvalue in semantic analysis
    value: Expr
    line: int
    col: int


@dataclass
class If(Stmt):
    cond: Expr
    then_block: "Block"
    else_branch: "Block | If | None"
    line: int
    col: int


@dataclass
class While(Stmt):
    cond: Expr
    body: "Block"
    line: int
    col: int


@dataclass
class For(Stmt):
    init: Stmt | None
    cond: Expr
    update: Assign
    body: "Block"
    line: int
    col: int


@dataclass
class Return(Stmt):
    value: Expr | None
    line: int
    col: int


@dataclass
class ExprStmt(Stmt):
    expr: Expr
    line: int
    col: int


@dataclass
class Block(Stmt):
    statements: list
    line: int
    col: int


# -- Top level --

@dataclass
class Param:
    name: str
    type: Type
    line: int
    col: int


@dataclass
class Function:
    name: str
    params: list
    return_type: Type
    body: Block
    line: int
    col: int


@dataclass
class Program:
    functions: list = field(default_factory=list)
