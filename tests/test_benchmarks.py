import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

import run_benchmarks  # noqa: E402


def test_count_instructions_counts_body_and_terminators():
    tac = run_benchmarks.compile_to_tac("func main() -> int { let int: x = 1 + 2; return x; }")
    # entry block: [t0 = 1 + 2] BinOp, [x.0 = t0] Copy, [ret x.0] terminator = 3
    assert run_benchmarks.count_instructions(tac) == 3


def test_run_benchmark_reports_reduction_and_matching_return_values():
    src = "func main() -> int { let int: a = 2 + 3; let int: unused = a * 100; return a; }"
    result = run_benchmarks.run_benchmark("tiny", src)

    assert result["return_value"] == 5
    assert result["instructions_before"] > result["instructions_after"]
    assert result["instruction_reduction_pct"] > 0
    assert result["time_before_ms"] >= 0
    assert result["time_after_ms"] >= 0


def test_run_benchmark_raises_if_semantic_errors_present():
    import pytest

    with pytest.raises(AssertionError):
        run_benchmarks.compile_to_tac("func main() -> int { return y; }")
