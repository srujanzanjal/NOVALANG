# NovaLang Design Decisions Log

This document records architectural decisions made before implementation began,
along with the reasoning. These are written down explicitly so that (a) they
don't get re-litigated mid-implementation, and (b) they can be dropped
directly into the project report / defended in a viva as deliberate scope
choices rather than accidents.

## 1. IR structure: basic blocks + CFG from day one

**Decision:** The IR generator builds basic blocks and an explicit
control-flow graph (CFG) per function, not a flat list of TAC instructions.
Every `if`, `while`, and `for` construct introduces block boundaries the
moment the IR generator sees a branch. Each basic block ends in exactly one
terminator instruction (`br`, `br_cond`, or `ret`).

**Why:** Loop-invariant code motion (stretch goal) requires loop detection,
which requires a CFG (natural loops via back-edges). Building the CFG later
would mean re-deriving it from flat TAC. Since LLVM IR itself is
fundamentally block-based (`ir.Function` containing `ir.Block`s), building
our own CFG first makes Phase 6 codegen a near 1:1 structural mapping instead
of a re-derivation.

**Consequence:** DCE = unreachable-block elimination + per-block dead
instruction elimination. CSE is local (within a block) for v1; cross-block
CSE is a stretch goal requiring dominance information and is likely out of
scope.

## 2. String support: print-only literals

**Decision:** Strings may only appear as literal arguments to `print()`.
No string variables, no concatenation, no comparison, no indexing.

**Why:** General string semantics in LLVM IR require global constant arrays
and `getelementptr`-based addressing — a meaningfully larger scope than the
type-checking side of "supporting strings" suggests. Scoping this down
avoids an open-ended rabbit hole.

**Report line:** "Strings are supported as literal arguments to `print()`
only; general string semantics are out of scope for this project."

## 3. Array bounds checking: exactly one static case

**Decision:** A compile-time bounds error is raised **if and only if** both
the array size and the index are integer literals known at compile time, and
the index is outside `[0, size)`. All other index expressions (variables,
computed expressions) are unchecked and are a runtime concern outside this
project's scope. There are no runtime traps or panics.

**Why:** "Bounds checks where statically determinable" is otherwise
unbounded in scope. This is a single `if` in the type checker, triggered on
`ArrayAccess(arr, IntLiteral)`.

## 4. Type promotion: none, implicit

**Decision:** `int op float` is a compile-time type error. No implicit
casting in either direction. (Explicit cast syntax like `(float)x` may be
added later as a stretch goal.)

**Why:** Removes an entire class of "which direction does this promote, and
what does codegen do about it" decisions from both the semantic analyzer and
the code generator.

## 5. Recursion / forward declarations: two-pass codegen

**Decision:** Code generation happens in two passes over all top-level
functions:

1. **Pass 1 (declare):** walk every function AST, emit only the LLVM
   function *declaration* (name, parameter types, return type) into the
   module.
2. **Pass 2 (define):** walk every function AST again, emitting the actual
   body. Any `call` instruction resolves against a signature already present
   in the module, regardless of source order.

**Why:** This is what makes self-recursion (`factorial`) and mutual
recursion (`isEven`/`isOdd`-style) work without requiring the source to
declare functions in dependency order.

## 6. Error recovery: hard cap

**Decision:** `MAX_ERRORS = 20`. A global counter increments on every
panic-mode synchronization in the parser (and equivalently for semantic
errors). When the cap is hit, the compiler prints `"Too many errors,
aborting compilation"` and exits — no unbounded thrashing on pathologically
broken input.

## 7. Toolchain pinning

**Decision:** `llvmlite==0.48.0` (embeds LLVM 22.1.0), pinned in
`requirements.txt`. LLVM toolchain (clang/llc/lld) installed via
`winget install --id LLVM.LLVM` for the final IR→object→executable step.

**Why:** llvmlite couples tightly to a specific embedded LLVM version;
resolving a version mismatch close to a demo is exactly the kind of
avoidable risk this log exists to prevent.

**Note (found during setup):** llvmlite 0.48.0 deprecated
`llvm.initialize()` — LLVM's internal setup is now automatic. Codegen
bootstrap only needs `initialize_native_target()` +
`initialize_native_asmprinter()` before requesting a `TargetMachine`.

**Update — no external clang/llc/lld on the primary dev machine:**
`winget install LLVM.LLVM` requires admin elevation that isn't available
here, and the LLVM NSIS installer's manifest hard-requires elevation
regardless of target install directory (confirmed: it fails identically
even targeting a user-writable folder). A portable alternative (Zig, which
bundles clang+lld with no installer) was also attempted, but the download
domain is blocked on this network.

