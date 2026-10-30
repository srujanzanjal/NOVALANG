"""FastAPI backend for the NovaLang playground.

Drives the real novac pipeline (novac/cli.py's stage order, mirrored here)
directly in-process — no subprocess, no shelling out to `python -m novac` —
so a single request returns every stage's output at once instead of one
dump-stage per invocation.
"""

import contextlib
import io
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from novac.cli import _dump_tac, _format_ast, _OPT_ALIASES
from novac.codegen import compile_and_run, generate_llvm_ir
from novac.ir_gen import IRGenerator
from novac.lexer import Lexer
from novac.optimizer import PASS_REGISTRY, run_passes
from novac.parser import Parser
from novac.semantic import SemanticAnalyzer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"

app = FastAPI(title="NovaLang Playground API")

app.add_middleware(
    CORSMiddleware,
    # Vite falls back to 5174/5175/... whenever 5173 is already taken by
    # another project's dev server, so match any localhost port rather than
    # hardcoding one.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompileRequest(BaseModel):
    source: str
    opt_level: str | None = None  # "O0" | "O1" | "O2"
    passes: list[str] | None = None
    run: bool = False


def _resolve_passes(opt_level, passes):
    if passes is not None:
        unknown = set(passes) - set(PASS_REGISTRY)
        if unknown:
            raise ValueError(f"unknown optimization pass(es): {sorted(unknown)}")
        return passes
    if opt_level is not None:
        return _OPT_ALIASES[opt_level]
    return []


def _token_dict(tok):
    return {
        "type": tok.type.name,
        "lexeme": tok.lexeme,
        "value": tok.value,
        "line": tok.line,
        "col": tok.col,
    }


@app.get("/api/examples")
def list_examples():
    examples = []
    for path in sorted(EXAMPLES_DIR.glob("*.nova")):
        examples.append({"id": path.stem, "name": path.stem, "source": path.read_text(), "category": "valid"})
    for path in sorted((EXAMPLES_DIR / "errors").glob("*.nova")):
        examples.append({"id": f"errors/{path.stem}", "name": path.stem, "source": path.read_text(), "category": "error"})
    return examples


@app.post("/api/compile")
def compile_source(req: CompileRequest):
    result = {
        "stage": "lexer",
        "tokens": None,
        "ast": None,
        "tac": None,
        "optimizedTac": None,
        "llvmIr": None,
        "output": None,
        "returnValue": None,
        "errors": [],
    }

    lexer = Lexer(req.source)
    tokens = lexer.tokenize()
    result["tokens"] = [_token_dict(t) for t in tokens]
    if lexer.errors:
        result["errors"] = [{"stage": "lexer", "message": str(e)} for e in lexer.errors]
        return result

    parser = Parser(tokens)
    program = parser.parse_program()
    result["stage"] = "parser"
    result["ast"] = _format_ast(program)
    if parser.errors:
        result["errors"] = [{"stage": "parser", "message": str(e)} for e in parser.errors]
        return result

    sem_errors = SemanticAnalyzer().analyze(program)
    result["stage"] = "semantic"
    if sem_errors:
        result["errors"] = [{"stage": "semantic", "message": str(e)} for e in sem_errors]
        return result

    tac_module = IRGenerator().generate(program)
    result["stage"] = "ir"
    tac_buf = io.StringIO()
    _dump_tac(tac_module, tac_buf)
    result["tac"] = tac_buf.getvalue()

    try:
        passes = _resolve_passes(req.opt_level, req.passes)
    except ValueError as e:
        result["errors"] = [{"stage": "optimizer", "message": str(e)}]
        return result

    if passes:
        run_passes(tac_module, passes)
    result["stage"] = "optimizer"
    opt_buf = io.StringIO()
    _dump_tac(tac_module, opt_buf)
    result["optimizedTac"] = opt_buf.getvalue()

    llvm_module = generate_llvm_ir(tac_module)
    result["stage"] = "codegen"
    result["llvmIr"] = str(llvm_module)

    if req.run:
        if "main" not in {f.name for f in tac_module.functions}:
            result["errors"] = [{"stage": "run", "message": "--run requires a 'main() -> int' function"}]
            return result
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            jit_result = compile_and_run(llvm_module, "main")
        result["stage"] = "run"
        result["output"] = stdout_buf.getvalue()
        result["returnValue"] = jit_result.return_value

    return result
