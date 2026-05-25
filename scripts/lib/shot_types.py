"""Closed shot-type vocabulary and smart-default table for the shot-list DSL.

Per spec: docs/superpowers/specs/2026-05-25-shot-list-dsl-design.md
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


SHOT_TYPES = frozenset({
    "wide", "push", "pull", "hero", "pan", "orbit", "fly", "land", "hold",
})


@dataclass(frozen=True)
class ShotDefaults:
    """Smart-default values for one shot type.

    For 2-waypoint shots (push/pull/fly), `distance` and `height` are the
    *start* values; the per-type compiler computes end values internally.
    `None` means the field doesn't apply to this shot type.
    """
    focal: Optional[int]
    distance: Optional[float]
    height: Optional[float]
    ease: str = "easeInOut"


DEFAULTS: dict[str, ShotDefaults] = {
    "wide":   ShotDefaults(focal=24, distance=100.0, height=60.0),
    "push":   ShotDefaults(focal=35, distance=50.0,  height=12.0),
    "pull":   ShotDefaults(focal=42, distance=25.0,  height=8.0),
    "hero":   ShotDefaults(focal=40, distance=30.0,  height=8.0),
    "pan":    ShotDefaults(focal=38, distance=25.0,  height=6.0),
    "orbit":  ShotDefaults(focal=28, distance=80.0,  height=40.0),
    "fly":    ShotDefaults(focal=28, distance=80.0,  height=40.0),
    "land":   ShotDefaults(focal=50, distance=20.0,  height=5.0),
    "hold":   ShotDefaults(focal=None, distance=None, height=None),
}


COMPASS_DIRS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
