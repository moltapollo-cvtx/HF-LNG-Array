#!/usr/bin/env python3
"""Render a single preview frame of a cinematic at a given time `t`.

Used for surgical FOV verification (e.g. "what does the BOG hero shot look like
at t=20 with focal=45?"). Renders fast at low-res — Eevee, 480x270 default, no
captions, no post.

Usage (from project root):

    python scripts/preview_shot.py --site option-e --cinematic differentiator --t 30
    python scripts/preview_shot.py --site option-e --cinematic process-flow --t 5.5 --res 0.5 --open

When invoked under system python this script re-executes itself under
`blender --background`. When already running inside Blender it does the work.

Output: models/lng-site/cinematics/previews/<site>-<cinematic>-t<t>.png
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _in_blender() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Render a single preview frame at a given time.")
    p.add_argument("--site", required=True, help="site id, e.g. option-e")
    p.add_argument("--cinematic", required=True, help="cinematic name, e.g. differentiator")
    p.add_argument("--t", type=float, required=True, help="seconds from cinematic start")
    p.add_argument("--res", type=float, default=0.25,
                   help="resolution scale 0.05-1.0 (default 0.25 = 480x270)")
    p.add_argument("--engine", default="eevee", choices=("eevee", "cycles"))
    p.add_argument("--output", default=None,
                   help="output PNG path. Default: models/lng-site/cinematics/previews/<site>-<cinematic>-t<t>.png")
    p.add_argument("--captions", default=None,
                   help="Path to compiled cinematics JSON. Default: models/lng-site/<site>-cinematics.json")
    p.add_argument("--blend", default=None,
                   help="Path to source .blend. Default: models/lng-site/<site>.blend")
    p.add_argument("--site-yaml", default=None,
                   help="Path to sites/<site>.yaml. Default: sites/<site>.yaml")
    p.add_argument("--motion-blur", action=argparse.BooleanOptionalAction, default=False,
                   help="Eevee motion blur (off by default for still previews — slower with it on).")
    p.add_argument("--show-labels", action="store_true",
                   help="Keep the yellow blueprint labels visible.")
    p.add_argument("--open", action="store_true", help="Open the rendered PNG after render (macOS `open`).")
    return p.parse_args(argv)


# ---------- outer entry: re-exec under blender ----------

def _run_under_blender(argv) -> int:
    blender = os.environ.get("BLENDER_BIN") or "blender"
    cmd = [blender, "--background", "--python", str(Path(__file__).resolve()), "--", *argv]
    return subprocess.run(cmd).returncode


# ---------- inner entry: actually render ----------

def _resolve_paths(args):
    site = args.site
    blend = Path(args.blend or f"models/lng-site/{site}.blend")
    captions = Path(args.captions or f"models/lng-site/{site}-cinematics.json")
    site_yaml = Path(args.site_yaml or f"sites/{site}.yaml")
    if args.output:
        output = Path(args.output)
    else:
        t_label = f"{args.t:.2f}".replace(".", "p")
        output = ROOT / "models/lng-site/cinematics/previews" / f"{site}-{args.cinematic}-t{t_label}.png"
    for p in (blend, captions, site_yaml):
        if not (ROOT / p).is_file() and not p.is_file():
            raise SystemExit(f"[preview_shot] missing required file: {p}")
    return (
        (ROOT / blend) if not blend.is_absolute() else blend,
        (ROOT / captions) if not captions.is_absolute() else captions,
        (ROOT / site_yaml) if not site_yaml.is_absolute() else site_yaml,
        output,
    )


def _build_anchors(site_yaml):
    """Mirror generate_lng_cinematics._build_anchor_map() — kept inline so this script is independent."""
    from lib.site_config import load_site  # type: ignore
    site = load_site(str(site_yaml))
    anchors = {}
    for eq in site.equipment:
        anchors[eq.id] = eq.pos
    sx, sy = 15.5, 5.2
    ox, oy, oz = site.iso_array.origin
    anchors["isoArrayCenter"] = (
        ox + (site.iso_array.cols - 1) * sx / 2.0,
        oy + (site.iso_array.rows - 1) * sy / 2.0,
        oz + 1.45,
    )
    return anchors


def _inner_main(args) -> int:
    import json
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    import generate_lng_cinematics as gen  # type: ignore

    blend, captions_path, site_yaml, output = _resolve_paths(args)
    data = json.loads(captions_path.read_text())
    if args.cinematic not in data.get("cinematics", {}):
        raise SystemExit(
            f"[preview_shot] cinematic {args.cinematic!r} not in {captions_path.name}; "
            f"choose from {sorted(data['cinematics'])}"
        )
    cinematic = data["cinematics"][args.cinematic]
    fps = int(data.get("fps", 30))
    duration = float(cinematic["durationSec"])
    if not (0.0 <= args.t <= duration):
        raise SystemExit(f"[preview_shot] t={args.t} outside 0..{duration}s for {args.cinematic!r}")
    frame = max(1, int(round(args.t * fps)) + 1)

    anchors = _build_anchors(site_yaml)

    gen.open_blend(bpy, blend)
    scene = bpy.context.scene
    gen.remove_existing_cinematic_objects(bpy)
    if not args.show_labels:
        hidden = gen.hide_blueprint_labels(bpy)
        if hidden:
            print(f"[preview_shot] hid {hidden} label object(s)", flush=True)
    cam, target = gen.make_cinematic_camera(bpy)
    scene.camera = cam

    # Resolution
    res = list(data.get("resolution", [1920, 1080]))
    scale = max(0.05, min(1.0, args.res))
    w, h = int(res[0] * scale), int(res[1] * scale)
    w -= w % 2
    h -= h % 2
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.fps = fps

    # Engine
    if args.engine == "eevee":
        for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                continue
        eevee = getattr(scene, "eevee", None)
        if eevee is not None:
            for attr, value in (("taa_render_samples", 16), ("use_gtao", True)):
                if hasattr(eevee, attr):
                    setattr(eevee, attr, value)
        scene.render.use_motion_blur = args.motion_blur
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 32

    scene.view_settings.view_transform = "Filmic"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)

    # Keyframe the full camera path; we'll then jump to the single target frame.
    gen.keyframe_cinematic(Vector, scene, cam, target, cinematic, fps, anchors)
    scene.frame_start = 1
    scene.frame_end = max(2, frame + 1)
    scene.frame_set(frame)

    print(f"[preview_shot] {args.site}/{args.cinematic} @ t={args.t}s (frame {frame})  -> {output}", flush=True)
    print(f"[preview_shot] resolution {w}x{h}, engine {args.engine}", flush=True)
    bpy.ops.render.render(write_still=True)

    # Report active camera state for FOV awareness
    pos = cam.matrix_world.translation
    print(f"[preview_shot] camera pos=({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f}) focal={cam.data.lens:.1f}mm")
    print(f"[preview_shot] wrote {output}")
    if args.open:
        try:
            subprocess.run(["open", str(output)], check=False)
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    if _in_blender():
        # Blender passed args after '--'
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        try:
            sys.exit(_inner_main(_parse_args(argv)))
        except SystemExit:
            raise
        except Exception as exc:
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        sys.exit(_run_under_blender(sys.argv[1:]))
