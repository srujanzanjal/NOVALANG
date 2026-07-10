"""
Validates the codegen execution path this project relies on: llvmlite
generates LLVM IR, which is JIT-compiled and executed in-process via
llvmlite's bundled MCJIT engine. No external clang/llc/lld is required or
assumed to be on PATH (see docs/decisions.md #7).
"""
import ctypes

import llvmlite.binding as llvm
import llvmlite.ir as ir


def test_jit_execution_returns_native_result():
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    module = ir.Module(name="smoke_test")
    func_ty = ir.FunctionType(ir.IntType(32), [])
    func = ir.Function(module, func_ty, name="main")
    block = func.append_basic_block(name="entry")
    builder = ir.IRBuilder(block)
    builder.ret(ir.Constant(ir.IntType(32), 42))

    llvm_mod = llvm.parse_assembly(str(module))
    llvm_mod.verify()

    target_machine = llvm.Target.from_default_triple().create_target_machine()
    with llvm.create_mcjit_compiler(llvm_mod, target_machine) as engine:
        engine.finalize_object()
        func_ptr = engine.get_function_address("main")
        cfunc = ctypes.CFUNCTYPE(ctypes.c_int32)(func_ptr)
        assert cfunc() == 42
