"""Benchmark suite measuring optimizer impact: TAC instruction count and
JIT execution time, before vs. after running every optimization pass, for
each program in benchmarks/programs/. Results are printed as a table and
written to benchmarks/results/results.json (consumed by
benchmarks/plot_results.py for the report chart).

Execution timing uses jit_compile() + repeated direct calls (not
compile_and_run()) specifically so it measures actual execution, not
one-time MCJIT setup overhead — see the commit that introduced
jit_compile() for why that distinction matters here.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novac.codegen import generate_llvm_ir, jit_compile
from novac.ir_gen import IRGenerator
from novac.lexer import Lexer
from novac.optimizer import PASS_REGISTRY, run_passes
from novac.parser import Parser
from novac.semantic import SemanticAnalyzer

BENCH_DIR = Path(__file__).parent / "programs"
RESULTS_DIR = Path(__file__).parent / "results"
TIMED_CALLS = 5  # per variant; the minimum of these is reported (standard best-of-N microbenchmark practice)


def count_instructions(tac_module) -> int:
    total = 0
    for func in tac_module.functions:
        for block in func.blocks.values():
            total += len(block.instructions) + (1 if block.terminator else 0)
    return total


def compile_to_tac(source):
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    errors = SemanticAnalyzer().analyze(program)
    if errors:
        raise AssertionError(f"unexpected semantic errors: {[str(e) for e in errors]}")
    return IRGenerator().generate(program)


def time_calls(compiled, n=TIMED_CALLS):
    times = []
    result = None
    for _ in range(n):
        start = time.perf_counter()
        result = compiled()
        times.append(time.perf_counter() - start)
    return min(times), result


def run_benchmark(name: str, source: str) -> dict:
    tac_unopt = compile_to_tac(source)
    instructions_before = count_instructions(tac_unopt)
    compiled_unopt = jit_compile(generate_llvm_ir(tac_unopt))
    time_before, return_unopt = time_calls(compiled_unopt)

    tac_opt = compile_to_tac(source)  # fresh TAC - passes mutate in place
    run_passes(tac_opt, list(PASS_REGISTRY))
    instructions_after = count_instructions(tac_opt)
    compiled_opt = jit_compile(generate_llvm_ir(tac_opt))
    time_after, return_opt = time_calls(compiled_opt)

    if return_unopt != return_opt:
        raise AssertionError(
            f"{name}: optimization changed program behavior! "
            f"unoptimized returned {return_unopt}, optimized returned {return_opt}"
        )

    return {
        "name": name,
        "instructions_before": instructions_before,
        "instructions_after": instructions_after,
        "instruction_reduction_pct": round(100 * (1 - instructions_after / instructions_before), 1),
        "time_before_ms": round(time_before * 1000, 4),
        "time_after_ms": round(time_after * 1000, 4),
        "speedup": round(time_before / time_after, 2) if time_after > 0 else None,
        "return_value": return_unopt,
    }


def print_table(results):
    cols = [
        ("Benchmark", "name", "<", 22),
        ("Instr Before", "instructions_before", ">", 12),
        ("Instr After", "instructions_after", ">", 11),
        ("Reduction", "instruction_reduction_pct", ">", 10),
        ("Time Before (ms)", "time_before_ms", ">", 17),
        ("Time After (ms)", "time_after_ms", ">", 16),
        ("Speedup", "speedup", ">", 8),
    ]
    header = " ".join(f"{title:{align}{width}}" for title, _, align, width in cols)
    print(header)
    print("-" * len(header))
    for r in results:
        cells = []
        for title, key, align, width in cols:
            value = r[key]
            if key == "instruction_reduction_pct":
                value = f"{value}%"
            elif key == "speedup":
                value = f"{value}x"
            cells.append(f"{value:{align}{width}}")
        print(" ".join(cells))


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    results = []
    for path in sorted(BENCH_DIR.glob("*.nova")):
        print(f"Running {path.stem}...", file=sys.stderr)
        results.append(run_benchmark(path.stem, path.read_text()))

    print()
    print_table(results)

    out_path = RESULTS_DIR / "results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
