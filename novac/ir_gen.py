from . import ast_nodes as ast
from . import ir


class Env:
    """Maps source-level variable names to unique IR-level names. A
    separate chain from semantic.py's Scope: this one exists to prevent
    shadowed variables (legal per semantic analysis) from colliding under
    the same flat, non-SSA TAC name within a function."""

    def __init__(self, parent=None):
        self.parent = parent
        self.bindings: dict[str, str] = {}

    def declare(self, name: str, ir_name: str):
        self.bindings[name] = ir_name

    def resolve(self, name: str) -> str:
        env = self
        while env is not None:
            if name in env.bindings:
                return env.bindings[name]
            env = env.parent
        raise KeyError(f"unresolved variable '{name}' (semantic analysis should have caught this)")


class IRGenerator:
    """Translates a semantically-valid, type-annotated AST into TAC with
    basic blocks and a CFG (tac_spec.md). Assumes the program has already
    passed semantic analysis with zero errors — it does not re-check types
    or re-validate control flow, only relies on those guarantees (e.g.
    'nothing follows a fully-terminating statement in a block')."""

    def __init__(self):
        self.temp_counter = 0
        self.label_counter = 0
        self.var_counter = 0
        self.func: ir.Function | None = None
        self.env: Env | None = None
        self.current: ir.BasicBlock | None = None

    def generate(self, program: ast.Program) -> ir.Module:
        module = ir.Module()
        for fn in program.functions:
            module.functions.append(self._gen_function(fn))
        return module

    # -- naming helpers --

    def _new_temp(self) -> ir.Temp:
        name = f"t{self.temp_counter}"
        self.temp_counter += 1
        return ir.Temp(name)

    def _new_label(self, hint: str) -> str:
        label = f"{hint}.{self.label_counter}"
        self.label_counter += 1
        return label

    def _declare_var(self, source_name: str, type_) -> ir.Var:
        ir_name = f"{source_name}.{self.var_counter}"
        self.var_counter += 1
        self.func.locals[ir_name] = type_
        self.env.declare(source_name, ir_name)
        return ir.Var(ir_name)

    def _resolve_var(self, source_name: str) -> ir.Var:
        return ir.Var(self.env.resolve(source_name))

    # -- block helpers --

    def _new_block(self, label: str) -> ir.BasicBlock:
        block = ir.BasicBlock(label)
        self.func.add_block(block)
        return block

    def _emit(self, instr):
        assert self.current is not None, "emit() with no live block (unreachable code reached codegen)"
        self.current.instructions.append(instr)

    def _terminate(self, instr):
        assert self.current is not None
        assert self.current.terminator is None
        self.current.terminator = instr

    # -- top level --

    def _gen_function(self, fn: ast.Function) -> ir.Function:
        self.temp_counter = 0
        self.label_counter = 0
        self.var_counter = 0
        self.func = ir.Function(fn.name, [], fn.return_type)
        self.env = Env()

        for p in fn.params:
            ir_var = self._declare_var(p.name, p.type)
            self.func.params.append((ir_var.name, p.type))

        entry = self._new_block("entry")
        self.current = entry
        self._gen_block(fn.body)

        assert self.current is None, (
            f"function '{fn.name}': fell through without a terminator "
            "(semantic analysis should have rejected this)"
        )
        self.func.link_preds_succs()
        return self.func

    # -- statements --

    def _gen_block(self, block: ast.Block):
        parent_env = self.env
        self.env = Env(parent_env)
        for stmt in block.statements:
            if self.current is None:
                break
            self._gen_stmt(stmt)
        self.env = parent_env

    def _gen_stmt(self, stmt: ast.Stmt):
        if isinstance(stmt, ast.VarDecl):
            self._gen_var_decl(stmt)
        elif isinstance(stmt, ast.Assign):
            self._gen_assign(stmt)
        elif isinstance(stmt, ast.If):
            self._gen_if(stmt)
        elif isinstance(stmt, ast.While):
            self._gen_while(stmt)
        elif isinstance(stmt, ast.For):
            self._gen_for(stmt)
        elif isinstance(stmt, ast.Return):
            self._gen_return(stmt)
        elif isinstance(stmt, ast.ExprStmt):
            self._gen_expr_stmt(stmt)
        elif isinstance(stmt, ast.Block):
            self._gen_block(stmt)
        else:
            raise AssertionError(f"unhandled statement node type: {type(stmt).__name__}")

    def _gen_var_decl(self, stmt: ast.VarDecl):
        if stmt.init is None:
            self._declare_var(stmt.name, stmt.type)
            return

        if stmt.type.is_array():
            element_vals = [self._gen_expr(el) for el in stmt.init.elements]
            var = self._declare_var(stmt.name, stmt.type)
            for i, val in enumerate(element_vals):
                self._emit(ir.ArrayStore(var, ir.Const(i, "int"), val))
        else:
            val = self._gen_expr(stmt.init)
            var = self._declare_var(stmt.name, stmt.type)
            self._emit(ir.Copy(var, val))

    def _gen_assign(self, stmt: ast.Assign):
        if isinstance(stmt.target, ast.Identifier):
            val = self._gen_expr(stmt.value)
            self._emit(ir.Copy(self._resolve_var(stmt.target.name), val))
        elif isinstance(stmt.target, ast.ArrayIndex):
            array_var = self._resolve_var(stmt.target.array.name)
            index_val = self._gen_expr(stmt.target.index)
            val = self._gen_expr(stmt.value)
            self._emit(ir.ArrayStore(array_var, index_val, val))
        else:
            raise AssertionError(f"unhandled assignment target: {type(stmt.target).__name__}")

    def _gen_if(self, stmt: ast.If):
        cond_val = self._gen_expr(stmt.cond)

        then_block = self._new_block(self._new_label("if.then"))
        else_block = self._new_block(self._new_label("if.else")) if stmt.else_branch is not None else None
        merge_label = self._new_label("if.merge")

        self._terminate(ir.CondBranch(
            cond_val, then_block.label, else_block.label if else_block else merge_label
        ))

        self.current = then_block
        self._gen_block(stmt.then_block)
        then_falls_through = self.current is not None
        if then_falls_through:
            self._terminate(ir.Branch(merge_label))

        else_falls_through = stmt.else_branch is None
        if stmt.else_branch is not None:
            self.current = else_block
            if isinstance(stmt.else_branch, ast.If):
                self._gen_if(stmt.else_branch)
            else:
                self._gen_block(stmt.else_branch)
            else_falls_through = self.current is not None
            if else_falls_through:
                self._terminate(ir.Branch(merge_label))

        if then_falls_through or else_falls_through:
            self.current = self._new_block(merge_label)
        else:
            self.current = None

    def _gen_while(self, stmt: ast.While):
        cond_label = self._new_label("while.cond")
        body_label = self._new_label("while.body")
        after_label = self._new_label("while.after")

        self._terminate(ir.Branch(cond_label))

        cond_block = self._new_block(cond_label)
        self.current = cond_block
        cond_val = self._gen_expr(stmt.cond)
        body_block = self._new_block(body_label)
        after_block = self._new_block(after_label)
        self._terminate(ir.CondBranch(cond_val, body_block.label, after_block.label))

        self.current = body_block
        self._gen_block(stmt.body)
        if self.current is not None:
            self._terminate(ir.Branch(cond_label))

        self.current = after_block

    def _gen_for(self, stmt: ast.For):
        parent_env = self.env
        self.env = Env(parent_env)

        if stmt.init is not None:
            self._gen_stmt(stmt.init)

        cond_label = self._new_label("for.cond")
        body_label = self._new_label("for.body")
        after_label = self._new_label("for.after")

        self._terminate(ir.Branch(cond_label))

        cond_block = self._new_block(cond_label)
        self.current = cond_block
        cond_val = self._gen_expr(stmt.cond)
        body_block = self._new_block(body_label)
        after_block = self._new_block(after_label)
        self._terminate(ir.CondBranch(cond_val, body_block.label, after_block.label))

        self.current = body_block
        self._gen_block(stmt.body)
        if self.current is not None:
            self._gen_stmt(stmt.update)
            self._terminate(ir.Branch(cond_label))

        self.current = after_block
        self.env = parent_env

    def _gen_return(self, stmt: ast.Return):
        val = self._gen_expr(stmt.value) if stmt.value is not None else None
        self._terminate(ir.Return(val))
        self.current = None

    def _gen_expr_stmt(self, stmt: ast.ExprStmt):
        if isinstance(stmt.expr, ast.Call) and stmt.expr.name == "print":
            arg_val = self._gen_expr(stmt.expr.args[0])
            self._emit(ir.Print(arg_val))
        else:
            self._gen_expr(stmt.expr)

    # -- expressions --

    def _gen_expr(self, expr: ast.Expr):
        if isinstance(expr, ast.IntLiteral):
            return ir.Const(expr.value, "int")
        if isinstance(expr, ast.FloatLiteral):
            return ir.Const(expr.value, "float")
        if isinstance(expr, ast.BoolLiteral):
            return ir.Const(expr.value, "bool")
        if isinstance(expr, ast.StringLiteral):
            return ir.Const(expr.value, "string")
        if isinstance(expr, ast.Identifier):
            return self._resolve_var(expr.name)
        if isinstance(expr, ast.ArrayIndex):
            array_var = self._resolve_var(expr.array.name)
            index_val = self._gen_expr(expr.index)
            dest = self._new_temp()
            self._emit(ir.ArrayLoad(dest, array_var, index_val))
            return dest
        if isinstance(expr, ast.UnaryOp):
            operand_val = self._gen_expr(expr.operand)
            dest = self._new_temp()
            self._emit(ir.UnaryOp(dest, expr.op, operand_val))
            return dest
        if isinstance(expr, ast.BinaryOp):
            return self._gen_binary_op(expr)
        if isinstance(expr, ast.Call):
            arg_vals = [self._gen_expr(a) for a in expr.args]
            dest = self._new_temp()
            self._emit(ir.Call(dest, expr.name, arg_vals))
            return dest
        raise AssertionError(f"unhandled expression node type: {type(expr).__name__}")

    def _gen_binary_op(self, expr: ast.BinaryOp):
        if expr.op == "&&":
            return self._gen_short_circuit(expr, short_circuit_on_true=False)
        if expr.op == "||":
            return self._gen_short_circuit(expr, short_circuit_on_true=True)

        left_val = self._gen_expr(expr.left)
        right_val = self._gen_expr(expr.right)
        dest = self._new_temp()
        self._emit(ir.BinOp(dest, expr.op, left_val, right_val))
        return dest

    def _gen_short_circuit(self, expr: ast.BinaryOp, short_circuit_on_true: bool):
        """&&: if left is false, result is left (false), rhs unevaluated.
        ||: if left is true, result is left (true), rhs unevaluated.
        Implemented via a shared temp reassigned along both incoming edges
        (no phi node needed — this IR is not SSA, decisions.md #9)."""
        dest = self._new_temp()
        left_val = self._gen_expr(expr.left)
        self._emit(ir.Copy(dest, left_val))

        rhs_block = self._new_block(self._new_label("shortcircuit.rhs"))
        merge_label = self._new_label("shortcircuit.merge")

        if short_circuit_on_true:
            self._terminate(ir.CondBranch(left_val, merge_label, rhs_block.label))
        else:
            self._terminate(ir.CondBranch(left_val, rhs_block.label, merge_label))

        self.current = rhs_block
        right_val = self._gen_expr(expr.right)
        self._emit(ir.Copy(dest, right_val))
        self._terminate(ir.Branch(merge_label))

        self.current = self._new_block(merge_label)
        return dest
