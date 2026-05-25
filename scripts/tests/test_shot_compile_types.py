"""Tests for per-shot-type compile functions."""
from __future__ import annotations
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.shot_compiler import (  # pyright: ignore[reportMissingImports]
    Shot,
    compile_wide, compile_push, compile_pull, compile_hero,
    compile_pan, compile_orbit, compile_fly, compile_land, compile_hold,
)
from tests._runner import run_tests


SUBJECT = (10.0, -5.0, 0.0)


def test_wide_emits_one_waypoint_at_start():
    shot = Shot(type="wide", dur=5, subject="x", caption="Establishing")
    wps = compile_wide(shot, start_t=10, subject_pos=SUBJECT)
    assert len(wps) == 1
    assert wps[0].t == 10
    assert wps[0].focal == 24
    assert wps[0].caption == "Establishing"
    expected_pos = (SUBJECT[0] + 70.71, SUBJECT[1] - 70.71, 60.0)
    assert all(math.isclose(a, b, abs_tol=0.1) for a, b in zip(wps[0].pos, expected_pos)), wps[0].pos


def test_push_emits_two_waypoints_far_to_close():
    shot = Shot(type="push", dur=5, subject="x", caption="Push", from_dir="NW")
    wps = compile_push(shot, start_t=0, subject_pos=SUBJECT)
    assert len(wps) == 2
    assert wps[0].t == 0
    assert wps[1].t == 5
    d0 = math.dist(wps[0].pos[:2], SUBJECT[:2])
    d1 = math.dist(wps[1].pos[:2], SUBJECT[:2])
    assert math.isclose(d0, 50.0, abs_tol=0.5), d0
    assert math.isclose(d1, 25.0, abs_tol=0.5), d1
    assert wps[0].focal == 35
    assert wps[1].focal == 42


def test_pull_emits_two_waypoints_close_to_far():
    shot = Shot(type="pull", dur=4, subject="x", caption="Pull", from_dir="NW")
    wps = compile_pull(shot, start_t=0, subject_pos=SUBJECT)
    assert len(wps) == 2
    d0 = math.dist(wps[0].pos[:2], SUBJECT[:2])
    d1 = math.dist(wps[1].pos[:2], SUBJECT[:2])
    assert math.isclose(d0, 25.0, abs_tol=0.5), d0
    assert math.isclose(d1, 50.0, abs_tol=0.5), d1


def test_hero_drifts_subtly_over_duration():
    shot = Shot(type="hero", dur=5, subject="x", caption="Hero")
    wps = compile_hero(shot, start_t=0, subject_pos=SUBJECT)
    assert len(wps) == 2
    d0 = math.dist(wps[0].pos[:2], SUBJECT[:2])
    d1 = math.dist(wps[1].pos[:2], SUBJECT[:2])
    assert math.isclose(d0, 30.0, abs_tol=0.5), d0
    assert math.isclose(d1, 32.0, abs_tol=0.5), d1
    assert wps[0].focal == 40
    assert wps[1].focal == 40


def test_pan_sweeps_sw_to_se():
    shot = Shot(type="pan", dur=4, subject="x", caption="Pan")
    wps = compile_pan(shot, start_t=0, subject_pos=SUBJECT)
    assert len(wps) == 2
    assert wps[0].pos[0] < SUBJECT[0], "start should be west of subject"
    assert wps[1].pos[0] > SUBJECT[0], "end should be east of subject"


def test_orbit_emits_multiple_waypoints():
    shot = Shot(type="orbit", dur=12, subject="x", caption="Orbit")
    wps = compile_orbit(shot, start_t=0, subject_pos=SUBJECT)
    assert len(wps) == 5, len(wps)
    for w in wps:
        d = math.dist(w.pos[:2], SUBJECT[:2])
        assert math.isclose(d, 80.0, abs_tol=0.5), d


def test_fly_descends_and_closes():
    shot = Shot(type="fly", dur=8, subject="x", caption="Fly", from_dir="W")
    wps = compile_fly(shot, start_t=0, subject_pos=SUBJECT)
    assert len(wps) == 2
    assert wps[0].pos[2] > wps[1].pos[2], "should descend"
    d0 = math.dist(wps[0].pos[:2], SUBJECT[:2])
    d1 = math.dist(wps[1].pos[:2], SUBJECT[:2])
    assert d0 > d1, "should close"


def test_land_emits_one_waypoint_at_end():
    shot = Shot(type="land", dur=3, subject="x", caption="Land")
    wps = compile_land(shot, start_t=42, subject_pos=SUBJECT)
    assert len(wps) == 1
    assert wps[0].t == 45
    assert wps[0].focal == 50


def test_hold_emits_no_waypoints():
    shot = Shot(type="hold", dur=2, subject="x", caption="")
    wps = compile_hold(shot, start_t=10, subject_pos=SUBJECT)
    assert wps == []


def test_focal_override_applies_to_both_waypoints():
    shot = Shot(type="push", dur=5, subject="x", caption="X", focal=50)
    wps = compile_push(shot, start_t=0, subject_pos=SUBJECT)
    assert wps[0].focal == 50
    assert wps[1].focal == 50


if __name__ == "__main__":
    sys.exit(run_tests({
        "wide": test_wide_emits_one_waypoint_at_start,
        "push": test_push_emits_two_waypoints_far_to_close,
        "pull": test_pull_emits_two_waypoints_close_to_far,
        "hero": test_hero_drifts_subtly_over_duration,
        "pan": test_pan_sweeps_sw_to_se,
        "orbit": test_orbit_emits_multiple_waypoints,
        "fly": test_fly_descends_and_closes,
        "land": test_land_emits_one_waypoint_at_end,
        "hold": test_hold_emits_no_waypoints,
        "focal override": test_focal_override_applies_to_both_waypoints,
    }))
