"""novac — the NovaLang compiler CLI.

    python -m novac examples/factorial.nova --run
    python -m novac examples/factorial.nova --dump-stage=tac
    python -m novac examples/factorial.nova -O2 --dump-stage=optimized-tac
    python -m novac examples/factorial.nova --passes=const-fold,dce --run

Default optimization level is -O0 (no passes), matching standard compiler
convention — --dump-stage=optimized-tac is the one exception: with no
explicit -O/--passes given, it defaults to -O2 so "show me before vs
after" works without the user having to remember a second flag.
"""

import argparse
import dataclasses
import sys

from . import ir as tac_ir
from .codegen import compile_and_run, generate_llvm_ir
from .ir_gen import IRGenerator
from .lexer import Lexer
from .optimizer import PASS_REGISTRY, run_passes
from .parser import Parser
from .semantic import SemanticAnalyzer

_OPT_ALIASES = {
    "O0": [],
    "O1": ["const-fold", "const-prop"],
    "O2": ["const-fold", "const-prop", "dce", "cse"],
}

_NOISY_AST_FIELDS = {"line", "col", "type"}


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novac", description="NovaLang compiler")
    parser.add_argument("source", help="path to a .nova source file")
    parser.add_argument("--run", action="store_true", help="JIT-compile and execute the program")
    parser.add_argument(
        "--dump-stage",
        choices=["tokens", "ast", "tac", "optimized-tac", "llvm-ir"],
        help="print the given pipeline stage instead of running",
    )

    opt_group = parser.add_mutually_exclusive_group()
    opt_group.add_argument("-O0", dest="opt_level", action="store_const", const="O0")
    opt_group.add_argument("-O1", dest="opt_level", action="store_const", const="O1")
    opt_group.add_argument("-O2", dest="opt_level", action="store_const", const="O2")
    opt_group.add_argument("--passes", help="comma-separated pass allowlist, e.g. const-fold,dce")
    return parser


def _resolve_passes(args, default=()):
    if args.passes is not None:
        names = [p.strip() for p in args.passes.split(",") if p.strip()]
        unknown = set(names) - set(PASS_REGISTRY)
        if unknown:
            raise ValueError(f"unknown optimization pass(es): {sorted(unknown)}")
        return names
    if args.opt_level is not None:
        return _OPT_ALIASES[args.opt_level]
    return list(default)


def _format_ast(node, indent=0) -> str:
    pad = "  " * indent
    if isinstance(node, list):
        return "\n".join(_format_ast(item, indent) for item in node) if node else f"{pad}[]"
    if dataclasses.is_dataclass(node):
        lines = [f"{pad}{type(node).__name__}"]
        for f in dataclasses.fields(node):
            if f.name in _NOISY_AST_FIELDS:
                continue
            value = getattr(node, f.name)
            if dataclasses.is_dataclass(value) or isinstance(value, list):
                lines.append(f"{pad}  {f.name}:")
                lines.append(_format_ast(value, indent + 2))
            else:
                lines.append(f"{pad}  {f.name}: {value!r}")
        return "\n".join(lines)
    return f"{pad}{node!r}"


def _dump_tac(module: tac_ir.Module, out):
    for func in module.functions:
        params = ", ".join(f"{name}: {t}" for name, t in func.params)
        out.write(f"func {func.name}({params}) -> {func.return_type}:\n")
        for label, block in func.blocks.items():
            out.write(f"  {label}:\n")
            for instr in block.instructions:
                out.write(f"    {instr}\n")
            out.write(f"    {block.terminator}\n")
        out.write("\n")


def main(argv=None, out=None, err=None) -> int:
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    args = _build_arg_parser().parse_args(argv)

    try:
        with open(args.source, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        err.write(f"error: cannot read '{args.source}': {e}\n")
        return 1

    lexer = Lexer(source)
    tokens = lexer.tokenize()
    if lexer.errors:
        for e in lexer.errors:
            err.write(f"error: {e}\n")
        return 1
    if args.dump_stage == "tokens":
        for tok in tokens:
            out.write(f"{tok}\n")
        return 0

    parser = Parser(tokens)
    program = parser.parse_program()
    if parser.errors:
        for e in parser.errors:
            err.write(f"error: {e}\n")
        return 1
    if args.dump_stage == "ast":
        out.write(_format_ast(program) + "\n")
        return 0

    sem_errors = SemanticAnalyzer().analyze(program)
    if sem_errors:
        for e in sem_errors:
            err.write(f"error: {e}\n")
        return 1

    tac_module = IRGenerator().generate(program)
    if args.dump_stage == "tac":
        _dump_tac(tac_module, out)
        return 0

    try:
        passes = _resolve_passes(args, default=_OPT_ALIASES["O2"] if args.dump_stage == "optimized-tac" else [])
    except ValueError as e:
        err.write(f"error: {e}\n")
        return 2
    if passes:
        run_passes(tac_module, passes)

    if args.dump_stage == "optimized-tac":
        _dump_tac(tac_module, out)
        return 0

    llvm_module = generate_llvm_ir(tac_module)
    if args.dump_stage == "llvm-ir":
        out.write(str(llvm_module) + "\n")
        return 0

    if args.run:
        if "main" not in {f.name for f in tac_module.functions}:
            err.write("error: --run requires a 'main() -> int' function\n")
            return 1
        result = compile_and_run(llvm_module, "main")
        return result.return_value

    out.write("compiled successfully (no errors). Pass --run to execute, or --dump-stage=... to inspect a stage.\n")
    return 0
