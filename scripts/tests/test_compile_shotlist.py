"""Tests for compile_shotlist — the top-level orchestrator."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.shot_compiler import compile_shotlist, ShotListError  # pyright: ignore[reportMissingImports]
from tests._runner import run_tests

FIXTURE = Path(__file__).parent / "fixtures" / "minimal.shots.yaml"


def test_compile_produces_expected_structure():
    out = compile_shotlist(FIXTURE)
    assert out["fps"] == 30
    assert "cinematics" in out
    assert "micro" in out["cinematics"]
    micro = out["cinematics"]["micro"]
    assert micro["label"] == "Micro Test Cinematic"
    assert micro["durationSec"] == 9
    # wide (1 wp) + hero (2 wp) = 3 waypoints
    assert len(micro["waypoints"]) == 3
    assert micro["waypoints"][0]["t"] == 0.0
    assert micro["waypoints"][0]["caption"] == "Establishing"
    assert micro["waypoints"][1]["t"] == 5.0
    assert micro["waypoints"][1]["caption"] == "BOG hero"
    assert micro["waypoints"][2]["t"] == 9.0


def test_unknown_shot_type_raises():
    bad = Path(__file__).parent / "fixtures" / "_bad_type.shots.yaml"
    bad.write_text(
        "site: option-e\n"
        "cinematics:\n"
        "  x:\n"
        "    shots:\n"
        "      - {type: ZOOM, dur: 5, subject: site}\n"
    )
    try:
        compile_shotlist(bad)
    except ShotListError as e:
        assert "ZOOM" in str(e) or "zoom" in str(e).lower()
        bad.unlink()
        return
    bad.unlink()
    raise AssertionError("expected ShotListError for unknown type")


def test_unknown_subject_raises():
    bad = Path(__file__).parent / "fixtures" / "_bad_subject.shots.yaml"
    bad.write_text(
        "site: option-e\n"
        "cinematics:\n"
        "  x:\n"
        "    shots:\n"
        "      - {type: hero, dur: 5, subject: warpDrive}\n"
    )
    try:
        compile_shotlist(bad)
    except ShotListError as e:
        assert "warpDrive" in str(e)
        bad.unlink()
        return
    bad.unlink()
    raise AssertionError("expected ShotListError for unknown subject")


if __name__ == "__main__":
    sys.exit(run_tests({
        "compile produces structure": test_compile_produces_expected_structure,
        "unknown type raises": test_unknown_shot_type_raises,
        "unknown subject raises": test_unknown_subject_raises,
    }))
