"""Shot-list DSL compiler — turns shots.yaml into cinematic JSON.

Per spec: docs/superpowers/specs/2026-05-25-shot-list-dsl-design.md
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional

from lib.shot_types import COMPASS_DIRS, DEFAULTS  # pyright: ignore[reportMissingImports]


# Compass unit vectors (xy plane, z=0)
_SQRT2_OVER_2 = math.sqrt(2) / 2
_COMPASS_UNIT = {
    "N":  (0.0,            1.0,            0.0),
    "NE": ( _SQRT2_OVER_2,  _SQRT2_OVER_2, 0.0),
    "E":  (1.0,            0.0,            0.0),
    "SE": ( _SQRT2_OVER_2, -_SQRT2_OVER_2, 0.0),
    "S":  (0.0,           -1.0,            0.0),
    "SW": (-_SQRT2_OVER_2, -_SQRT2_OVER_2, 0.0),
    "W":  (-1.0,           0.0,            0.0),
    "NW": (-_SQRT2_OVER_2,  _SQRT2_OVER_2, 0.0),
}


def offset(
    subject: tuple[float, float, float],
    direction: str,
    distance: float,
    height: float,
) -> tuple[float, float, float]:
    """Compute camera position offset from a subject in a compass direction.

    `direction` must be one of the 8 compass tokens. Z (height) replaces
    the subject's z entirely — height is absolute, not relative to subject.
    """
    if direction not in _COMPASS_UNIT:
        raise ValueError(
            f"invalid direction {direction!r}; expected one of {COMPASS_DIRS}"
        )
    ux, uy, _ = _COMPASS_UNIT[direction]
    sx, sy, _ = subject
    return (sx + ux * distance, sy + uy * distance, height)


@dataclass(frozen=True)
class Shot:
    """One shot from a .shots.yaml file (after type/required-field validation)."""
    type: str
    dur: float
    subject: str
    caption: str = ""
    from_dir: str = "S"
    focal: Optional[int] = None
    distance: Optional[float] = None
    height: Optional[float] = None
    ease: Optional[str] = None


@dataclass(frozen=True)
class Waypoint:
    """One waypoint in the emitted cinematic JSON."""
    t: float
    pos: tuple[float, float, float]
    lookAt: tuple[float, float, float]
    focal: int
    ease: str
    feature: str
    caption: str


def _lookat_for(subject_pos: tuple[float, float, float]) -> tuple[float, float, float]:
    """Default lookAt: 1.5m above subject footprint (eye-level on equipment)."""
    return (subject_pos[0], subject_pos[1], subject_pos[2] + 1.5)


def _ease_for(shot: Shot, fallback: str) -> str:
    return shot.ease or fallback


def compile_wide(shot, start_t, subject_pos):
    """One waypoint, SE-aerial at fixed scale."""
    d = DEFAULTS["wide"]
    distance = shot.distance if shot.distance is not None else d.distance
    height = shot.height if shot.height is not None else d.height
    pos = offset(subject_pos, "SE", distance, height)
    lookat = (subject_pos[0], subject_pos[1], subject_pos[2] + 5.0)
    return [Waypoint(
        t=float(start_t), pos=pos, lookAt=lookat,
        focal=shot.focal or d.focal,
        ease=_ease_for(shot, d.ease),
        feature=shot.subject, caption=shot.caption,
    )]


def _push_pull(shot, start_t, subject_pos, *, reverse: bool):
    """Shared body for push (far→close) and pull (close→far)."""
    d = DEFAULTS["push"] if not reverse else DEFAULTS["pull"]
    near_dist, far_dist = 25.0, 50.0
    near_h, far_h = 8.0, 12.0
    if reverse:
        d0, d1 = near_dist, far_dist
        h0, h1 = near_h, far_h
        f0, f1 = 42, 35
    else:
        d0, d1 = far_dist, near_dist
        h0, h1 = far_h, near_h
        f0, f1 = 35, 42
    if shot.distance is not None:
        d0 = d1 = shot.distance
    if shot.height is not None:
        h0 = h1 = shot.height
    if shot.focal is not None:
        f0 = f1 = shot.focal
    lookat = _lookat_for(subject_pos)
    ease = _ease_for(shot, d.ease)
    return [
        Waypoint(t=float(start_t),         pos=offset(subject_pos, shot.from_dir, d0, h0),
                 lookAt=lookat, focal=f0, ease=ease,
                 feature=shot.subject, caption=shot.caption),
        Waypoint(t=float(start_t + shot.dur), pos=offset(subject_pos, shot.from_dir, d1, h1),
                 lookAt=lookat, focal=f1, ease=ease,
                 feature=shot.subject, caption=shot.caption),
    ]


def compile_push(shot, start_t, subject_pos):
    return _push_pull(shot, start_t, subject_pos, reverse=False)


def compile_pull(shot, start_t, subject_pos):
    return _push_pull(shot, start_t, subject_pos, reverse=True)


def compile_hero(shot, start_t, subject_pos):
    """Two waypoints with subtle drift — Ken-Burns feel."""
    d = DEFAULTS["hero"]
    dist = shot.distance if shot.distance is not None else d.distance
    h = shot.height if shot.height is not None else d.height
    focal = shot.focal or d.focal
    lookat = _lookat_for(subject_pos)
    ease = _ease_for(shot, d.ease)
    return [
        Waypoint(t=float(start_t),          pos=offset(subject_pos, "SW", dist, h),
                 lookAt=lookat, focal=focal, ease=ease,
                 feature=shot.subject, caption=shot.caption),
        Waypoint(t=float(start_t + shot.dur), pos=offset(subject_pos, "SW", dist + 2, h + 1),
                 lookAt=lookat, focal=focal, ease=ease,
                 feature=shot.subject, caption=shot.caption),
    ]


def compile_pan(shot, start_t, subject_pos):
    """Sweeping arc SW → SE around the subject."""
    d = DEFAULTS["pan"]
    dist = shot.distance if shot.distance is not None else d.distance
    h = shot.height if shot.height is not None else d.height
    focal = shot.focal or d.focal
    lookat = _lookat_for(subject_pos)
    ease = _ease_for(shot, d.ease)
    return [
        Waypoint(t=float(start_t),          pos=offset(subject_pos, "SW", dist, h),
                 lookAt=lookat, focal=focal, ease=ease,
                 feature=shot.subject, caption=shot.caption),
        Waypoint(t=float(start_t + shot.dur), pos=offset(subject_pos, "SE", dist, h),
                 lookAt=lookat, focal=focal, ease=ease,
                 feature=shot.subject, caption=shot.caption),
    ]


def compile_orbit(shot, start_t, subject_pos):
    """N waypoints, one per quarter-turn (every ~3 seconds)."""
    d = DEFAULTS["orbit"]
    dist = shot.distance if shot.distance is not None else d.distance
    h = shot.height if shot.height is not None else d.height
    focal = shot.focal or d.focal
    ease = _ease_for(shot, "linear")  # orbits feel steadier with linear
    n_segments = max(1, math.ceil(shot.dur / 3.0))
    n_waypoints = n_segments + 1
    lookat = (subject_pos[0], subject_pos[1], subject_pos[2] + 2.0)
    wps = []
    for i in range(n_waypoints):
        angle = (i / n_segments) * 2 * math.pi
        t = start_t + (i / n_segments) * shot.dur
        px = subject_pos[0] + math.cos(angle) * dist
        py = subject_pos[1] + math.sin(angle) * dist
        wps.append(Waypoint(
            t=float(t), pos=(px, py, h), lookAt=lookat,
            focal=focal, ease=ease,
            feature=shot.subject, caption=shot.caption,
        ))
    return wps


def compile_fly(shot, start_t, subject_pos):
    """High+far → mid+close moving aerial pass."""
    d = DEFAULTS["fly"]
    start_dist = shot.distance if shot.distance is not None else 80.0
    start_h    = shot.height   if shot.height   is not None else 40.0
    end_dist = max(start_dist - 50.0, 15.0)
    end_h    = max(start_h - 25.0,    8.0)
    focal = shot.focal or d.focal
    lookat = (subject_pos[0], subject_pos[1], subject_pos[2] + 2.0)
    ease = _ease_for(shot, d.ease)
    return [
        Waypoint(t=float(start_t),          pos=offset(subject_pos, shot.from_dir, start_dist, start_h),
                 lookAt=lookat, focal=focal, ease=ease,
                 feature=shot.subject, caption=shot.caption),
        Waypoint(t=float(start_t + shot.dur), pos=offset(subject_pos, shot.from_dir, end_dist, end_h),
                 lookAt=lookat, focal=focal, ease=ease,
                 feature=shot.subject, caption=shot.caption),
    ]


def compile_land(shot, start_t, subject_pos):
    """One waypoint at the end of the shot's duration — final settling pose."""
    d = DEFAULTS["land"]
    dist = shot.distance if shot.distance is not None else d.distance
    h = shot.height if shot.height is not None else d.height
    focal = shot.focal or d.focal
    lookat = (subject_pos[0], subject_pos[1], subject_pos[2] + 2.0)
    ease = _ease_for(shot, d.ease)
    return [Waypoint(
        t=float(start_t + shot.dur),
        pos=offset(subject_pos, "SE", dist, h),
        lookAt=lookat, focal=focal, ease=ease,
        feature=shot.subject, caption=shot.caption,
    )]


