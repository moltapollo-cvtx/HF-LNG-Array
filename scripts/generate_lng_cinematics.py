#!/usr/bin/env python3
"""Author and render Apollo LNG Option E cinematic flythroughs.

Dry-run validation (no Blender required):
  python3 scripts/generate_lng_cinematics.py --dry-run --cinematic all

Render one cinematic at full quality:
  blender --background --python scripts/generate_lng_cinematics.py -- \\
    --cinematic process-flow

Render all three (full quality):
  blender --background --python scripts/generate_lng_cinematics.py -- --cinematic all

Quick preview pass (low res, fast):
  blender --background --python scripts/generate_lng_cinematics.py -- \\
    --cinematic all --resolution-scale 0.25
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_anchor_map(args, payload: dict):
    """Return {anchor_id: (x,y,z)}. site YAML wins; payload featureAnchors fallback."""
    anchors = {}
    if args.site:
        sys.path.insert(0, str(project_root() / "scripts"))
        from lib.site_config import load_site  # pyright: ignore[reportMissingImports]
        site = load_site(args.site)
        for eq in site.equipment:
            anchors[eq.id] = eq.pos
        # Derived: isoArrayCenter from iso_array origin + half-extent
        # Use isoSpacing from lng-site-options.json assumptions.
        try:
            opts_path = project_root() / "models/lng-site/lng-site-options.json"
            import json as _json
            sx = _json.loads(opts_path.read_text())["assumptions"]["isoSpacing"]["x"]
            sy = _json.loads(opts_path.read_text())["assumptions"]["isoSpacing"]["y"]
        except Exception:
            sx, sy = 15.5, 5.2  # fallback
        ox, oy, oz = site.iso_array.origin
        anchors["isoArrayCenter"] = (
            ox + (site.iso_array.cols - 1) * sx / 2.0,
            oy + (site.iso_array.rows - 1) * sy / 2.0,
            oz + 1.45,
        )
    # Fallback: featureAnchors block in the cinematic JSON
    for k, v in (payload.get("featureAnchors") or {}).items():
        anchors.setdefault(k, tuple(v))
    return anchors


def _resolve_vec(value, anchors: dict, label: str):
    """Resolve a [x,y,z] list or {anchor: name} dict into a 3-tuple."""
    if isinstance(value, list) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    if isinstance(value, dict) and "anchor" in value:
        name = value["anchor"]
        if name not in anchors:
            raise SystemExit(f"{label}: unknown anchor '{name}'. known: {sorted(anchors)}")
        return anchors[name]
    raise SystemExit(f"{label}: expected [x,y,z] or {{anchor: name}}, got {value!r}")


def blender_cli_args(argv: list[str]) -> list[str]:
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv[1:]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Apollo LNG Option E cinematic flythroughs.")
    parser.add_argument("--cinematic", default="all", help="Cinematic id (process-flow|differentiator|scale-detail) or 'all'.")
    parser.add_argument("--data", default="models/lng-site/option-e-cinematics.json", help="Waypoint JSON.")
    parser.add_argument("--blend", default="models/lng-site/option-e.blend", help="Source Blender file.")
    parser.add_argument("--output-dir", default="models/lng-site/cinematics", help="Where rendered MP4s land.")
    parser.add_argument("--engine", default="eevee", choices=("eevee", "cycles"), help="Render engine.")
    parser.add_argument("--resolution-scale", type=float, default=1.0, help="0.0-1.0 scaling on render resolution.")
    parser.add_argument("--no-captions", action="store_true", help="Skip ffmpeg caption burn-in pass.")
    parser.add_argument("--dry-run", action="store_true", help="Validate JSON and print plan without invoking bpy.")
    parser.add_argument("--site", default=None,
        help="Path to sites/option-X.yaml. When given, feature anchors come from there.")
    parser.add_argument("--show-labels", action="store_true",
        help="Render the 2D yellow blueprint labels. Off by default — they're for blueprint view, not cinematic.")
    parser.add_argument("--motion-blur", action=argparse.BooleanOptionalAction, default=True,
        help="Eevee motion blur on/off. Default on — softens fast pans.")
    return parser.parse_args(blender_cli_args(argv))


def resolve_path(path_value: str) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else project_root() / p


def load_data(path_value: str) -> dict:
    data_path = resolve_path(path_value)
    if not data_path.exists():
        raise SystemExit(f"Missing cinematics JSON: {data_path}")
    return json.loads(data_path.read_text(encoding="utf8"))


def selected_cinematics(data: dict, cinematic_arg: str) -> list[tuple[str, dict]]:
    if cinematic_arg == "all":
        return list(data["cinematics"].items())
    if cinematic_arg not in data["cinematics"]:
        raise SystemExit(f"Unknown cinematic: {cinematic_arg}. Choose from {sorted(data['cinematics'])}.")
    return [(cinematic_arg, data["cinematics"][cinematic_arg])]


def validate_cinematic(name: str, cinematic: dict) -> None:
    waypoints = cinematic.get("waypoints") or []
    if len(waypoints) < 2:
        raise SystemExit(f"Cinematic '{name}' needs at least 2 waypoints, got {len(waypoints)}.")
    duration = cinematic.get("durationSec")
    if not duration or duration <= 0:
        raise SystemExit(f"Cinematic '{name}' is missing a positive durationSec.")
    last_t = -1.0
    for i, wp in enumerate(waypoints):
        t = wp.get("t")
        if t is None or t < 0 or t > duration:
            raise SystemExit(f"Cinematic '{name}' waypoint {i} has invalid t={t!r} for duration {duration}.")
        if t <= last_t:
            raise SystemExit(f"Cinematic '{name}' waypoint {i} t={t} is not strictly after previous t={last_t}.")
        last_t = t
        for key in ("pos", "lookAt"):
            arr = wp.get(key)
            if isinstance(arr, dict) and "anchor" in arr:
                continue  # anchor refs resolved later via _resolve_vec
            if not isinstance(arr, list) or len(arr) != 3:
                raise SystemExit(f"Cinematic '{name}' waypoint {i} has invalid {key}: {arr!r}")
        if not isinstance(wp.get("focal", 35), (int, float)) or wp.get("focal", 35) <= 0:
            raise SystemExit(f"Cinematic '{name}' waypoint {i} has invalid focal: {wp.get('focal')!r}")


# ------------------------------------------------------------------------------
# bpy-bearing code below this line. None of it runs during --dry-run.
# ------------------------------------------------------------------------------


def import_bpy():
    try:
        import bpy  # type: ignore
        from mathutils import Vector  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Blender Python is required to render. Invoke as: "
            "blender --background --python scripts/generate_lng_cinematics.py -- ..."
        ) from exc
    return bpy, Vector


EASE_MAP = {
    "linear":    ("LINEAR", "AUTO"),
    "easeIn":    ("CUBIC",  "EASE_IN"),
    "easeOut":   ("CUBIC",  "EASE_OUT"),
    "easeInOut": ("CUBIC",  "EASE_IN_OUT"),
}


def open_blend(bpy, blend_path: Path) -> None:
    if not blend_path.exists():
        raise SystemExit(f"Missing blend file: {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))


def remove_existing_cinematic_objects(bpy) -> None:
    for name in ("Cinematic Camera", "Cinematic Target"):
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)


# Material name used by the 2D blueprint labels. Anything wearing this material
# is a yellow gold-on-navy nameplate intended for the orthographic blueprint
# export, not the 3D drone cinematic.
BLUEPRINT_LABEL_MATERIAL = "Apollo gold nameplate"


def hide_blueprint_labels(bpy) -> int:
    """Hide the 2D yellow nameplate labels from cinematic renders.

    Targets objects either (a) wearing the "Apollo gold nameplate" material in
    any slot, or (b) whose name contains "label". Returns count hidden. The
    labels remain in the .blend for blueprint export — this only flips
    hide_render for the current render pass.
    """
    hidden = 0
    for obj in bpy.data.objects:
        is_label_named = "label" in obj.name.lower()
        uses_gold = False
        mat_slots = getattr(obj, "material_slots", None)
        if mat_slots:
            for slot in mat_slots:
                mat = getattr(slot, "material", None)
                if mat is not None and mat.name == BLUEPRINT_LABEL_MATERIAL:
                    uses_gold = True
                    break
        if is_label_named or uses_gold:
            obj.hide_render = True
            obj.hide_viewport = True
            hidden += 1
    return hidden


def make_cinematic_camera(bpy):
    cam_data = bpy.data.cameras.new("Cinematic Camera")
    cam_data.lens = 35
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new("Cinematic Camera", cam_data)
    bpy.context.collection.objects.link(cam)

    target = bpy.data.objects.new("Cinematic Target", None)
    target.empty_display_type = "SPHERE"
    target.empty_display_size = 0.6
    bpy.context.collection.objects.link(target)

    constraint = cam.constraints.new(type="TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"

    return cam, target


def clear_animation_data(obj) -> None:
    if obj.animation_data:
        obj.animation_data_clear()


def iter_action_fcurves(action):
    """Yield every F-curve on an Action across both legacy (<=4.3) and slotted (4.4+/5.x) API shapes."""
    legacy = getattr(action, "fcurves", None)
    if legacy is not None and len(legacy) > 0:
        yield from legacy
        return
    layers = getattr(action, "layers", None) or []
    slots = list(getattr(action, "slots", []) or [])
    for layer in layers:
        for strip in getattr(layer, "strips", []) or []:
            channelbags_iter = getattr(strip, "channelbags", None)
            if channelbags_iter is not None:
                for cb in channelbags_iter:
                    yield from getattr(cb, "fcurves", [])
                continue
            channelbag_fn = getattr(strip, "channelbag", None)
            if channelbag_fn is not None and slots:
                for slot in slots:
                    try:
                        cb = channelbag_fn(slot)
                    except TypeError:
                        cb = None
                    if cb is not None:
                        yield from getattr(cb, "fcurves", [])


def apply_easing_to_action(action, frame_to_ease: dict[int, str]) -> None:
    for fc in iter_action_fcurves(action):
        for kp in fc.keyframe_points:
            ease_name = frame_to_ease.get(int(round(kp.co.x)))
            if not ease_name:
                continue
            interp, easing = EASE_MAP.get(ease_name, ("BEZIER", "AUTO"))
            kp.interpolation = interp
            kp.easing = easing


def keyframe_cinematic(Vector, scene, cam, target, cinematic: dict, fps: int, anchors: dict | None = None) -> tuple[int, int]:
    waypoints = cinematic["waypoints"]
    duration = cinematic["durationSec"]
    total_frames = int(round(duration * fps))
    scene.frame_start = 1
    scene.frame_end = total_frames

    clear_animation_data(cam)
    clear_animation_data(cam.data)
    clear_animation_data(target)

    anchors = anchors or {}
    frame_to_ease: dict[int, str] = {}
    for i, wp in enumerate(waypoints):
        frame = max(1, int(round(wp["t"] * fps)) + 1)  # 1-indexed timeline
        scene.frame_set(frame)
        pos = _resolve_vec(wp["pos"], anchors, f"waypoint {i} pos")
        lookat = _resolve_vec(wp["lookAt"], anchors, f"waypoint {i} lookAt")
        cam.location = Vector(pos)
        cam.data.lens = float(wp.get("focal", 35))
        target.location = Vector(lookat)
        cam.keyframe_insert(data_path="location", frame=frame)
        cam.data.keyframe_insert(data_path="lens", frame=frame)
        target.keyframe_insert(data_path="location", frame=frame)
        frame_to_ease[frame] = wp.get("ease", "easeInOut")

    for action in (
        cam.animation_data.action if cam.animation_data else None,
        cam.data.animation_data.action if cam.data.animation_data else None,
        target.animation_data.action if target.animation_data else None,
    ):
        if action is not None:
            apply_easing_to_action(action, frame_to_ease)

    return scene.frame_start, scene.frame_end


def configure_render_to_png_sequence(scene, args, frames_dir: Path, fps: int, resolution: tuple[int, int]) -> None:
    scale = max(0.05, min(1.0, args.resolution_scale))
    width = int(round(resolution[0] * scale))
    height = int(round(resolution[1] * scale))
    width -= width % 2
    height -= height % 2

    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps

    if args.engine == "eevee":
        for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                continue
        eevee = getattr(scene, "eevee", None)
        if eevee is not None:
            for attr, value in (
                ("taa_render_samples", 32),
                ("use_bloom", True),
                ("use_ssr", True),
                ("use_gtao", True),
            ):
                if hasattr(eevee, attr):
                    setattr(eevee, attr, value)
        # Motion blur softens the residual whip on fast pans (Walker spec: max 10 m/s).
        use_mb = getattr(args, "motion_blur", True)
        scene.render.use_motion_blur = use_mb
        if eevee is not None:
            if hasattr(eevee, "use_motion_blur"):
                eevee.use_motion_blur = use_mb
            if hasattr(eevee, "motion_blur_shutter") and use_mb:
                eevee.motion_blur_shutter = 0.5
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 64
        scene.render.use_motion_blur = getattr(args, "motion_blur", True)

    scene.view_settings.view_transform = "Filmic"

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15

    frames_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frames_dir / "frame_")


def caption_for_time(waypoints: list, duration: float, t: float) -> str:
    for i, wp in enumerate(waypoints):
        end = waypoints[i + 1]["t"] if i + 1 < len(waypoints) else duration
        if wp["t"] <= t < end:
            return wp.get("caption", "")
    return ""


def burn_captions_with_pillow(frames_dir: Path, cinematic: dict, fps: int) -> int:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found]
    except ImportError:
        print("[captions] Pillow not available; skipping caption burn-in.", flush=True)
        return 0

    font_candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    font_path = next((p for p in font_candidates if Path(p).exists()), None)

    waypoints = cinematic["waypoints"]
    duration = float(cinematic["durationSec"])

    frames = sorted(frames_dir.glob("frame_*.png"))
    if not frames:
        return 0

    sample = Image.open(frames[0])
    width, height = sample.size
    sample.close()
    font_size = max(14, int(height * 0.034))
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()

    pad_x = max(10, int(font_size * 0.7))
    pad_y = max(6, int(font_size * 0.4))
    bottom_offset = int(height * 0.07)
    burned = 0

    for frame_path in frames:
        try:
            frame_index = int(frame_path.stem.split("_")[-1])
        except ValueError:
            continue
        t = (frame_index - 1) / fps
        caption = caption_for_time(waypoints, duration, t)
        if not caption:
            continue

        with Image.open(frame_path) as img:
            img = img.convert("RGBA")
            draw = ImageDraw.Draw(img, "RGBA")
            try:
                bbox = draw.textbbox((0, 0), caption, font=font)
            except AttributeError:
                tw, th = draw.textsize(caption, font=font)
                bbox = (0, 0, tw, th)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            box_w = tw + pad_x * 2
            box_h = th + pad_y * 2
            box_x = (width - box_w) // 2
            box_y = height - box_h - bottom_offset
            draw.rounded_rectangle(
                (box_x, box_y, box_x + box_w, box_y + box_h),
                radius=max(4, int(font_size * 0.25)),
                fill=(0, 0, 0, int(0.55 * 255)),
            )
            text_x = box_x + pad_x - bbox[0]
            text_y = box_y + pad_y - bbox[1]
            draw.text((text_x, text_y), caption, font=font, fill=(255, 255, 255, 255))
            img.convert("RGB").save(frame_path, "PNG")
        burned += 1
    return burned


def encode_with_ffmpeg(frames_dir: Path, final_path: Path, fps: int) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to encode the PNG sequence into MP4.")
    pattern = str(frames_dir / "frame_%04d.png")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        "-r", str(fps),
        str(final_path),
    ]
    print(f"[encode] encoding → {final_path.name}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[encode] ffmpeg failed:", flush=True)
        print(result.stderr[-2000:], flush=True)
        raise SystemExit("ffmpeg encode failed")


def render_one(bpy, Vector, args, data: dict, name: str, cinematic: dict, blend_path: Path, output_dir: Path, anchors: dict | None = None) -> Path:
    fps = int(data.get("fps", 30))
    resolution = tuple(data.get("resolution", [1920, 1080]))

    open_blend(bpy, blend_path)
    scene = bpy.context.scene
    remove_existing_cinematic_objects(bpy)
    if not getattr(args, "show_labels", False):
        hidden = hide_blueprint_labels(bpy)
        if hidden:
            print(f"[labels] hiding {hidden} blueprint label object(s) from cinematic render", flush=True)
    cam, target = make_cinematic_camera(bpy)
    scene.camera = cam

    keyframe_cinematic(Vector, scene, cam, target, cinematic, fps, anchors)

    final_path = output_dir / f"option-e-{name}.mp4"
    with tempfile.TemporaryDirectory(prefix=f"apollo-cinematic-{name}-") as tmp:
        frames_dir = Path(tmp)
        configure_render_to_png_sequence(scene, args, frames_dir, fps, resolution)
        bpy.ops.render.render(animation=True)
        if not args.no_captions:
            burned = burn_captions_with_pillow(frames_dir, cinematic, fps)
            print(f"[captions] burned {burned} caption frames", flush=True)
        encode_with_ffmpeg(frames_dir, final_path, fps)
    return final_path


def dry_run(args, data: dict) -> None:
    fps = int(data.get("fps", 30))
    print(f"[dry-run] fps={fps}, blend={args.blend}, engine={args.engine}, scale={args.resolution_scale}")
    anchors = _build_anchor_map(args, data)
    for name, cinematic in selected_cinematics(data, args.cinematic):
        validate_cinematic(name, cinematic)
        waypoints = cinematic["waypoints"]
        duration = cinematic["durationSec"]
        print(f"[dry-run] '{name}' — {cinematic.get('label', name)}: {len(waypoints)} waypoints, {duration}s, {int(duration * fps)} frames")
        for i, wp in enumerate(waypoints):
            frame = int(round(wp["t"] * fps)) + 1
            pos = _resolve_vec(wp["pos"], anchors, f"{name} waypoint {i} pos")
            la = _resolve_vec(wp["lookAt"], anchors, f"{name} waypoint {i} lookAt")
            print(f"           t={wp['t']:>5.2f}s f={frame:>5d}  pos=({pos[0]:>7.2f},{pos[1]:>7.2f},{pos[2]:>7.2f})  →  ({la[0]:>7.2f},{la[1]:>7.2f},{la[2]:>7.2f})  lens={wp.get('focal', 35):>4}  ease={wp.get('ease', 'easeInOut')}  {wp.get('caption', '')}")


def main() -> None:
    args = parse_args(sys.argv)
    data = load_data(args.data)
    for name, cinematic in selected_cinematics(data, args.cinematic):
        validate_cinematic(name, cinematic)

    if args.dry_run:
        dry_run(args, data)
        return

    bpy, Vector = import_bpy()
    blend_path = resolve_path(args.blend)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    anchors = _build_anchor_map(args, data)
    rendered: list[Path] = []
    for name, cinematic in selected_cinematics(data, args.cinematic):
        print(f"[render] {name} → {output_dir / f'option-e-{name}.mp4'}", flush=True)
        path = render_one(bpy, Vector, args, data, name, cinematic, blend_path, output_dir, anchors)
        rendered.append(path)
        print(f"[render] done: {path}", flush=True)

    print("[render] all cinematics complete:")
    for p in rendered:
        size_mb = p.stat().st_size / (1024 * 1024) if p.exists() else 0
        print(f"  {p}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
