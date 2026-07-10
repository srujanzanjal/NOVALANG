# Notes for Switching Development to macOS

This project started on a Windows machine with no admin rights and a
network that blocks external toolchain downloads (see `docs/decisions.md`
toolchain section) — so it currently runs on `llvmlite`'s bundled MCJIT
execution engine only, with no standalone executable output. This file
tracks what to do once development moves to a personal Mac with normal
install access, kept updated as the project progresses.

## 1. Get the real toolchain (the thing Windows blocked)

macOS makes this trivial and removes the biggest limitation we're working
around right now:

- `xcode-select --install` gets you `clang`, `ld`, and friends for free —
  no Homebrew required. This alone is enough to unlock standalone native
  executables.
- Optional, for an exact-version match with `llvmlite`'s embedded LLVM
  (22.1.x as of this doc): `brew install llvm@22`. Not required — see §3.

## 2. Re-run the environment setup

```
git clone <this repo>          # or just copy the folder over
cd novalang
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify the `llvmlite` wheel installs cleanly for your Python version + Mac
chip (Apple Silicon vs Intel both have wheels as of 0.48.0, but re-check
`pip index versions llvmlite` if this doc is stale). Then re-run the
toolchain smoke test:

```
pytest tests/test_toolchain_smoke.py -v
```

## 3. Recommended Phase 6 codegen approach (unlocks standalone executables)

Don't make Phase 6 depend on shelling out to external `clang` to *parse*
our generated `.ll` text — that reintroduces an LLVM-version-matching
problem (our `.ll` is produced by whatever LLVM `llvmlite` embeds; the
Mac's system/Homebrew clang may embed a different one). Instead:

1. Keep using `llvmlite`'s own `TargetMachine.emit_object()` to compile our
   IR directly to a native `.o` object file — this uses the *same* embedded
   LLVM that generated the IR, so there's no version mismatch, ever.
2. Shell out to the system `clang` (or `cc`/`ld`) **only as a linker**:
   `clang out.o -o out`. Linking a `.o` file has much looser compatibility
   requirements than parsing `.ll` text across LLVM versions, so this is
   the robust path.

This means the CLI's `-o` flag becomes: generate `.ll` (for `--dump-stage`
and debugging) → `emit_object()` → invoke system linker → done. The JIT
path (current default) and the compile-to-binary path can coexist —
`--run` uses MCJIT, `-o <path>` uses emit_object + link.

## 4. Things that differ from the Windows dev environment

- **Target triple** changes: Apple Silicon is `arm64-apple-darwin`, Intel
  Macs are `x86_64-apple-darwin` (Windows was `x86_64-pc-windows-msvc`).
  `llvmlite.binding.Target.from_default_triple()` picks this up
  automatically — don't hardcode the Windows triple anywhere.
- No `.exe` extension on output binaries; Mach-O executables just need the
  executable bit (`chmod +x`, though the linker sets this already).
- First run of a freshly linked local binary is generally fine without
  Gatekeeper friction (that mainly affects downloaded/quarantined files,
  not ones you compiled locally) — but if macOS ever refuses to run it,
  `xattr -d com.apple.quarantine <path>` is the fix.
- Git line endings: this repo was authored on Windows without
  `core.autocrlf` configured. If Mac git starts flagging whole-file diffs
  from CRLF/LF churn, add a `.gitattributes` with `* text=auto` rather than
  fighting it file-by-file.

## 5. What this unlocks for the project deliverables

Once §1–3 are done, the stretch goal from `docs/decisions.md` (standalone
`novac prog.nova -o prog` producing a real executable, not just JIT
execution) becomes straightforward — worth doing before the final demo/
report, since "produces a real native binary" is one of the project's
stated differentiators.

## Log

- *(entry date TBD)* — doc created while still on Windows, ahead of the
  actual migration; nothing below this line has been verified on real
  macOS hardware yet.