def compile_hold(shot, start_t, subject_pos):
    """No waypoints — extends the timeline by shot.dur via interpolation."""
    del shot, start_t, subject_pos  # required by COMPILERS signature; intentional no-op
    return []


COMPILERS = {
    "wide": compile_wide,
    "push": compile_push,
    "pull": compile_pull,
    "hero": compile_hero,
    "pan":  compile_pan,
    "orbit": compile_orbit,
    "fly":  compile_fly,
    "land": compile_land,
    "hold": compile_hold,
}


# ---------- orchestrator: yaml file → cinematic JSON dict ----------

from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402  # pyright: ignore[reportMissingModuleSource]

from lib.site_config import load_site, Site  # pyright: ignore[reportMissingImports]  # noqa: E402
from lib.shot_types import SHOT_TYPES  # pyright: ignore[reportMissingImports]  # noqa: E402


class ShotListError(ValueError):
    """Raised on malformed shots YAML."""


def _resolve_anchors(site: "Site") -> dict[str, tuple[float, float, float]]:
    """Map anchor name → 3-tuple position from the site YAML."""
    anchors: dict[str, tuple[float, float, float]] = {}
    for eq in site.equipment:
        anchors[eq.id] = eq.pos
    # isoArrayCenter: center of the ISO grid
    ox, oy, oz = site.iso_array.origin
    SX, SY = 15.5, 5.2  # match scripts/lib/site_config.py + renderer convention
    anchors["isoArrayCenter"] = (
        ox + (site.iso_array.cols - 1) * SX / 2.0,
        oy + (site.iso_array.rows - 1) * SY / 2.0,
        oz + 1.45,
    )
    # `site`: geometric centroid of all anchors so wide/orbit/etc. have a default subject
    pts = list(anchors.values())
    if pts:
        anchors["site"] = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
            0.0,
        )
    return anchors


