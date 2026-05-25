#!/usr/bin/env python3
"""Run the Blender cinematic render with a live progress bar.

Wraps `blender --background --python scripts/generate_lng_cinematics.py -- ...`
and parses its stdout for per-frame save lines + per-cinematic start markers,
driving a tqdm progress bar. The full Blender log is mirrored to a file so
nothing is lost.

Usage (drop-in replacement for the bare blender command):

    python scripts/render_with_progress.py -- --cinematic all --no-captions \\
        --output-dir models/lng-site/cinematics/no-captions \\
        --site sites/option-e.yaml

Anything after `--` is forwarded to the inner script as-is. Output frames
match what the underlying renderer would have produced.

Frame totals are computed up-front from the compiled cinematics JSON so the
ETA is meaningful from frame 1, not from frame N once we figure out duration.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent


def _parse_outer(argv):
    # Split argv at '--' — everything after is the inner Blender script args.
    if "--" in argv:
        i = argv.index("--")
        outer, inner = argv[:i], argv[i + 1:]
    else:
        outer, inner = argv, []
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"),
                   help="Blender binary (default: $BLENDER_BIN or 'blender').")
    p.add_argument("--script", default=str(ROOT / "scripts/generate_lng_cinematics.py"),
                   help="Inner Blender script.")
    p.add_argument("--data", default="models/lng-site/option-e-cinematics.json",
                   help="Compiled cinematics JSON (used for frame totals).")
    p.add_argument("--log", default=None,
                   help="Mirror Blender stdout to this file. Default: logs/blender-<timestamp>.log")
    args = p.parse_args(outer)
    args.inner = inner
    return args


def _frame_plan(data_path: Path, inner_args: list[str]) -> tuple[list[tuple[str, int]], int]:
    """Compute (cinematic_name, frame_count) pairs and total frames.

    Honors `--cinematic <name>|all` from the inner args.
    """
    data = json.loads(data_path.read_text())
    fps = int(data.get("fps", 30))
    cinematics = data.get("cinematics", {})
    target = "all"
    if "--cinematic" in inner_args:
        idx = inner_args.index("--cinematic")
        if idx + 1 < len(inner_args):
            target = inner_args[idx + 1]
    plan: list[tuple[str, int]] = []
    if target == "all":
        names = list(cinematics.keys())
    else:
        if target not in cinematics:
            raise SystemExit(f"[render_with_progress] cinematic {target!r} not in {data_path.name}")
        names = [target]
    for n in names:
        dur = float(cinematics[n]["durationSec"])
        plan.append((n, int(round(dur * fps))))
    total = sum(p[1] for p in plan)
    return plan, total


RE_FRAME_SAVED = re.compile(r"Saved: '.*frame_(\d+)\.png'")
RE_RENDER_START = re.compile(r"^\[render\] (\S+) ")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse_outer(argv)

    data_path = ROOT / args.data
    if not data_path.is_file():
        raise SystemExit(f"[render_with_progress] missing cinematics JSON at {data_path}. "
                         f"Run `python scripts/compile_shots.py cinematics/<site>.shots.yaml` first.")
    plan, total_frames = _frame_plan(data_path, args.inner)
    if total_frames <= 0:
        raise SystemExit("[render_with_progress] frame plan empty — nothing to do")

    log_path = Path(args.log) if args.log else (
        ROOT / "logs" / f"blender-{time.strftime('%Y%m%d-%H%M%S')}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [args.blender, "--background", "--python", args.script, "--", *args.inner]
    print(f"[render_with_progress] launching: {' '.join(cmd)}", flush=True)
    print(f"[render_with_progress] mirroring stdout to {log_path}", flush=True)
    print(f"[render_with_progress] plan: {plan}  total frames={total_frames}", flush=True)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            bufsize=1, universal_newlines=True, cwd=ROOT)
    overall = tqdm(total=total_frames, unit="frame", desc="overall", position=0,
                   bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    current_name: str | None = None
    current_bar: tqdm | None = None
    current_total = 0
    current_count = 0

    plan_lookup = dict(plan)
    started_at = time.time()
    try:
        with log_path.open("w") as log_fh:
            assert proc.stdout is not None
            for line in proc.stdout:
                log_fh.write(line)
                log_fh.flush()
                m = RE_RENDER_START.search(line)
                if m:
                    name = m.group(1)
                    if name in plan_lookup:
                        if current_bar is not None:
                            current_bar.close()
                        current_name = name
                        current_total = plan_lookup[name]
                        current_count = 0
                        current_bar = tqdm(total=current_total, unit="frame",
                                           desc=f"  {name}", position=1, leave=True,
                                           bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
                    continue
                m = RE_FRAME_SAVED.match(line.strip()) or RE_FRAME_SAVED.search(line)
                if m:
                    overall.update(1)
                    if current_bar is not None and current_count < current_total:
                        current_bar.update(1)
                        current_count += 1
                    continue
                # Pass through informational lines for visibility
                if any(tag in line for tag in ("[render]", "[encode]", "[labels]", "[captions]", "[velocity-retime]", "ERROR", "Error")):
                    overall.write(line.rstrip())
    finally:
        if current_bar is not None:
            current_bar.close()
        overall.close()

    rc = proc.wait()
    elapsed = time.time() - started_at
    print(f"[render_with_progress] exit={rc} elapsed={elapsed:.1f}s  log={log_path}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
