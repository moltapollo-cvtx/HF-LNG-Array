#!/usr/bin/env python3
"""Scaffold a sites/option-X.yaml from parametric inputs.

Ports the placement formulas in `build_scene()` (generate_lng_site_blender.py) to
a standalone CLI. Coordinate frame: +x = east, +y = north, +z = up. Site center
at origin. Equipment z is 0 (ground plane); builders apply per-type height offsets.

NOTE — Option-E-tuned constants:
The current build_scene() derives several positions from `site_length` /
`site_width`, which are themselves derived from `footprintAcres`. For Option E
(footprintAcres=2.3) these resolve to roughly:
    array_center_x = -site_length * 0.10  ≈ -15.97
    vaporizer_x    =  site_length / 2 - 35  ≈  44.85
    transport_x    = -site_length / 2 + 27  ≈ -51.85 (and y = site_width/2 - 13.5 ≈ 18.02)
    delivery_x     =  site_length / 2 - 7   ≈  72.85
    queens_x       = -site_length / 2 + 28  ≈ -51.85 (midpoint with +16.5 trailer ≈ -43.6)
This scaffolder hardcodes the Option-E values because Task 4's parity target is
Option E. Generalizing these formulas across options A-D is Task 6/7 work.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Scaffold an Apollo LNG site YAML.")
    p.add_argument("--letter", required=True)
    p.add_argument("--isos", type=int, required=True)
    p.add_argument("--cols", type=int, required=True)
    p.add_argument("--rows", type=int, required=True)
    p.add_argument("--has-capture", action="store_true")
    p.add_argument("--has-pump", action="store_true")
    p.add_argument("--title", default="")
    p.add_argument("--subtitle", default="")
    p.add_argument("--data", default="models/lng-site/lng-site-options.json")
    return p.parse_args(argv)


def load_assumptions(data_path: Path) -> dict:
    with data_path.open() as fh:
        return json.load(fh)["assumptions"]


def compute_layout(args, assumptions: dict) -> dict:
    """Replicates the position formulas from build_scene().
    Coordinate frame: +x = east, +y = north, +z = up. Site center at origin.
    """
    sx = assumptions["isoSpacing"]["x"]
    sy = assumptions["isoSpacing"]["y"]

    # ISO array centered on (-16, -2) per current build_scene; SW corner = center - half-extent
    array_w = (args.cols - 1) * sx
    array_h = (args.rows - 1) * sy
    array_cx = -15.97
    array_cy = -2.0
    origin = (round(array_cx - array_w / 2, 2),
              round(array_cy - array_h / 2, 2),
              0.0)

    cryo = (array_cx, round(array_cy - 15.0, 2), 0.0)
    queens = (round(cryo[0] - 27.63, 2), round(cryo[1] - 2.5, 2), 0.0)
    vaporizer = (44.85, -6.0, 0.0)
    transport = (-51.85, 18.02, 0.0)
    delivery = (72.85, -3.5, 0.0)
    bog = (31.85, -15.0, 0.0)

    equipment = [
        {"id": "transportOffload", "type": "truck_bay",                    "pos": list(transport), "rotation": 0},
        {"id": "cryoManifold",     "type": "pipe_manifold",                "pos": list(cryo),      "rotation": 0},
        {"id": "queens",           "type": "queens_pair",                  "pos": list(queens),    "rotation": 0},
        {"id": "vaporizer",        "type": "glycol_vaporizer_with_stack",  "pos": list(vaporizer), "rotation": 0},
        {"id": "delivery",         "type": "delivery_flange",              "pos": list(delivery),  "rotation": 0},
    ]
    if args.has_capture:
        equipment.insert(-1, {"id": "bogCapture", "type": "bog_skid", "pos": list(bog), "rotation": 0})

    return {
        "site": {
            "id": f"option-{args.letter.lower()}",
            "letter": args.letter.upper(),
            "title": args.title or f"Option {args.letter.upper()}",
            "subtitle": args.subtitle,
            "footprintAcres": 2.3,
            "enduranceHrs": 22,
            "hasPump": bool(args.has_pump),
            "hasCapture": bool(args.has_capture),
            "recommended": False,
        },
        "iso_array": {
            "count": args.isos,
            "cols": args.cols,
            "rows": args.rows,
            "origin": list(origin),
            "rotation": 0,
        },
        "equipment": equipment,
    }


def main(argv=None):
    args = parse_args(argv)
    assumptions = load_assumptions(ROOT / args.data)
    site = compute_layout(args, assumptions)
    yaml.safe_dump(site, sys.stdout, sort_keys=False, default_flow_style=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