def _shot_from_dict(raw: dict, idx: int) -> Shot:
    """Validate + normalize one shot entry."""
    for key in ("type", "dur", "subject"):
        if key not in raw:
            raise ShotListError(f"shot[{idx}] missing required field '{key}'")
    if raw["type"] not in SHOT_TYPES:
        raise ShotListError(
            f"shot[{idx}] unknown type {raw['type']!r}; allowed: {sorted(SHOT_TYPES)}"
        )
    if not isinstance(raw["dur"], (int, float)) or raw["dur"] <= 0:
        raise ShotListError(f"shot[{idx}] dur must be a positive number, got {raw['dur']!r}")
    from_dir = raw.get("from", "S")
    if from_dir not in _COMPASS_UNIT:
        raise ShotListError(f"shot[{idx}] from {from_dir!r} invalid; use N|NE|E|SE|S|SW|W|NW")
    return Shot(
        type=raw["type"],
        dur=float(raw["dur"]),
        subject=str(raw["subject"]),
        caption=str(raw.get("caption", "")),
        from_dir=from_dir,
        focal=int(raw["focal"]) if "focal" in raw else None,
        distance=float(raw["distance"]) if "distance" in raw else None,
        height=float(raw["height"]) if "height" in raw else None,
        ease=raw.get("ease"),
    )


