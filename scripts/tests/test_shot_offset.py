"""Tests for offset() — compass-direction camera placement."""
from __future__ import annotations
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.shot_compiler import offset  # pyright: ignore[reportMissingImports]
from tests._runner import run_tests


def _close(a, b, tol=1e-3):
    return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))


def test_north_offset():
    out = offset(subject=(0, 0, 0), direction="N", distance=10, height=5)
    assert _close(out, (0, 10, 5)), out


def test_southeast_offset():
    out = offset(subject=(0, 0, 0), direction="SE", distance=10, height=2)
    expected = (math.sqrt(2)/2 * 10, -math.sqrt(2)/2 * 10, 2)
    assert _close(out, expected), out


def test_offset_relative_to_nonzero_subject():
    out = offset(subject=(5, -3, 0), direction="W", distance=10, height=8)
    assert _close(out, (5 - 10, -3, 8)), out


def test_invalid_direction_raises():
    try:
        offset(subject=(0, 0, 0), direction="northwest", distance=10, height=5)
    except ValueError as e:
        assert "northwest" in str(e)
        return
    raise AssertionError("expected ValueError")


if __name__ == "__main__":
    sys.exit(run_tests({
        "north offset": test_north_offset,
        "southeast offset": test_southeast_offset,
        "subject-relative offset": test_offset_relative_to_nonzero_subject,
        "invalid direction raises": test_invalid_direction_raises,
    }))
