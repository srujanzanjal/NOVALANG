# NovaLang TAC / CFG Specification

This defines the intermediate representation used between Phase 4 (IR
generation) and Phase 6 (LLVM codegen). It is implemented as real Python
classes in `novac/ir.py` (see decisions.md #9) — this document is the spec
those classes must satisfy, written before implementation so optimizer
passes (Phase 5) have a stable target to pattern-match against.

Not SSA. Named variables and compiler-generated temporaries are both valid
operands and may be reassigned in place — this keeps Phase 4 simple. This is
an explicit scope decision, not an oversight; SSA construction (phi nodes,
dominance frontiers) is real complexity we are deliberately not taking on.

## Operands

| Kind | Example | Notes |
|---|---|---|
| `Temp(name)` | `t1`, `t2` | compiler-generated, unique per function |
| `Var(name)` | `n`, `sum` | source-level variable |
| `Const(value, type)` | `Const(5, INT)` | compile-time literal |

## Instructions

Every instruction is a small dataclass with a fixed set of fields. Grouped
by role:

**Value-producing (non-terminator):**

| Class | Fields | Meaning |
|---|---|---|
| `BinOp` | `dest, op, left, right` | `dest = left op right`; op ∈ `+ - * / % < <= > >= == != && \|\|` |
| `UnaryOp` | `dest, op, operand` | `dest = op operand`; op ∈ `- !` |
| `Copy` | `dest, src` | `dest = src` (used by const propagation to leave a trivial assignment before DCE removes it) |
| `ArrayLoad` | `dest, array, index` | `dest = array[index]` |
| `ArrayStore` | `array, index, src` | `array[index] = src` |
| `Call` | `dest_or_None, func_name, args` | `dest = call func_name(args)`; `dest` is `None` for void-context calls |
| `Print` | `value` | built-in `print(value)` |

**Terminators (exactly one per block, always the last instruction):**

| Class | Fields | Meaning |
|---|---|---|
| `Branch` | `target: str` | unconditional jump to block label |
| `CondBranch` | `cond, true_target: str, false_target: str` | conditional jump |
| `Return` | `value_or_None` | function return |

A block missing a terminator, or containing a terminator anywhere but the
last position, is an internal compiler error — this invariant is checked
when a block is sealed by the IR generator.

## BasicBlock

```
BasicBlock:
    label: str                  # unique within the function, e.g. "L3", "if.then", "loop.cond"
    instructions: list[Instr]   # non-terminator instructions, in order
    terminator: Instr           # exactly one of Branch / CondBranch / Return
    preds: list[BasicBlock]     # filled in when the CFG is assembled
    succs: list[BasicBlock]     # derived from the terminator
```

## CFG / Function

```
Function:
    name: str
    params: list[(name: str, type: Type)]
    return_type: Type
    entry: BasicBlock
    blocks: dict[str, BasicBlock]   # all blocks, including entry
```

`succs` is always derivable from a block's terminator (`Branch` → one
successor, `CondBranch` → two, `Return` → zero / exit). `preds` is the
reverse edge set, computed once after the whole function body is generated.

## Block boundaries: when the IR generator starts a new block

- Function entry → `entry` block.
- `if`/`else` → `then` block, optional `else` block, `merge` block (join point).
- `while` → `cond` block (loop test, re-entered every iteration), `body`
  block, `after` block.
- `for` → same shape as `while`, with the init clause emitted into the
  preheader (the block before `cond`) and the increment clause emitted at
  the end of `body`, before the jump back to `cond`.
- Short-circuit `&&` / `||` also introduce blocks (evaluate left operand,
  branch around the right operand) — do **not** lower these to a plain
  `BinOp`, since that would evaluate both sides unconditionally and break
  short-circuit semantics.

## What this buys each later phase

- **Phase 5 (DCE):** unreachable-block elimination = blocks with no `preds`
  and not the entry block, removed transitively. Dead instruction
  elimination = per-block backward scan removing instructions whose `dest`
  is never used before being redefined or the block ends.
- **Phase 5 (CSE):** local only for v1 — within one block's instruction
  list, no cross-block value numbering (see decisions.md #1).
- **Phase 6 (codegen):** `Function.blocks` maps almost directly onto
  `ir.Function` + one `ir.IRBuilder` block per `BasicBlock`; `preds`/`succs`
  give you the LLVM `br` targets for free.