VALID_CAPTION_POSITIONS = ("lower-center", "upper-center", "left", "right")
VALID_CAPTION_EFFECTS = ("fade", "slide-in", "typewriter", "scale-up", "pulse")


def _compile_cinematic(name: str, body: dict, anchors: dict, velocity_cap: Optional[float] = None) -> dict:
    shots_raw = body.get("shots") or []
    if not shots_raw:
        raise ShotListError(f"cinematic {name!r} has no shots")

    waypoints = []
    t = 0.0
    for i, raw in enumerate(shots_raw):
        shot = _shot_from_dict(raw, i)
        if shot.subject not in anchors:
            raise ShotListError(
                f"cinematic {name!r} shot[{i}]: unknown subject {shot.subject!r}; "
                f"known anchors: {sorted(anchors)}"
            )
        subject_pos = anchors[shot.subject]
        new_wps = COMPILERS[shot.type](shot, start_t=t, subject_pos=subject_pos)
        # Renderer requires strictly-ascending timestamps. When back-to-back shots
        # both emit a waypoint at the same join time, drop the previous shot's
        # end pose — the new shot's start pose takes precedence at the boundary.
        if waypoints and new_wps and round(new_wps[0].t, 3) == waypoints[-1]["t"]:
            waypoints.pop()
        for wp in new_wps:
            waypoints.append({
                "t": round(wp.t, 3),
                "pos": [round(x, 3) for x in wp.pos],
                "lookAt": [round(x, 3) for x in wp.lookAt],
                "focal": wp.focal,
                "ease": wp.ease,
                "feature": wp.feature,
                "caption": wp.caption,
            })
        t += shot.dur

    duration = round(t, 3)
    velocity_report = None
    if velocity_cap and velocity_cap > 0 and len(waypoints) > 1:
        waypoints, duration, velocity_report = _retime_velocity(name, waypoints, duration, velocity_cap)

    captions_block = _compile_captions(name, body.get("captions") or [], duration)

    out = {
        "label": body.get("label", name),
        "description": body.get("description", ""),
        "durationSec": duration,
        "waypoints": waypoints,
        "captions": captions_block,
    }
    if velocity_report is not None:
        out["velocityReport"] = velocity_report
    return out


