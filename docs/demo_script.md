# Live Demo Script

A walkthrough for a viva/live demo, in order. Every command is meant to be
run from the project root with the venv active. Each section has the
exact command, what it should show, and what to say about it.

Before the demo: run `.venv\Scripts\activate` (or
`source .venv/bin/activate` on macOS/Linux) once, then everything below
is `python -m novac ...`.

---

## 1. A successful compile and run

```
python -m novac examples/factorial.nova --run
```

**Expect:**
```
3628800
15
```

**Say:** "This is the language spec's own running example — recursive
factorial, a fixed-size array, a `for` loop, and `print()`. `factorial(10)
= 3628800`, and the array sum `1+2+3+4+5 = 15`. This isn't an
AST-walking interpreter — the source went through lexing, parsing,
semantic analysis, IR generation, and LLVM code generation, and this
output came from LLVM's JIT executing real compiled native instructions."

---

## 2. Full pipeline visibility — one program, every stage

```
python -m novac examples/factorial.nova --dump-stage=tokens
python -m novac examples/factorial.nova --dump-stage=ast
python -m novac examples/factorial.nova --dump-stage=tac
python -m novac examples/factorial.nova --dump-stage=llvm-ir
```

**Say:** "`--dump-stage` prints any point in the pipeline instead of
running further — tokens, the AST as an indented tree, three-address code
grouped into basic blocks, or the final LLVM IR. This is the same source
file at every stage, so you can see exactly what each phase does to it."

Worth pointing at specifically in the TAC dump: block labels like
`if.then.0` / `if.else.1` — "the IR generator builds real basic blocks
and a control-flow graph, not just a flat instruction list, from the
start — that's what makes the optimizer's dead-block elimination and the
LLVM codegen phase both straightforward instead of needing extra
analysis passes later."

---

## 3. Error recovery — multiple independent errors in one pass

```
python -m novac examples/errors/multiple_errors.nova
```

**Expect:**
```
error: 6:18: expected an expression, got SEMICOLON ';'
error: 10:12: expected an expression, got PLUS '+'
```

**Say:** "This file has three functions, two of them broken in
unrelated ways — a missing expression after `=`, and a missing expression
after `+`. Most student compilers abort on the first syntax error. This
one uses panic-mode recovery: on an error, it skips forward to the next
`;`/`}`/statement-start keyword and keeps parsing, so it finds *both*
mistakes in one compile run, the way GCC or Clang would."

Other error examples worth having ready if asked about a specific phase:

```
python -m novac examples/errors/unterminated_string.nova   # lexer error
python -m novac examples/errors/undeclared_variable.nova   # semantic error
python -m novac examples/errors/type_mismatch.nova         # int/float, no implicit conversion
python -m novac examples/errors/array_out_of_bounds.nova   # compile-time bounds check
```

---

## 4. Optimization: before vs. after, on the same program

**Instruction-count impact** (a program with no loop, so the story is
code size, not speed):

```
python -m novac benchmarks/programs/constant_showcase.nova --dump-stage=tac
python -m novac benchmarks/programs/constant_showcase.nova --dump-stage=optimized-tac
```

**Say:** "Before optimization, this is ~25 TAC instructions — a chain of
additions, multiplications, and several variables that are computed but
never used. After constant folding, constant propagation, dead-code
elimination, and common-subexpression elimination — `--dump-stage=
optimized-tac` runs all four passes by default — it collapses to a single
instruction: everything was foldable at compile time, and everything
except the one printed value was dead."

**Runtime impact** (a program with a hot loop, so the compile-time fix
pays off on every iteration):

```
python benchmarks/run_benchmarks.py
```

**Expect** (approximate — exact numbers vary by machine):
```
Benchmark              Instr Before Instr After  Reduction  Time Before (ms)  Time After (ms)  Speedup
------------------------------------------------------------------------------------------------------
array_sum_repeated               32          32       0.0%             13.21            11.81    1.12x
constant_showcase                25           1      96.0%              0.00             0.00    1.17x
fib_recursive                    11          11       0.0%              3.01             3.04    0.99x
loop_redundant                   22          18      18.2%             12.62             8.60    1.47x
```

**Say — and this is the honest part, not a sales pitch:** "`loop_redundant`
has a redundant computation inside a 2-million-iteration loop body. The
loop body is one basic block, analyzed *once* at compile time — so an 18%
reduction in that block's instructions gets paid for once and collected 2
million times at runtime: a measured 1.47x speedup, not an estimate.
`fib_recursive` and `array_sum_repeated` show essentially no improvement —
correctly: recursive Fibonacci has no foldable constants or redundant
work for these passes to find, since every operand is a runtime value.
Optimization only helps where the source program actually gives the
optimizer something to work with, and this benchmark suite reports that
honestly instead of only showing the flattering case."

If asked to see the chart: `benchmarks/results/benchmark_chart.png`.

---

## 5. If asked to prove behavior-preservation specifically

```
python -m novac benchmarks/programs/loop_redundant.nova --run    # -O0 (default)
python -m novac benchmarks/programs/loop_redundant.nova -O2 --run
```

**Say:** "Same exit code either way — optimization changed *how much
work* the program does, never *what it computes*. This is also a
permanent automated test (`test_optimized_and_unoptimized_produce_
identical_results` in `tests/test_codegen.py`), not just something that
happens to look right in this one demo run."

---

## 6. Anticipated questions

- **"Why no standalone .exe?"** — Development happened on a machine with
  no admin rights and a network that blocks the portable toolchain
  alternative (Zig); `docs/decisions.md` §7 has the full story, including
  that the LLVM installer's manifest hard-requires elevation regardless
  of install directory. `llvmlite`'s own MCJIT engine JIT-compiles to
  real native machine code and executes it in-process instead — same
  claim ("real machine code, not an interpreter"), no `.exe` file
  written to disk. `docs/mac_migration.md` is a ready checklist for
  unlocking standalone output on a machine with normal install access.
- **"What's the hardest bug you hit?"** — Three good answers, all in
  `docs/decisions.md`: the lexer's missing-EOF-on-error-cap bug (found by
  a test, not by inspection), the semantic analyzer's unreachable-code
  gap for `if`/`else` where both branches return (found by reasoning
  about what Phase 4 needed, before it became a bug), and the DCE pass
  needing to converge to its own fixed point internally rather than
  relying on the outer pass loop.
- **"Why not SSA?"** — Deliberate simplicity trade-off (decisions.md #9):
  named vars and temps are plain reassignable operands, at the cost of
  needing every var/temp to get a real stack slot in codegen rather than
  an SSA register — directly necessary because short-circuit `&&`/`||`
  codegen reassigns a shared temp across two different blocks.
- **"Why does print() not just call printf?"** — decisions.md #13: it
  did, until a real Windows CRT-linking problem surfaced during testing.
  Good story for "I found a real bug, understood why, and fixed the
  design rather than working around it."