**Resolution:** the primary execution path for this project is llvmlite's
own bundled MCJIT execution engine — LLVM IR is generated, JIT-compiled to
real native machine code, and executed in-process via
`llvm.create_mcjit_compiler(...)` + `ctypes`, with no external toolchain
dependency at all. Verified working end-to-end in `tests/test_toolchain_smoke.py`.
This still satisfies "produces actual running machine code, not an
interpreter" — MCJIT compiles to the same native instructions clang/llc
would produce, it just doesn't write a standalone `.exe` file to disk.

Standalone-executable output (`novac prog.nova -o prog.exe`) becomes a
**stretch goal**, gated on access to a machine with either admin rights or
an unblocked network for a portable toolchain. The CLI and benchmark suite
should be designed so this is a drop-in addition later (same LLVM IR text,
just handed to a different backend) rather than a redesign.

## 8. CLI optimization flags: allowlist, not just -O0/-O2

**Decision:** `--passes=const-fold,const-prop,dce,cse` (comma-separated
allowlist) is the primary interface. Convenience aliases:

- `-O0` → `--passes=` (empty)
- `-O1` → `--passes=const-fold,const-prop`
- `-O2` → `--passes=const-fold,const-prop,dce,cse`

**Why:** The project's benchmark story depends on being able to toggle each
optimization pass independently and measure its individual impact, not just
"optimized vs. not."

## 10. All-paths-return check (added during Phase 3, not in the original spec)

**Decision:** Semantic analysis rejects any function where control can
fall off the end without hitting a `return` on every path. Algorithm
(`_always_returns` in `novac/semantic.py`): a `Block` always-returns if any
statement in it always-returns (everything after that is already flagged
separately as unreachable code); an `if` always-returns only if it has an
`else` and **both** branches always-return; `while`/`for` are never assumed
to always-return (no static trip-count analysis) — a return has to follow
the loop.

**Why:** every NovaLang function has a concrete, non-void return type
(there is no `void`), and `docs/tac_spec.md` requires every basic block to
end in exactly one terminator instruction. A function that can fall off
its end would produce an LLVM block with no terminator, which fails
LLVM's verifier outright. This check exists to fail fast in Phase 3 with a
clear source-level message, instead of failing opaquely inside Phase 6
codegen.

## 11. Arrays are local-variable-only (no array params or return types)

**Decision:** A function's parameters and return type may never be an
array type. Arrays may only be declared as local variables within a
function body.

**Why:** the original spec never shows an array being passed to or
returned from a function, and allowing it opens a real semantic question
never asked for: are arrays passed by value (full copy) or by reference?
By-reference would need pointer/aliasing semantics (explicitly excluded
from this project's scope); by-value copying is a plausible but
unrequested feature. Found while designing CSE (Phase 5): CSE needs to
reason about whether a function call could mutate an array through an
aliased reference, and the answer is trivially "never" once arrays can't
cross function boundaries at all — closing this gap up front made the
optimizer's aliasing story simple instead of speculative.

## 12. Integer division/modulo: C-like truncating semantics, not Python's

**Decision:** `/` and `%` on `int` operands truncate toward zero (matching
C and LLVM's `sdiv`/`srem`), not Python's floor-based `//`/`%` (which
round toward negative infinity and can disagree with truncation when
operands have different signs, e.g. `-7 // 2 == -4` in Python vs. `-3` for
truncating division). `%` on `float` operands uses C's `fmod` semantics
(`math.fmod`), not Python's float `%`, for the same reason. Division by
zero is not statically checked (a runtime concern, out of scope like other
array-bounds cases) — constant folding simply declines to fold a division
whose divisor is a zero constant, leaving it to fail at runtime exactly as
unfolded code would.

**Why:** constant folding (Phase 5) evaluates arithmetic at compile time
in Python, but Phase 6 codegen emits LLVM's `sdiv`/`srem`/`fdiv`/`frem`
instructions, which execute at runtime with C truncation semantics. If the
two didn't match exactly, `-O2` output could silently compute a different
answer than `-O0` for negative operands — which would be a real
correctness bug hiding inside the project's own headline feature
(measurable, behavior-preserving optimization).

## 9a. Arrays: single dimension only

**Decision:** A type is a scalar (`int`/`float`/`bool`/`string`) optionally
followed by exactly one `[N]` — no `int[5][3]`-style multi-dimensional
arrays. The original spec's examples only ever show 1D fixed-size arrays;
the EBNF's naive recursive `type "[" N "]"` form would have silently
permitted more than that.

**Why:** consistent with the project's explicit "small language, deep
compiler" philosophy — multi-dimensional array indexing adds real
complexity to codegen (nested `getelementptr` computation) for a feature
never actually requested.

## 9. TAC representation: real Python classes, not strings

**Decision:** TAC instructions, basic blocks, and the CFG are modeled as
actual Python classes (`TACInstr` subclasses per opcode, `BasicBlock`, `CFG`)
from the start — never formatted into strings and re-parsed.

**Why:** Optimizer passes pattern-match on instruction type/fields. String-
based IR that gets re-parsed is a common self-inflicted mess in student
compiler projects and makes every pass harder to write and debug than it
needs to be.
