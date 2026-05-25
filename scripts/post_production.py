#!/usr/bin/env python3
"""Post-production toolchain for Apollo LNG Option E cinematics.

Phase 5 of the polish pass: title card, end card, color grade, vignette,
film grain, optional caption rebuild, concat. Pillow + ffmpeg subprocess.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    sys.stderr.write(
        "Pillow is required. Activate the project venv or run:\n"
        "  python3 -m venv .venv && source .venv/bin/activate && pip install Pillow\n"
    )
    raise

REPO_ROOT = Path(__file__).resolve().parent.parent

APOLLO_NAVY      = (13, 17, 23)
APOLLO_NAVY_HIGH = (26, 39, 68)
APOLLO_TEXT      = (230, 237, 243)
APOLLO_TEAL      = (45, 212, 191)
APOLLO_GOLD      = (212, 175, 55)

DEFAULT_RES = (1920, 1080)
DEFAULT_FPS = 30
TITLE_DURATION_S = 5.0
END_DURATION_S = 3.0
TITLE_FADE_IN = 1.0
TITLE_HOLD = 3.0
TITLE_FADE_OUT = 1.0
END_FADE_IN = 0.5
END_HOLD = 2.0
END_FADE_OUT = 0.5

GRADE_CURVES = {
    "golden-hour": (
        "0/30 64/96 128/144 192/192 255/255",
        "0/35 64/90 128/138 192/188 255/255",
        "0/50 64/100 128/148 192/198 255/255",
    ),
    "teal": (
        "0/20 64/86 128/138 192/188 255/250",
        "0/30 64/94 128/142 192/192 255/255",
        "0/60 64/110 128/158 192/208 255/255",
    ),
}

DEFAULT_FONT = REPO_ROOT / "assets" / "fonts" / "Satoshi-Variable.ttf"
FONT_FALLBACKS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


@dataclass
class FontFamily:
    base_path: Path
    bold_path: Path | None = None
    medium_path: Path | None = None
    regular_path: Path | None = None

    @classmethod
    def resolve(cls, primary: Path) -> "FontFamily":
        primary = Path(primary)
        if not primary.exists():
            for fallback in FONT_FALLBACKS:
                if Path(fallback).exists():
                    primary = Path(fallback)
                    break
        family_dir = primary.parent
        return cls(
            base_path=primary,
            bold_path=_first_existing(family_dir / "Satoshi-Bold.otf"),
            medium_path=_first_existing(family_dir / "Satoshi-Medium.otf"),
            regular_path=_first_existing(family_dir / "Satoshi-Regular.otf"),
        )

    def load(self, size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
        candidates = {
            "bold": [self.bold_path, self.base_path],
            "medium": [self.medium_path, self.regular_path, self.base_path],
            "regular": [self.regular_path, self.base_path],
        }[weight]
        for path in candidates:
            if path and Path(path).exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except OSError:
                    continue
        return ImageFont.load_default()


def _first_existing(path: Path) -> Path | None:
    return path if path.exists() else None


def _ensure_ffmpeg() -> str:
    bin_path = shutil.which("ffmpeg")
    if not bin_path:
        raise SystemExit("ffmpeg is required and was not found on PATH.")
    return bin_path


def _run(cmd: list[str], *, verbose: bool = False) -> None:
    if verbose:
        print("$", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, capture_output=not verbose, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or "")
        raise SystemExit(f"command failed (exit {proc.returncode}): {cmd[0]}")


def _probe_video(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "json", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stream = json.loads(proc.stdout)["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    fps = round(float(num) / float(den))
    duration = float(stream.get("duration") or 0.0)
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "duration": duration,
    }


def _draw_gradient(
    size: tuple[int, int],
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
    *,
    teal_glow: tuple[float, float] | None = None,
) -> Image.Image:
    """Vertical navy gradient with an optional radial teal glow at (cx, cy) fractional pos."""
    w, h = size
    img = Image.new("RGB", size, top_color)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    if teal_glow is not None:
        cx, cy = teal_glow[0] * w, teal_glow[1] * h
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        gpx = glow.load()
        max_r = math.hypot(w, h) * 0.55
        for y in range(h):
            for x in range(w):
                d = math.hypot(x - cx, y - cy)
                a = max(0.0, 1.0 - d / max_r)
                alpha = int((a ** 2.5) * 90)
                if alpha:
                    gpx[x, y] = (*APOLLO_TEAL, alpha)
        glow = glow.filter(ImageFilter.GaussianBlur(radius=80))
        img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    return img


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox


def _draw_letter_spaced(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    spacing_px: int = 0,
) -> int:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), ch, font=font)
        x += (bbox[2] - bbox[0]) + spacing_px
    return x


def _render_title_frame(
    size: tuple[int, int],
    title: str,
    subtitle: str,
    kicker: str,
    fonts: FontFamily,
    alpha: float,
    *,
    end_card: bool = False,
) -> Image.Image:
    w, h = size
    if end_card:
        bg = _draw_gradient(size, APOLLO_NAVY, APOLLO_NAVY_HIGH, teal_glow=(0.5, 0.85))
    else:
        bg = _draw_gradient(size, APOLLO_NAVY_HIGH, APOLLO_NAVY, teal_glow=(0.72, 0.18))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    title_font = fonts.load(int(h * 0.085), weight="bold")
    sub_font = fonts.load(int(h * 0.026), weight="medium")
    kicker_font = fonts.load(int(h * 0.015), weight="medium")

    title_bbox = _text_size(draw, title, title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    title_x = (w - title_w) // 2 - title_bbox[0]
    title_y = (h - title_h) // 2 - int(h * 0.04) - title_bbox[1]
    a = int(alpha * 255)
    draw.text((title_x, title_y), title, font=title_font, fill=(*APOLLO_TEXT, a))

    if subtitle:
        sub_bbox = _text_size(draw, subtitle, sub_font)
        sub_w = sub_bbox[2] - sub_bbox[0]
        sub_x = (w - sub_w) // 2 - sub_bbox[0]
        sub_y = title_y + title_h + int(h * 0.025)
        draw.text((sub_x, sub_y), subtitle, font=sub_font, fill=(*APOLLO_TEAL, a))

    if kicker and not end_card:
        kicker_upper = kicker.upper()
        kicker_y = int(h * 0.92)
        kicker_x = int(w * 0.06)
        _draw_letter_spaced(
            draw,
            (kicker_x, kicker_y),
            kicker_upper,
            kicker_font,
            (*APOLLO_TEAL, a),
            spacing_px=2,
        )

    composed = Image.alpha_composite(bg.convert("RGBA"), layer).convert("RGB")
    return composed


def _alpha_curve(t: float, duration: float, fade_in: float, hold: float, fade_out: float) -> float:
    if t <= 0:
        return 0.0
    if t < fade_in:
        return t / fade_in
    if t < fade_in + hold:
        return 1.0
    if t < fade_in + hold + fade_out:
        return 1.0 - (t - fade_in - hold) / fade_out
    return 0.0


def render_card(
    out_mp4: Path,
    *,
    size: tuple[int, int],
    fps: int,
    duration_s: float,
    fade_in: float,
    hold: float,
    fade_out: float,
    title: str,
    subtitle: str,
    kicker: str,
    fonts: FontFamily,
    end_card: bool,
    verbose: bool = False,
) -> None:
    """Render a title or end card to MP4 (yuv420p, libx264 CRF 18)."""
    total_frames = int(round(duration_s * fps))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for i in range(total_frames):
            t = i / fps
            alpha = _alpha_curve(t, duration_s, fade_in, hold, fade_out)
            img = _render_title_frame(
                size, title, subtitle, kicker, fonts, alpha, end_card=end_card,
            )
            img.save(tmp_dir / f"frame_{i+1:04d}.png", "PNG")
        _ensure_ffmpeg()
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmp_dir / "frame_%04d.png"),
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_mp4),
        ]
        _run(cmd, verbose=verbose)


def _normalize_curve(spec: str) -> str:
    """Convert '0/30 64/96 ...' (8-bit pairs) to ffmpeg-curves '0/0.117 0.251/0.376 ...'."""
    out = []
    for pair in spec.split():
        x, y = pair.split("/")
        out.append(f"{float(x)/255:.4f}/{float(y)/255:.4f}")
    return " ".join(out)


def build_grade_filter(grade: str) -> str | None:
    if grade in ("off", "none"):
        return None
    if grade not in GRADE_CURVES:
        raise SystemExit(f"unknown grade: {grade}")
    r, g, b = (_normalize_curve(c) for c in GRADE_CURVES[grade])
    return f"curves=r='{r}':g='{g}':b='{b}'"


def build_filter_chain(*, grade: str, vignette: bool, grain: bool) -> str | None:
    parts: list[str] = []
    g = build_grade_filter(grade)
    if g:
        parts.append(g)
    if vignette:
        parts.append("vignette='PI/4.5':eval=init")
    if grain:
        parts.append("noise=alls=8:allf=t+u")
    return ",".join(parts) if parts else None


def apply_filters(
    input_mp4: Path,
    out_mp4: Path,
    *,
    filter_chain: str | None,
    verbose: bool = False,
) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(input_mp4)]
    if filter_chain:
        cmd += ["-vf", filter_chain]
    cmd += [
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        str(out_mp4),
    ]
    _run(cmd, verbose=verbose)


def concat_segments(segments: list[Path], out_mp4: Path, *, verbose: bool = False) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for seg in segments:
            f.write(f"file '{seg.resolve()}'\n")
        listfile = Path(f.name)
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(listfile),
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_mp4),
        ]
        _run(cmd, verbose=verbose)
    finally:
        listfile.unlink(missing_ok=True)


# ---------- caption rebuild (Phase 5 v2 path, --rerender-captions) ----------

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _parse_bold_segments(text: str) -> list[tuple[str, bool]]:
    segments: list[tuple[str, bool]] = []
    pos = 0
    for m in _BOLD_RE.finditer(text):
        if m.start() > pos:
            segments.append((text[pos:m.start()], False))
        segments.append((m.group(1), True))
        pos = m.end()
    if pos < len(text):
        segments.append((text[pos:], False))
    return segments


def caption_for_time(waypoints: list, duration: float, t: float) -> str:
    for i, wp in enumerate(waypoints):
        end = waypoints[i + 1]["t"] if i + 1 < len(waypoints) else duration
        if wp["t"] <= t < end:
            return wp.get("caption", "")
    return ""


def caption_alpha(
    waypoints: list, duration: float, t: float,
    *, fade_in: float = 0.3, fade_out: float = 0.4,
) -> float:
    for i, wp in enumerate(waypoints):
        end = waypoints[i + 1]["t"] if i + 1 < len(waypoints) else duration
        if wp["t"] <= t < end:
            local = t - wp["t"]
            remaining = end - t
            a_in = min(1.0, local / fade_in) if fade_in > 0 else 1.0
            a_out = min(1.0, remaining / fade_out) if fade_out > 0 else 1.0
            return max(0.0, min(a_in, a_out))
    return 0.0


def explicit_captions_at(captions: list[dict], t: float) -> list[tuple[dict, float, float]]:
    """Return all explicit captions active at time t.

    Each entry: (caption_dict, alpha, progress). Progress is 0..1 across the
    full caption duration (used by slide-in/typewriter/scale-up/pulse effects).
    Alpha incorporates fade_in/fade_out.
    """
    out: list[tuple[dict, float, float]] = []
    for c in captions:
        t0 = float(c["t"])
        dur = float(c["duration"])
        if dur <= 0:
            continue
        t1 = t0 + dur
        if not (t0 <= t < t1):
            continue
        local = t - t0
        remaining = t1 - t
        fi = float(c.get("fade_in", 0.3))
        fo = float(c.get("fade_out", 0.4))
        a_in = min(1.0, local / fi) if fi > 0 else 1.0
        a_out = min(1.0, remaining / fo) if fo > 0 else 1.0
        alpha = max(0.0, min(a_in, a_out))
        progress = local / dur
        out.append((c, alpha, progress))
    return out


def _render_caption_overlay(
    size: tuple[int, int],
    text: str,
    alpha: float,
    fonts: FontFamily,
) -> Image.Image:
    """Legacy entry point for waypoint-bound captions. Always lower-center / fade."""
    return _render_caption_layout(
        size=size, text=text, alpha=alpha, fonts=fonts,
        position="lower-center", effect="fade", progress=1.0, bold_word="", font_override="",
    )


def _resolve_font_family(fonts: FontFamily, override: str) -> FontFamily:
    """Honor a per-caption font override.

    The override may be (a) empty -> use default fonts, (b) a bundled Satoshi
    stem (e.g. "Satoshi-Bold"), or (c) an absolute path to a TTF/OTF.
    """
    if not override:
        return fonts
    candidate = Path(override)
    if not candidate.is_absolute() and not candidate.exists():
        # Treat as a stem inside the bundled fonts dir.
        bundled = REPO_ROOT / "assets" / "fonts" / override
        for suffix in ("", ".ttf", ".otf"):
            with_suffix = Path(str(bundled) + suffix)
            if with_suffix.exists():
                candidate = with_suffix
                break
    if not candidate.exists():
        print(f"[captions] warn: font override {override!r} not found; using default", flush=True)
        return fonts
    return FontFamily.resolve(candidate)


def _typewriter_visible(text: str, progress: float, fade_in: float, duration: float) -> str:
    """Reveal characters proportionally to elapsed fade_in (or 30% of duration if no fade_in)."""
    reveal_window = fade_in / duration if duration > 0 else 0.3
    reveal_window = max(0.1, min(0.9, reveal_window if reveal_window > 0 else 0.3))
    reveal_p = min(1.0, progress / reveal_window)
    chars_to_show = max(1, int(round(len(text) * reveal_p)))
    return text[:chars_to_show]


def _render_caption_layout(
    *,
    size: tuple[int, int],
    text: str,
    alpha: float,
    fonts: FontFamily,
    position: str,
    effect: str,
    progress: float,
    bold_word: str,
    font_override: str,
    fade_in_s: float = 0.3,
    duration_s: float = 3.5,
) -> Image.Image:
    """Render one caption layer at a given visual state.

    Inputs:
        size           — frame WxH (px)
        text           — caption text (markdown-style **bold** still respected)
        alpha          — 0..1 base opacity
        position       — lower-center | upper-center | left | right
        effect         — fade | slide-in | typewriter | scale-up | pulse
        progress       — 0..1 progress through the caption's full duration
        bold_word      — if non-empty, wraps that word in **markers** before rendering
        font_override  — empty, bundled stem, or abs path
        fade_in_s      — used by typewriter to size the reveal window
        duration_s     — full caption duration (used by pulse + typewriter)
    """
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    if not text or alpha <= 0:
        return overlay

    # Effect: typewriter truncates text by progress
    rendered_text = text
    if effect == "typewriter":
        rendered_text = _typewriter_visible(text, progress, fade_in_s, duration_s)

    # Optional inline bolding of a single word
    if bold_word and bold_word in rendered_text and "**" not in rendered_text:
        rendered_text = rendered_text.replace(bold_word, f"**{bold_word}**", 1)

    family = _resolve_font_family(fonts, font_override)
    font_size = max(14, int(h * 0.033))
    font_regular = family.load(font_size, weight="medium")
    font_bold = family.load(font_size, weight="bold")
    draw = ImageDraw.Draw(overlay)

    segments = _parse_bold_segments(rendered_text)
    total_w = 0
    measured = []
    for seg, is_bold in segments:
        f = font_bold if is_bold else font_regular
        bbox = draw.textbbox((0, 0), seg, font=f)
        seg_w = bbox[2] - bbox[0]
        seg_h = bbox[3] - bbox[1]
        measured.append((seg, is_bold, f, seg_w, seg_h, bbox))
        total_w += seg_w
    max_h = max((m[4] for m in measured), default=font_size)

    pad_x = max(14, int(font_size * 0.9))
    pad_y = max(8, int(font_size * 0.5))
    box_w = total_w + pad_x * 2
    box_h = max_h + pad_y * 2

    # Position resolution
    margin_y = int(h * 0.08)
    margin_x = int(w * 0.05)
    if position == "lower-center":
        anchor_x = (w - box_w) // 2
        anchor_y = h - box_h - margin_y
    elif position == "upper-center":
        anchor_x = (w - box_w) // 2
        anchor_y = margin_y
    elif position == "left":
        anchor_x = margin_x
        anchor_y = h - box_h - margin_y
    elif position == "right":
        anchor_x = w - box_w - margin_x
        anchor_y = h - box_h - margin_y
    else:
        anchor_x = (w - box_w) // 2
        anchor_y = h - box_h - margin_y

    # Effect: slide-in translates from edge during the first ~fade_in window
    if effect == "slide-in":
        slide_window = max(0.1, min(0.6, fade_in_s / duration_s if duration_s > 0 else 0.3))
        slide_p = min(1.0, progress / slide_window)
        offset = int((1.0 - slide_p) * (h * 0.06))
        if position == "upper-center":
            anchor_y -= offset
        elif position in ("lower-center", "left", "right"):
            anchor_y += offset

    # Effect: scale-up grows the box from 92% to 100% during fade_in
    scale = 1.0
    if effect == "scale-up":
        scale_window = max(0.1, min(0.6, fade_in_s / duration_s if duration_s > 0 else 0.3))
        scale_p = min(1.0, progress / scale_window)
        scale = 0.92 + 0.08 * scale_p
    elif effect == "pulse":
        # Single subtle sine pulse centered at mid-caption
        import math as _math
        scale = 1.0 + 0.03 * _math.sin(_math.pi * progress)

    box_x = anchor_x
    box_y = anchor_y
    if scale != 1.0:
        # Render into a scratch and resize-then-composite
        scratch = _render_caption_layout(
            size=size, text=text if effect != "typewriter" else rendered_text,
            alpha=alpha, fonts=fonts, position=position, effect="fade",
            progress=progress, bold_word=bold_word, font_override=font_override,
            fade_in_s=fade_in_s, duration_s=duration_s,
        )
        # Compute the box bbox to scale around its center
        new_w = max(1, int(box_w * scale))
        new_h = max(1, int(box_h * scale))
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        sub = scratch.crop((box_x, box_y, box_x + box_w, box_y + box_h)).resize(
            (new_w, new_h), resampling
        )
        cx = box_x + box_w // 2
        cy = box_y + box_h // 2
        out = Image.new("RGBA", size, (0, 0, 0, 0))
        out.alpha_composite(sub, dest=(cx - new_w // 2, cy - new_h // 2))
        return out

    a = int(alpha * 255)
    shadow = Image.new("RGBA", (box_w + 24, box_h + 24), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (12, 12, box_w + 12, box_h + 12),
        radius=16, fill=(0, 0, 0, int(alpha * 110)),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))
    overlay.alpha_composite(shadow, dest=(box_x - 12, box_y - 12))

    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_w, box_y + box_h),
        radius=16, fill=(0, 0, 0, int(alpha * 0.65 * 255)),
    )

    x = box_x + pad_x
    for seg, is_bold, f, seg_w, seg_h, bbox in measured:
        text_x = x - bbox[0]
        text_y = box_y + (box_h - seg_h) // 2 - bbox[1]
        color = (*APOLLO_TEAL, a) if is_bold else (255, 255, 255, a)
        draw.text((text_x, text_y), seg, font=f, fill=color)
        x += seg_w
    return overlay


def rerender_captions(
    input_mp4: Path,
    out_mp4: Path,
    *,
    cinematic: dict,
    fonts: FontFamily,
    verbose: bool = False,
) -> None:
    """Extract frames, overlay animated captions from JSON, re-encode.

    Caption resolution order per frame:
      1. Explicit captions: array (new schema; full effect/position/font support).
      2. Waypoint-bound captions (legacy shorthand from shots.yaml).
    Explicit captions take precedence; waypoint captions only render when no
    explicit caption is active at that timestamp.
    """
    spec = _probe_video(input_mp4)
    size = (spec["width"], spec["height"])
    fps = spec["fps"]
    waypoints = cinematic["waypoints"]
    explicit = cinematic.get("captions") or []
    duration = float(cinematic["durationSec"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        frames_dir = tmp_dir / "frames"
        frames_dir.mkdir()
        _ensure_ffmpeg()
        _run(
            [
                "ffmpeg", "-y", "-i", str(input_mp4),
                "-vsync", "0",
                str(frames_dir / "frame_%04d.png"),
            ],
            verbose=verbose,
        )
        for frame in sorted(frames_dir.glob("frame_*.png")):
            idx = int(frame.stem.split("_")[-1])
            t = (idx - 1) / fps

            active = explicit_captions_at(explicit, t) if explicit else []
            overlays: list[Image.Image] = []

            if active:
                for caption_dict, c_alpha, c_progress in active:
                    if c_alpha <= 0:
                        continue
                    overlays.append(_render_caption_layout(
                        size=size,
                        text=caption_dict["text"],
                        alpha=c_alpha,
                        fonts=fonts,
                        position=caption_dict.get("position", "lower-center"),
                        effect=caption_dict.get("effect", "fade"),
                        progress=c_progress,
                        bold_word=caption_dict.get("bold_word", ""),
                        font_override=caption_dict.get("font", ""),
                        fade_in_s=float(caption_dict.get("fade_in", 0.3)),
                        duration_s=float(caption_dict.get("duration", 3.5)),
                    ))
            else:
                text = caption_for_time(waypoints, duration, t)
                alpha = caption_alpha(waypoints, duration, t)
                if text and alpha > 0:
                    overlays.append(_render_caption_overlay(size, text, alpha, fonts))

            if not overlays:
                continue
            with Image.open(frame) as base:
                base = base.convert("RGBA")
                composed = base
                for ov in overlays:
                    composed = Image.alpha_composite(composed, ov)
                composed.convert("RGB").save(frame, "PNG")
        _run(
            [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(frames_dir / "frame_%04d.png"),
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(out_mp4),
            ],
            verbose=verbose,
        )


# ---------- pipeline ----------

@dataclass
class PipelineConfig:
    input_mp4: Path
    output_mp4: Path
    title: str
    subtitle: str
    end_title: str
    end_subtitle: str
    kicker: str
    fonts: FontFamily
    grade: str = "golden-hour"
    vignette: bool = True
    grain: bool = True
    rerender_captions: bool = False
    cinematic: dict | None = None
    fps: int | None = None
    size: tuple[int, int] | None = None
    keep_intermediates: bool = False
    verbose: bool = False


def run_pipeline(cfg: PipelineConfig) -> Path:
    spec = _probe_video(cfg.input_mp4)
    size = cfg.size or (spec["width"], spec["height"])
    fps = cfg.fps or spec["fps"]
    work_root = cfg.output_mp4.parent / f"._post_{cfg.output_mp4.stem}"
    work_root.mkdir(parents=True, exist_ok=True)
    try:
        middle = cfg.input_mp4
        if cfg.rerender_captions:
            if not cfg.cinematic:
                raise SystemExit("--rerender-captions requires --captions to resolve a cinematic")
            recap = work_root / "captions.mp4"
            print(f"[1/4] rebuilding captions → {recap.name}", flush=True)
            rerender_captions(middle, recap, cinematic=cfg.cinematic, fonts=cfg.fonts, verbose=cfg.verbose)
            middle = recap

        graded = work_root / "graded.mp4"
        filter_chain = build_filter_chain(grade=cfg.grade, vignette=cfg.vignette, grain=cfg.grain)
        print(f"[2/4] applying grade/vignette/grain → {graded.name}", flush=True)
        if filter_chain is None:
            shutil.copy2(middle, graded)
        else:
            apply_filters(middle, graded, filter_chain=filter_chain, verbose=cfg.verbose)

        title_mp4 = work_root / "title.mp4"
        end_mp4 = work_root / "end.mp4"
        print(f"[3/4] rendering title + end cards", flush=True)
        render_card(
            title_mp4, size=size, fps=fps,
            duration_s=TITLE_DURATION_S,
            fade_in=TITLE_FADE_IN, hold=TITLE_HOLD, fade_out=TITLE_FADE_OUT,
            title=cfg.title, subtitle=cfg.subtitle, kicker=cfg.kicker,
            fonts=cfg.fonts, end_card=False, verbose=cfg.verbose,
        )
        render_card(
            end_mp4, size=size, fps=fps,
            duration_s=END_DURATION_S,
            fade_in=END_FADE_IN, hold=END_HOLD, fade_out=END_FADE_OUT,
            title=cfg.end_title, subtitle=cfg.end_subtitle, kicker="",
            fonts=cfg.fonts, end_card=True, verbose=cfg.verbose,
        )

        print(f"[4/4] concatenating → {cfg.output_mp4.name}", flush=True)
        concat_segments([title_mp4, graded, end_mp4], cfg.output_mp4, verbose=cfg.verbose)
        return cfg.output_mp4
    finally:
        if not cfg.keep_intermediates:
            shutil.rmtree(work_root, ignore_errors=True)


# ---------- caption resolution ----------

def _resolve_cinematic(captions: str | None, default_name: str | None = None) -> tuple[dict | None, str | None]:
    """Parse --captions path[#name]; returns (cinematic_dict, name)."""
    if not captions:
        return None, None
    if "#" in captions:
        path_str, name = captions.split("#", 1)
    else:
        path_str, name = captions, default_name
    data = json.loads(Path(path_str).read_text())
    if not name:
        return data, None
    cinematic = data["cinematics"][name]
    return cinematic, name


# ---------- CLI ----------

def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--font", default=str(DEFAULT_FONT), help="path to TTF/OTF (Satoshi-Variable.ttf by default)")
    p.add_argument("--grade", default="golden-hour", choices=["golden-hour", "teal", "off", "none"])
    p.add_argument("--vignette", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--grain", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--rerender-captions", action="store_true",
                   help="rebuild captions from JSON (default off: existing v1 burns stay)")
    p.add_argument("--keep-intermediates", action="store_true")
    p.add_argument("--verbose", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apollo LNG cinematics post-production")
    sub = parser.add_subparsers(dest="cmd")

    single = sub.add_parser("single", help="single-file post-production (default if no subcommand)")
    single.add_argument("--input", required=True, type=Path)
    single.add_argument("--output", required=True, type=Path)
    single.add_argument("--captions", default=None,
                        help="path/to/cinematics.json#name for caption rebuild or kicker labelling")
    single.add_argument("--title", default="Apollo LNG · Option E")
    single.add_argument("--subtitle", default="")
    single.add_argument("--end-title", default="Apollo Energy Group · LNG Solutions")
    single.add_argument("--end-subtitle", default="walker@apollogroup.energy")
    single.add_argument("--kicker", default="DRONE FLYTHROUGH · OPTION E")
    _add_common_args(single)

    batch = sub.add_parser("batch", help="batch over a directory of cinematics")
    batch.add_argument("--input-dir", required=True, type=Path)
    batch.add_argument("--output-dir", required=True, type=Path)
    batch.add_argument("--captions", default=None,
                       help="path/to/cinematics.json (per-clip lookup by filename)")
    batch.add_argument("--title", default="Apollo LNG · Option E")
    batch.add_argument("--subtitle", default=None,
                       help="override; default is the per-clip JSON label")
    batch.add_argument("--end-title", default="Apollo Energy Group · LNG Solutions")
    batch.add_argument("--end-subtitle", default="walker@apollogroup.energy")
    batch.add_argument("--kicker", default="DRONE FLYTHROUGH · OPTION E")
    batch.add_argument("--prefix", default="option-e-",
                       help="filename prefix used to derive clip name")
    _add_common_args(batch)

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 2

    fonts = FontFamily.resolve(Path(args.font))

    if args.cmd == "single":
        cinematic, _ = _resolve_cinematic(args.captions)
        if args.captions and "#" not in args.captions:
            print("[warn] --captions has no #name; not using for caption rebuild", flush=True)
            cinematic = None
        cfg = PipelineConfig(
            input_mp4=args.input,
            output_mp4=args.output,
            title=args.title,
            subtitle=args.subtitle,
            end_title=args.end_title,
            end_subtitle=args.end_subtitle,
            kicker=args.kicker,
            fonts=fonts,
            grade=args.grade,
            vignette=args.vignette,
            grain=args.grain,
            rerender_captions=args.rerender_captions,
            cinematic=cinematic,
            keep_intermediates=args.keep_intermediates,
            verbose=args.verbose,
        )
        out = run_pipeline(cfg)
        print(f"✓ wrote {out}", flush=True)
        return 0

    if args.cmd == "batch":
        in_dir: Path = args.input_dir
        out_dir: Path = args.output_dir
        if not in_dir.is_dir():
            raise SystemExit(f"--input-dir not a directory: {in_dir}")
        captions_data: dict | None = None
        if args.captions:
            captions_data = json.loads(Path(args.captions).read_text())
        clips = sorted(p for p in in_dir.glob(f"{args.prefix}*.mp4") if p.is_file())
        if not clips:
            raise SystemExit(f"no MP4s matched {args.prefix}*.mp4 in {in_dir}")
        for clip in clips:
            name = clip.stem[len(args.prefix):] if clip.stem.startswith(args.prefix) else clip.stem
            cinematic = None
            subtitle = args.subtitle
            if captions_data and name in captions_data.get("cinematics", {}):
                cinematic = captions_data["cinematics"][name]
                if subtitle is None:
                    subtitle = cinematic.get("label", "")
            if subtitle is None:
                subtitle = ""
            out_path = out_dir / clip.name
            print(f"\n=== {clip.name} → {out_path} ===", flush=True)
            cfg = PipelineConfig(
                input_mp4=clip,
                output_mp4=out_path,
                title=args.title,
                subtitle=subtitle,
                end_title=args.end_title,
                end_subtitle=args.end_subtitle,
                kicker=args.kicker,
                fonts=fonts,
                grade=args.grade,
                vignette=args.vignette,
                grain=args.grain,
                rerender_captions=args.rerender_captions,
                cinematic=cinematic,
                keep_intermediates=args.keep_intermediates,
                verbose=args.verbose,
            )
            run_pipeline(cfg)
        print(f"\n✓ wrote {len(clips)} polished MP4s to {out_dir}", flush=True)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
