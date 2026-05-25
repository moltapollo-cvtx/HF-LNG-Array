"""Scaffolder parity tests — generated YAML should match current build_scene positions."""
from __future__ import annotations
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from tests._runner import run_tests

ROOT = Path(__file__).resolve().parents[2]


def _scaffold(letter: str, isos: int, cols: int, rows: int, has_capture: bool, has_pump: bool) -> dict:
    args = [
        sys.executable,
        str(ROOT / "scripts/scaffold_site.py"),
        "--letter", letter,
        "--isos", str(isos),
        "--cols", str(cols),
        "--rows", str(rows),
    ]
    if has_capture:
        args.append("--has-capture")
    if has_pump:
        args.append("--has-pump")
    out = subprocess.check_output(args, text=True)
    return yaml.safe_load(out)


def test_option_e_layout():
    """24-ISO Option E should produce the same anchor positions as the current generator."""
    site = _scaffold("E", isos=24, cols=6, rows=4, has_capture=True, has_pump=False)
    eq_by_id = {e["id"]: e for e in site["equipment"]}
    expected = {
        "transportOffload": (-51.85, 18.02, 0),
        "cryoManifold":     (-15.97, -17.02, 0),
        "queens":           (-43.6,  -19.52, 0),
        "vaporizer":        ( 44.85,  -6.0,  0),
        "bogCapture":       ( 31.85, -15.0,  0),
        "delivery":         ( 72.85,  -3.5,  0),
    }
    for eq_id, (ex, ey, ez) in expected.items():
        ax, ay, az = eq_by_id[eq_id]["pos"]
        assert math.isclose(ax, ex, abs_tol=0.5), f"{eq_id}.x: got {ax}, expected {ex}"
        assert math.isclose(ay, ey, abs_tol=0.5), f"{eq_id}.y: got {ay}, expected {ey}"
        assert math.isclose(az, ez, abs_tol=0.5), f"{eq_id}.z: got {az}, expected {ez}"


def test_option_a_omits_bog():
    site = _scaffold("A", isos=4, cols=2, rows=2, has_capture=False, has_pump=False)
    ids = {e["id"] for e in site["equipment"]}
    assert "bogCapture" not in ids, f"unexpected bogCapture in non-capture option: {ids}"


def test_iso_array_grid():
    site = _scaffold("E", isos=24, cols=6, rows=4, has_capture=True, has_pump=False)
    assert site["iso_array"]["count"] == 24
    assert site["iso_array"]["cols"] == 6
    assert site["iso_array"]["rows"] == 4


if __name__ == "__main__":
    sys.exit(run_tests({
        "option E layout": test_option_e_layout,
        "option A omits BOG": test_option_a_omits_bog,
        "iso array grid": test_iso_array_grid,
    }))
