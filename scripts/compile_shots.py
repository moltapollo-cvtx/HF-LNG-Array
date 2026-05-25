#!/usr/bin/env python3
"""Compile a *.shots.yaml file into the cinematic JSON the renderer reads.

Usage:
  python scripts/compile_shots.py cinematics/option-e.shots.yaml
      → models/lng-site/option-e-cinematics.json   (default output path)

  python scripts/compile_shots.py cinematics/option-e.shots.yaml --out /tmp/out.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.shot_compiler import compile_shotlist, ShotListError  # pyright: ignore[reportMissingImports]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Compile a shots.yaml into cinematic JSON.")
    p.add_argument("input", help="Path to *.shots.yaml")
    p.add_argument("--out", default=None,
        help="Output path. Default: models/lng-site/<site>-cinematics.json")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    src = Path(args.input)
    try:
        out = compile_shotlist(src)
    except ShotListError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.out is None:
        site = src.stem
        if site.endswith(".shots"):
            site = site[:-6]
        out_path = src.resolve().parents[1] / "models" / "lng-site" / f"{site}-cinematics.json"
    else:
        out_path = Path(args.out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    n = sum(len(c["waypoints"]) for c in out["cinematics"].values())
    print(f"[compile_shots] wrote {out_path} ({len(out['cinematics'])} cinematics, {n} waypoints)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
