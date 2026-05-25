"""Test _resolve_vec accepts both numeric arrays and anchor refs."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests._runner import run_tests

# import the helpers from the cinematic generator
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import importlib
gen_module = importlib.import_module("generate_lng_cinematics")
_resolve_vec = gen_module._resolve_vec


def test_numeric_array():
    out = _resolve_vec([1.0, 2.0, 3.0], {}, "test")
    assert out == (1.0, 2.0, 3.0), f"got {out}"


def test_anchor_ref():
    anchors = {"foo": (4.0, 5.0, 6.0)}
    out = _resolve_vec({"anchor": "foo"}, anchors, "test")
    assert out == (4.0, 5.0, 6.0), f"got {out}"


def test_unknown_anchor_fails():
    try:
        _resolve_vec({"anchor": "missing"}, {"foo": (0, 0, 0)}, "test")
    except SystemExit as e:
        assert "missing" in str(e)
        return
    raise AssertionError("expected SystemExit")


if __name__ == "__main__":
    sys.exit(run_tests({
        "numeric array": test_numeric_array,
        "anchor ref": test_anchor_ref,
        "unknown anchor fails": test_unknown_anchor_fails,
    }))
