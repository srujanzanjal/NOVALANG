"""TAC -> LLVM IR codegen, plus JIT execution via llvmlite's bundled MCJIT
engine (no external clang/llc/lld — decisions.md #7 addendum).

Every Var and Temp gets a stack slot (alloca'd once in the function's
entry block) rather than being treated as an SSA register. This isn't
just simplicity: short-circuit && / || codegen (ir_gen.py) reassigns a
shared temp across two different blocks before its only use in a third,
so a plain SSA register would be wrong there without real phi nodes
(which decisions.md #9 deliberately avoids) — alloca+load/store sidesteps
that entirely, at the cost of the generated IR being less optimal than
hand-tuned LLVM IR (irrelevant here: this project's own optimizer passes
already ran at the TAC level in Phase 5, and re-optimizing the generated
LLVM IR itself is out of scope).

print() is implemented as calls to host callback functions backed by
Python's own print(), registered into the JIT via llvm.add_symbol(),
rather than linking against libc's printf directly. This was a deliberate
change after hitting real Windows-specific trouble: modern Python links
the Universal CRT, whose printf isn't resolvable under that name via
ctypes from the api-ms-win-crt-*.dll forwarders, and even the legacy
msvcrt.dll's printf (which DOES resolve) turned out to buffer into a
separate CRT instance's stdio state that pytest's capfd never observes.
Routing print() through a Python callback sidesteps CRT-linking quirks
entirely and is a standard technique for a JIT'd toy language's I/O.
"""

import ctypes

import llvmlite.binding as llvm
import llvmlite.ir as lir

from . import ir as tac

INT_TYPE = lir.IntType(32)
FLOAT_TYPE = lir.DoubleType()
BOOL_TYPE = lir.IntType(1)
STRING_PTR_TYPE = lir.PointerType(lir.IntType(8))

# name -> (ctypes callback signature, llvm declared param type)
_PRINT_CALLBACKS = {
    "novac_print_int": (ctypes.CFUNCTYPE(None, ctypes.c_int32), INT_TYPE),
    "novac_print_float": (ctypes.CFUNCTYPE(None, ctypes.c_double), FLOAT_TYPE),
    "novac_print_bool": (ctypes.CFUNCTYPE(None, ctypes.c_int32), INT_TYPE),  # i1 widened to i32 for a clean C ABI
    "novac_print_string": (ctypes.CFUNCTYPE(None, ctypes.c_char_p), STRING_PTR_TYPE),
}


def _llvm_type(type_) -> lir.Type:
    base = {"int": INT_TYPE, "float": FLOAT_TYPE, "bool": BOOL_TYPE}[type_.base]
    return lir.ArrayType(base, type_.array_size) if type_.is_array() else base


