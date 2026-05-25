"""Tests for the closed shot vocabulary + defaults table."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.shot_types import SHOT_TYPES, DEFAULTS, ShotDefaults
from tests._runner import run_tests


def test_vocab_is_closed():
    assert SHOT_TYPES == frozenset({
        "wide", "push", "pull", "hero", "pan", "orbit", "fly", "land", "hold",
    }), SHOT_TYPES


def test_every_type_has_defaults():
    for t in SHOT_TYPES:
        assert t in DEFAULTS, f"missing defaults for {t}"


def test_defaults_have_expected_shape():
    h = DEFAULTS["hero"]
    assert isinstance(h, ShotDefaults)
    assert h.focal == 40
    assert h.distance == 30
    assert h.height == 8
    assert h.ease == "easeInOut"


def test_hold_has_no_geometric_defaults():
    h = DEFAULTS["hold"]
    assert h.focal is None
    assert h.distance is None
    assert h.height is None


if __name__ == "__main__":
    sys.exit(run_tests({
        "vocab closed": test_vocab_is_closed,
        "every type has defaults": test_every_type_has_defaults,
        "defaults shape": test_defaults_have_expected_shape,
        "hold no geom": test_hold_has_no_geometric_defaults,
    }))
