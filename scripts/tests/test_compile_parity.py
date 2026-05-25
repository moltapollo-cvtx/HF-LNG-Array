"""Parity test: DSL-compiled cinematic must render within mean pixel diff
threshold across 3 sample frames vs. the hand-tuned v1.6 cinematic.

Threshold rationale: the DSL re-derives camera waypoints from smart defaults
(arc / orbit / dolly) anchored on the site YAML, so it does NOT reproduce
the v1.6 hand-tuned poses frame-for-frame. The 0.25x preview render of the
process-flow cinematic measured mean=33.7/255 (t=10:47.5, t=22:34.1,
t=35:19.7) against v1.6 on 2026-05-25 — accepted as the DSL framing baseline.
40/255 is the gate that catches a real regression (e.g. anchor resolution
broken, shot order scrambled) without false-failing on framing variance.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "models/lng-site/cinematics/preview-legacy/option-e-process-flow.mp4"
DSL    = ROOT / "models/lng-site/cinematics/preview-dsl/option-e-process-flow.mp4"


def _diff(t: int) -> float:
    leg = f"/tmp/legacy_{t}.png"
    dsl = f"/tmp/dsl_{t}.png"
    diff = f"/tmp/diff_{t}.png"
    subprocess.check_call(["ffmpeg", "-y", "-i", str(LEGACY), "-vframes", "1", "-ss", str(t), leg],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call(["ffmpeg", "-y", "-i", str(DSL),    "-vframes", "1", "-ss", str(t), dsl],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call(["ffmpeg", "-y", "-i", leg, "-i", dsl, "-filter_complex",
                           "blend=all_mode=difference", "-frames:v", "1", diff],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    from PIL import Image, ImageStat
    return ImageStat.Stat(Image.open(diff).convert("L")).mean[0]


def main() -> int:
    diffs = {t: _diff(t) for t in (10, 22, 35)}
    mean = sum(diffs.values()) / len(diffs)
    for t, d in diffs.items():
        print(f"t={t}s: {d:.3f}/255")
    print(f"mean: {mean:.3f}/255")
    threshold = 40.0
    if mean > threshold:
        print(f"FAIL: mean diff exceeds {threshold:.1f}/255")
        return 1
    print(f"PASS (threshold={threshold:.1f}/255)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
