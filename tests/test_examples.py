"""Regression safety net for the examples/ corpus: every valid program
must still compile and run cleanly, and every deliberately-broken program
in examples/errors/ must still be rejected with a clear error (not crash)
as the compiler evolves.
"""
import io
from pathlib import Path

import pytest

from novac.cli import main

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
VALID_PROGRAMS = sorted(EXAMPLES_DIR.glob("*.nova"))
ERROR_PROGRAMS = sorted((EXAMPLES_DIR / "errors").glob("*.nova"))


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    code = main(args, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize("path", VALID_PROGRAMS, ids=lambda p: p.stem)
def test_valid_example_compiles_and_runs(path):
    code, out, err = run_cli([str(path), "--run"])
    assert code == 0, f"{path.name} failed to run: {err}"
    assert err == ""


@pytest.mark.parametrize("path", ERROR_PROGRAMS, ids=lambda p: p.stem)
def test_error_example_reports_error_without_crashing(path):
    code, out, err = run_cli([str(path)])
    assert code != 0
    assert "error:" in err


def test_examples_corpus_is_not_empty():
    # guards against a glob-pattern typo silently matching zero files
    assert len(VALID_PROGRAMS) >= 10
    assert len(ERROR_PROGRAMS) >= 3