def _compile_captions(cinematic_name: str, raw_entries: list, duration: float) -> list[dict]:
    """Parse a `captions:` list. Each entry can be a string (shorthand) or a mapping.

    Mapping fields (all optional except `text` and `t`):
        text       (str)             — the caption text
        t          (float, seconds)  — when the caption starts
        duration   (float, seconds)  — how long it shows. Default 3.5s.
        fade_in    (float, seconds)  — default 0.3s
        fade_out   (float, seconds)  — default 0.4s
        position   (str)             — lower-center (default) | upper-center | left | right
        font       (str)             — bundled stem (e.g. "Satoshi-Bold") or absolute TTF path
        effect     (str)             — fade (default) | slide-in | typewriter | scale-up | pulse
        bold_word  (str)             — optional word to highlight in teal
    """
    out: list[dict] = []
    for idx, raw in enumerate(raw_entries):
        if isinstance(raw, str):
            raise ShotListError(
                f"cinematic {cinematic_name!r} caption[{idx}]: string shorthand requires explicit t — "
                f"use a mapping {{text: '...', t: <sec>}}."
            )
        if not isinstance(raw, dict):
            raise ShotListError(f"cinematic {cinematic_name!r} caption[{idx}] must be a mapping or string, got {type(raw).__name__}")
        text = raw.get("text")
        if not text or not isinstance(text, str):
            # An empty placeholder for Walker to fill in. Skip but warn.
            print(f"[captions] {cinematic_name}: caption[{idx}] has no text — skipping (placeholder?)", flush=True)
            continue
        if "t" not in raw:
            raise ShotListError(f"cinematic {cinematic_name!r} caption[{idx}] missing required 't' (seconds from cinematic start)")
        try:
            t = float(raw["t"])
        except (TypeError, ValueError):
            raise ShotListError(f"cinematic {cinematic_name!r} caption[{idx}] t must be numeric, got {raw['t']!r}")
        if t < 0 or t > duration + 0.001:
            raise ShotListError(
                f"cinematic {cinematic_name!r} caption[{idx}] t={t} outside cinematic range 0..{duration}s"
            )
        dur = float(raw.get("duration", 3.5))
        if dur <= 0:
            raise ShotListError(f"cinematic {cinematic_name!r} caption[{idx}] duration must be positive, got {dur}")
        fade_in = float(raw.get("fade_in", 0.3))
        fade_out = float(raw.get("fade_out", 0.4))
        if fade_in < 0 or fade_out < 0:
            raise ShotListError(f"cinematic {cinematic_name!r} caption[{idx}] fade values must be >= 0")
        position = raw.get("position", "lower-center")
        if position not in VALID_CAPTION_POSITIONS:
            raise ShotListError(
                f"cinematic {cinematic_name!r} caption[{idx}] position {position!r} invalid; "
                f"allowed: {VALID_CAPTION_POSITIONS}"
            )
        effect = raw.get("effect", "fade")
        if effect not in VALID_CAPTION_EFFECTS:
            raise ShotListError(
                f"cinematic {cinematic_name!r} caption[{idx}] effect {effect!r} invalid; "
                f"allowed: {VALID_CAPTION_EFFECTS}"
            )
        font = raw.get("font") or ""
        bold_word = raw.get("bold_word") or ""
        out.append({
            "text": text,
            "t": round(t, 3),
            "duration": round(dur, 3),
            "fade_in": round(fade_in, 3),
            "fade_out": round(fade_out, 3),
            "position": position,
            "font": str(font),
            "effect": effect,
            "bold_word": str(bold_word),
        })
    # Sort by start time so the renderer can short-circuit cleanly.
    out.sort(key=lambda c: c["t"])
    return out


