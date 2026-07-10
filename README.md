# NovaLang

A compiler for a small procedural language, NovaLang, through every classical
phase — lexing, parsing, semantic analysis, TAC IR generation, optimization,
and LLVM codegen — producing a real native executable.

## Status

Phase 0 (setup) in progress. See `docs/decisions.md` for locked design
decisions and `docs/grammar.ebnf` / `docs/tac_spec.md` for the language and
IR specifications that guide implementation.

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

## Usage (planned CLI)

```
novac examples/factorial.nova -O2 --run
novac examples/factorial.nova --dump-stage=tac
novac examples/factorial.nova --passes=const-fold,dce
```

## Layout

- `novac/` — compiler source
- `tests/` — pytest suite, one file per phase, `tests/fixtures/` for sample
  `.nova` programs
- `docs/` — grammar, IR spec, and the design decisions log
- `benchmarks/` — optimization-impact measurement suite and results
- `examples/` — sample NovaLang programs used in the demo script
