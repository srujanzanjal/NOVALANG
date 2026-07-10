# NovaLang

A compiler for a small procedural language, NovaLang, through every classical
phase — lexing, parsing, semantic analysis, TAC IR generation, optimization,
and LLVM codegen — producing a real native executable.

## Status

The full pipeline (Phases 0-6) is implemented and tested: lexer, parser,
semantic analysis, TAC/CFG IR generation, four optimizer passes, and LLVM
codegen executed via `llvmlite`'s MCJIT. 129 tests passing. Remaining:
benchmark report, a larger `.nova` sample-program corpus, project report,
demo script. See `docs/decisions.md` for locked design decisions and
`docs/grammar.ebnf` / `docs/tac_spec.md` for the language and IR specs.

## Pipeline

```
.nova source
  -> Lexer          (novac/lexer.py)        -> tokens
  -> Parser         (novac/parser.py)       -> AST
  -> Semantic Analyzer (novac/semantic.py)  -> annotated AST + symbol table
  -> IR Generator   (novac/ir_gen.py)       -> TAC (basic blocks + CFG)
  -> Optimizer      (novac/optimizer/)      -> optimized TAC
  -> Code Generator (novac/codegen.py)      -> LLVM IR (.ll)
  -> llvmlite MCJIT                         -> in-process native execution
```

No external clang/llc/lld toolchain is required — see
`docs/decisions.md` (toolchain pinning section) for why: this dev
environment has no admin rights and a network that blocks the portable
alternative, so `llvmlite`'s bundled MCJIT engine is the primary execution
path. It JIT-compiles generated LLVM IR to real native machine code and
runs it in-process. A standalone `.exe` output mode is a stretch goal, see
the same doc.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Invoked as a Python module (no separate install step / console script):

```
python -m novac examples/factorial.nova --run
python -m novac examples/factorial.nova --dump-stage=tac
python -m novac examples/factorial.nova -O2 --dump-stage=optimized-tac
python -m novac examples/factorial.nova --passes=const-fold,dce --run
```

`--dump-stage` accepts `tokens`, `ast`, `tac`, `optimized-tac`, or
`llvm-ir`. Optimization defaults to `-O0` (no passes), except
`--dump-stage=optimized-tac` alone defaults to `-O2` so a before/after
comparison against plain `--dump-stage=tac` doesn't require a second flag.
`-O0`/`-O1`/`-O2` and `--passes=` are mutually exclusive.

## Layout

- `novac/` — compiler source
- `tests/` — pytest suite, one file per phase, `tests/fixtures/` for sample
  `.nova` programs
- `docs/` — grammar, IR spec, and the design decisions log
- `benchmarks/` — optimization-impact measurement suite and results
- `examples/` — sample NovaLang programs used in the demo script
