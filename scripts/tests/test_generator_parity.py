"""Compare legacy --option E output to new --site sites/option-e.yaml output.
Checks file-size drift only; pixel diff is in Task 9.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _blender(*extra: str) -> None:
    cmd = ["blender", "--background", "--python",
           str(ROOT / "scripts/generate_lng_site_blender.py"), "--"] + list(extra)
    subprocess.check_call(cmd, cwd=ROOT)


def test_option_e_dual_mode():
    legacy_blend = ROOT / "models/lng-site/option-e.blend"

    _blender("--option", "E", "--out", "models/lng-site")
    legacy_size = legacy_blend.stat().st_size
    legacy_copy = legacy_blend.with_suffix(".legacy.blend")
    legacy_blend.rename(legacy_copy)

    _blender("--site", "sites/option-e.yaml", "--out", "models/lng-site")
    new_size = legacy_blend.stat().st_size

    drift = abs(new_size - legacy_size) / legacy_size
    print(f"  legacy={legacy_size} new={new_size} drift={drift:.1%}")
    # The pipe_manifold geometry differs (Task 6 concern), so a moderate drift is expected.
    # 15% threshold accommodates that. Pixel diff in Task 9 is the real check.
    assert drift < 0.15, f"size drift {drift:.1%} exceeds 15% — likely missing equipment"

    legacy_copy.unlink()  # cleanup


if __name__ == "__main__":
    test_option_e_dual_mode()
    print("PASS")