def _retime_velocity(name: str, waypoints: list, duration: float, cap: float) -> tuple[list, float, dict]:
    """Stretch fast segments so no segment exceeds `cap` m/s.

    Algorithm: walk waypoint pairs left-to-right using the ORIGINAL deltas
    to compute per-segment velocity. Where v > cap, stretch that segment's
    dt so v = cap; the cumulative new-time series is monotonic by construction
    because every dt is positive. Total durationSec grows by the accumulated
    stretch.

    Returns (waypoints, new_duration, report). Report carries per-segment
    velocities (before + after) so callers and tools can show what changed.
    """
    n = len(waypoints)
    orig_t = [wp["t"] for wp in waypoints]
    new_t = [orig_t[0]]
    per_segment: list[dict] = []
    max_v_before = 0.0
    retimed_count = 0
    for i in range(1, n):
        dt = orig_t[i] - orig_t[i - 1]
        if dt <= 0:
            # Degenerate join — preserve order without retiming.
            new_t.append(new_t[-1])
            per_segment.append({"i": i - 1, "dt_before": dt, "dist": 0.0,
                                "v_before": 0.0, "v_after": 0.0, "retimed": False, "degenerate": True})
            continue
        ax, ay, az = waypoints[i - 1]["pos"]
        bx, by, bz = waypoints[i]["pos"]
        dist = math.sqrt((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2)
        v_before = dist / dt
        max_v_before = max(max_v_before, v_before)
        if v_before > cap:
            new_dt = dist / cap
            retimed_count += 1
            v_after = cap
        else:
            new_dt = dt
            v_after = v_before
        new_t.append(new_t[-1] + new_dt)
        per_segment.append({
            "i": i - 1,
            "dt_before": round(dt, 3),
            "dt_after": round(new_dt, 3),
            "dist": round(dist, 3),
            "v_before": round(v_before, 3),
            "v_after": round(v_after, 3),
            "retimed": v_before > cap,
        })
    # Apply new times back into the waypoint dicts.
    for i, t in enumerate(new_t):
        waypoints[i]["t"] = round(t, 3)

    new_duration = round(new_t[-1], 3) if new_t else duration
    report = {
        "cap": cap,
        "max_v_before": round(max_v_before, 3),
        "retimed_segments": retimed_count,
        "duration_growth_sec": round(new_duration - duration, 3),
        "per_segment": per_segment,
    }
    if retimed_count:
        print(
            f"[velocity-retime] {name}: capped {retimed_count} segment(s) at {cap} m/s; "
            f"max v was {max_v_before:.2f} m/s; durationSec {duration:.2f}→{new_duration:.2f}",
            flush=True,
        )
    return waypoints, new_duration, report


def compile_shotlist(path) -> dict:
    """Read a .shots.yaml and return the cinematic JSON dict (ready to dump)."""
    path = Path(path)
    if not path.exists():
        raise ShotListError(f"shots file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ShotListError(f"{path}: top-level must be a mapping")

    site_id = raw.get("site")
    if not site_id:
        raise ShotListError(f"{path}: missing top-level 'site:'")
    # Walk upward from the shots file to find the project root (the dir
    # containing a `sites/` subfolder). Falls back to the file's parent
    # parent so relative real-world layouts still work.
    project_root: Optional[Path] = None
    for candidate in path.resolve().parents:
        if (candidate / "sites").is_dir():
            project_root = candidate
            break
    if project_root is None:
        project_root = path.resolve().parents[1] if len(path.resolve().parents) > 1 else path.resolve().parent
    site_yaml = project_root / "sites" / f"{site_id}.yaml"
    site = load_site(site_yaml)
    anchors = _resolve_anchors(site)

    cinematics_raw = raw.get("cinematics") or {}
    if not isinstance(cinematics_raw, dict) or not cinematics_raw:
        raise ShotListError(f"{path}: missing or empty 'cinematics:' block")

    global_velocity_cap = _coerce_velocity_cap(raw.get("velocity_cap"))

    out_cinematics: dict[str, dict] = {}
    for name, body in cinematics_raw.items():
        if not isinstance(body, dict):
            raise ShotListError(f"{path}: cinematic {name!r} must be a mapping")
        # Per-cinematic override possible; falls back to global.
        local_cap = _coerce_velocity_cap(body.get("velocity_cap"))
        cap = local_cap if local_cap is not None else global_velocity_cap
        out_cinematics[name] = _compile_cinematic(name, body, anchors, velocity_cap=cap)

    return {
        "source": f"Compiled from {path} on {datetime.now().isoformat(timespec='seconds')}",
        "fps": int(raw.get("fps", 30)),
        "resolution": list(raw.get("resolution", [1920, 1080])),
        "blendFile": raw.get("blendFile", f"models/lng-site/{site_id}.blend"),
        "glbFile": raw.get("glbFile", f"models/lng-site/{site_id}.glb"),
        "velocityCap": global_velocity_cap,
        "cinematics": out_cinematics,
    }


def _coerce_velocity_cap(value) -> Optional[float]:
    if value is None or value is False:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ShotListError(f"velocity_cap must be a positive number, got {value!r}")
    if v <= 0:
        raise ShotListError(f"velocity_cap must be positive, got {v}")
    return v