class CodeGenerator:
    def __init__(self):
        self.llvm_module = lir.Module(name="novalang")
        self.llvm_funcs = {}
        self.print_funcs = {}
        self.string_cache = {}
        self.slots = {}
        self.llvm_blocks = {}
        self.current_locals = {}

    def generate(self, module: tac.Module) -> lir.Module:
        for name, (_, param_type) in _PRINT_CALLBACKS.items():
            fn_type = lir.FunctionType(lir.VoidType(), [param_type])
            self.print_funcs[name] = lir.Function(self.llvm_module, fn_type, name=name)

        # two-pass, matching the codegen decision for recursion/forward
        # references (decisions.md #5): declare every signature first, so
        # any Call can resolve regardless of definition order.
        for func in module.functions:
            self._declare_function(func)
        for func in module.functions:
            self._define_function(func)

        return self.llvm_module

    def _declare_function(self, func: tac.Function):
        param_types = [_llvm_type(t) for _, t in func.params]
        fn_type = lir.FunctionType(_llvm_type(func.return_type), param_types)
        self.llvm_funcs[func.name] = lir.Function(self.llvm_module, fn_type, name=func.name)

    def _define_function(self, func: tac.Function):
        llvm_func = self.llvm_funcs[func.name]
        self.slots = {}
        self.current_locals = func.locals

        alloca_block = llvm_func.append_basic_block(name="entry.alloca")
        alloca_builder = lir.IRBuilder(alloca_block)
        for name, type_ in func.locals.items():
            self.slots[name] = alloca_builder.alloca(_llvm_type(type_), name=name)

        for (param_name, _), llvm_arg in zip(func.params, llvm_func.args):
            alloca_builder.store(llvm_arg, self.slots[param_name])

        self.llvm_blocks = {label: llvm_func.append_basic_block(name=label) for label in func.blocks}
        alloca_builder.branch(self.llvm_blocks[func.entry.label])

        for label, block in func.blocks.items():
            self._gen_block(block, self.llvm_blocks[label])

    def _gen_block(self, block: tac.BasicBlock, llvm_block):
        builder = lir.IRBuilder(llvm_block)
        for instr in block.instructions:
            self._gen_instr(instr, builder)
        self._gen_terminator(block.terminator, builder)

    # -- operand helpers --

    def _type_of(self, operand) -> str:
        if isinstance(operand, tac.Const):
            return operand.type
        return self.current_locals[operand.name].base

    def _value_of(self, operand, builder):
        if isinstance(operand, tac.Const):
            if operand.type == "int":
                return lir.Constant(INT_TYPE, operand.value)
            if operand.type == "float":
                return lir.Constant(FLOAT_TYPE, operand.value)
            if operand.type == "bool":
                return lir.Constant(BOOL_TYPE, int(operand.value))
            if operand.type == "string":
                return self._get_string_ptr(operand.value, builder)
            raise AssertionError(f"codegen: unhandled const type {operand.type!r}")
        return builder.load(self.slots[operand.name])

    def _store(self, name, value, builder):
        builder.store(value, self.slots[name])

    def _get_string_ptr(self, text: str, builder):
        if text not in self.string_cache:
            data = bytearray((text + "\0").encode("utf8"))
            arr_type = lir.ArrayType(lir.IntType(8), len(data))
            global_var = lir.GlobalVariable(self.llvm_module, arr_type, name=f".str.{len(self.string_cache)}")
            global_var.linkage = "internal"
            global_var.global_constant = True
            global_var.unnamed_addr = True
            global_var.initializer = lir.Constant(arr_type, data)
            self.string_cache[text] = global_var
        return builder.bitcast(self.string_cache[text], STRING_PTR_TYPE)

    # -- instructions --

    def _gen_instr(self, instr, builder):
        if isinstance(instr, tac.BinOp):
            self._gen_binop(instr, builder)
        elif isinstance(instr, tac.UnaryOp):
            self._gen_unaryop(instr, builder)
        elif isinstance(instr, tac.Copy):
            self._store(instr.dest.name, self._value_of(instr.src, builder), builder)
        elif isinstance(instr, tac.ArrayLoad):
            self._gen_array_load(instr, builder)
        elif isinstance(instr, tac.ArrayStore):
            self._gen_array_store(instr, builder)
        elif isinstance(instr, tac.Call):
            self._gen_call(instr, builder)
        elif isinstance(instr, tac.Print):
            self._gen_print(instr, builder)
        else:
            raise AssertionError(f"codegen: unhandled instruction {type(instr).__name__}")

    def _gen_binop(self, instr, builder):
        left = self._value_of(instr.left, builder)
        right = self._value_of(instr.right, builder)
        t = self._type_of(instr.left)
        op = instr.op

        if t == "int":
            table = {
                "+": builder.add, "-": builder.sub, "*": builder.mul,
                "/": builder.sdiv, "%": builder.srem,
            }
            result = table[op](left, right) if op in table else builder.icmp_signed(op, left, right)
        elif t == "float":
            table = {
                "+": builder.fadd, "-": builder.fsub, "*": builder.fmul,
                "/": builder.fdiv, "%": builder.frem,
            }
            result = table[op](left, right) if op in table else builder.fcmp_ordered(op, left, right)
        elif t == "bool":
            result = builder.icmp_signed(op, left, right)  # only ==/!= reach here; && / || are branches (ir_gen.py)
        else:
            raise AssertionError(f"codegen: unexpected BinOp operand type {t!r}")

        self._store(instr.dest.name, result, builder)

    def _gen_unaryop(self, instr, builder):
        operand = self._value_of(instr.operand, builder)
        t = self._type_of(instr.operand)
        if instr.op == "-":
            result = builder.sub(lir.Constant(INT_TYPE, 0), operand) if t == "int" \
                else builder.fsub(lir.Constant(FLOAT_TYPE, 0.0), operand)
        elif instr.op == "!":
            result = builder.xor(operand, lir.Constant(BOOL_TYPE, 1))
        else:
            raise AssertionError(f"codegen: unhandled unary operator {instr.op!r}")
        self._store(instr.dest.name, result, builder)

    def _gen_array_load(self, instr, builder):
        zero = lir.Constant(INT_TYPE, 0)
        index_val = self._value_of(instr.index, builder)
        elem_ptr = builder.gep(self.slots[instr.array.name], [zero, index_val], inbounds=True)
        self._store(instr.dest.name, builder.load(elem_ptr), builder)

    def _gen_array_store(self, instr, builder):
        zero = lir.Constant(INT_TYPE, 0)
        index_val = self._value_of(instr.index, builder)
        src_val = self._value_of(instr.src, builder)
        elem_ptr = builder.gep(self.slots[instr.array.name], [zero, index_val], inbounds=True)
        builder.store(src_val, elem_ptr)

    def _gen_call(self, instr, builder):
        args = [self._value_of(a, builder) for a in instr.args]
        result = builder.call(self.llvm_funcs[instr.func_name], args)
        if instr.dest is not None:
            self._store(instr.dest.name, result, builder)

    def _gen_print(self, instr, builder):
        t = self._type_of(instr.value)
        val = self._value_of(instr.value, builder)
        if t == "int":
            builder.call(self.print_funcs["novac_print_int"], [val])
        elif t == "float":
            builder.call(self.print_funcs["novac_print_float"], [val])
        elif t == "bool":
            widened = builder.zext(val, INT_TYPE)
            builder.call(self.print_funcs["novac_print_bool"], [widened])
        elif t == "string":
            builder.call(self.print_funcs["novac_print_string"], [val])
        else:
            raise AssertionError(f"codegen: cannot print type {t!r}")

    def _gen_terminator(self, term, builder):
        if isinstance(term, tac.Branch):
            builder.branch(self.llvm_blocks[term.target])
        elif isinstance(term, tac.CondBranch):
            cond = self._value_of(term.cond, builder)
            builder.cbranch(cond, self.llvm_blocks[term.true_target], self.llvm_blocks[term.false_target])
        elif isinstance(term, tac.Return):
            builder.ret(self._value_of(term.value, builder)) if term.value is not None else builder.ret_void()
        else:
            raise AssertionError(f"codegen: unhandled terminator {type(term).__name__}")


def generate_llvm_ir(module: tac.Module) -> lir.Module:
    return CodeGenerator().generate(module)


def _print_int(value):
    print(value)


def _print_float(value):
    print(f"{value:.6f}")


def _print_bool(value):
    print("true" if value else "false")


def _print_string(ptr):
    print(ptr.decode("utf8"))


_PRINT_IMPLS = {
    "novac_print_int": _print_int,
    "novac_print_float": _print_float,
    "novac_print_bool": _print_bool,
    "novac_print_string": _print_string,
}


class JITResult:
    """Holds the MCJIT engine and callback closures alive alongside the
    result — both must outlive any use of the JIT-compiled code."""

    def __init__(self, return_value, engine, callback_refs):
        self.return_value = return_value
        self.engine = engine
        self._callback_refs = callback_refs  # keeps ctypes callback trampolines from being GC'd


class CompiledProgram:
    """A JIT-compiled module with its entry function ready to invoke
    directly, as many times as needed, without repeating MCJIT setup.
    Separated from compile_and_run() so benchmarking can time only actual
    execution, not one-time JIT compilation overhead — bundling the two
    would mean a short program's "execution time" mostly measures MCJIT
    setup noise instead of real optimization impact."""

    def __init__(self, cfunc, engine, callback_refs):
        self.cfunc = cfunc
        self.engine = engine
        self._callback_refs = callback_refs

    def __call__(self) -> int:
        return self.cfunc()


def jit_compile(llvm_module: lir.Module, entry_function: str = "main") -> CompiledProgram:
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    callback_refs = []
    for name, (cfunctype, _) in _PRINT_CALLBACKS.items():
        callback = cfunctype(_PRINT_IMPLS[name])
        callback_refs.append(callback)
        llvm.add_symbol(name, ctypes.cast(callback, ctypes.c_void_p).value)

    parsed = llvm.parse_assembly(str(llvm_module))
    parsed.verify()

    target_machine = llvm.Target.from_default_triple().create_target_machine()
    engine = llvm.create_mcjit_compiler(parsed, target_machine)
    engine.finalize_object()

    func_ptr = engine.get_function_address(entry_function)
    cfunc = ctypes.CFUNCTYPE(ctypes.c_int32)(func_ptr)
    return CompiledProgram(cfunc, engine, callback_refs)


def compile_and_run(llvm_module: lir.Module, entry_function: str = "main") -> JITResult:
    program = jit_compile(llvm_module, entry_function)
    result = program()
    return JITResult(result, program.engine, program._callback_refs)
