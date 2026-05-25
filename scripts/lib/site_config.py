"""Load + validate Apollo LNG per-option site YAML configs."""
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

EQUIPMENT_TYPES = {
    "iso_unit",
    "truck_bay",
    "pipe_manifold",
    "queens_pair",
    "glycol_vaporizer_with_stack",
    "bog_skid",
    "delivery_flange",
}


class SiteConfigError(ValueError):
    """Raised when a site YAML fails schema validation."""


@dataclass(frozen=True)
class Equipment:
    id: str
    type: str
    pos: tuple[float, float, float]
    rotation: float = 0.0


@dataclass(frozen=True)
class IsoArray:
    count: int
    cols: int
    rows: int
    origin: tuple[float, float, float]
    rotation: float = 0.0


@dataclass(frozen=True)
class Site:
    id: str
    letter: str
    title: str
    subtitle: str
    footprintAcres: float
    enduranceHrs: float
    hasPump: bool
    hasCapture: bool
    recommended: bool
    iso_array: IsoArray
    equipment: tuple[Equipment, ...]
    cinematic_title: str = ""
    cinematic_kicker: str = ""
    source_path: Optional[Path] = None


def _require(d: dict, key: str, path: str) -> Any:
    if key not in d:
        raise SiteConfigError(f"Missing required key '{path}.{key}'")
    return d[key]


def _as_vec3(value: Any, path: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise SiteConfigError(f"{path} must be a 3-element list, got {value!r}")
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError) as e:
        raise SiteConfigError(f"{path} must be numeric, got {value!r}") from e


def load_site(path):
    path = Path(path)
    if not path.exists():
        raise SiteConfigError(f"Site file not found: {path}")
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise SiteConfigError(f"Top-level YAML must be a mapping in {path}")

    site_block = _require(raw, "site", "")
    if not isinstance(site_block, dict):
        raise SiteConfigError("site block must be a mapping")

    iso_block = _require(raw, "iso_array", "")
    if not isinstance(iso_block, dict):
        raise SiteConfigError("iso_array block must be a mapping")

    iso = IsoArray(
        count=int(_require(iso_block, "count", "iso_array")),
        cols=int(_require(iso_block, "cols", "iso_array")),
        rows=int(_require(iso_block, "rows", "iso_array")),
        origin=_as_vec3(_require(iso_block, "origin", "iso_array"), "iso_array.origin"),
        rotation=float(iso_block.get("rotation", 0.0)),
    )

    equipment_raw = raw.get("equipment", [])
    if not isinstance(equipment_raw, list):
        raise SiteConfigError("equipment must be a list")

    seen_ids: set[str] = set()
    equipment: list[Equipment] = []
    for i, entry in enumerate(equipment_raw):
        if not isinstance(entry, dict):
            raise SiteConfigError(f"equipment[{i}] must be a mapping")
        eq_id = str(_require(entry, "id", f"equipment[{i}]"))
        if eq_id in seen_ids:
            raise SiteConfigError(f"Duplicate equipment id '{eq_id}' at equipment[{i}]")
        seen_ids.add(eq_id)
        eq_type = str(_require(entry, "type", f"equipment[{i}]"))
        if eq_type not in EQUIPMENT_TYPES:
            raise SiteConfigError(
                f"Unknown equipment type '{eq_type}' at equipment[{i}].type — "
                f"allowed: {sorted(EQUIPMENT_TYPES)}"
            )
        pos = _as_vec3(_require(entry, "pos", f"equipment[{i}]"), f"equipment[{i}].pos")
        if abs(pos[0]) > 200 or abs(pos[1]) > 200 or pos[2] != 0:
            print(
                f"[site_config] WARN equipment[{i}] id={eq_id!r} pos={pos} looks out of bounds",
                file=sys.stderr,
            )
        equipment.append(Equipment(
            id=eq_id,
            type=eq_type,
            pos=pos,
            rotation=float(entry.get("rotation", 0.0)),
        ))

    site_title = str(site_block.get("title", ""))
    site_letter = str(_require(site_block, "letter", "site"))
    cinematic_title = str(site_block.get("cinematic_title")
                          or (f"Apollo LNG \xB7 {site_title}" if site_title else f"Apollo LNG \xB7 Option {site_letter}"))
    cinematic_kicker = str(site_block.get("cinematic_kicker")
                           or (f"{site_title.upper()} \xB7 DRONE FLYTHROUGH" if site_title else f"OPTION {site_letter} \xB7 DRONE FLYTHROUGH"))
    return Site(
        id=str(_require(site_block, "id", "site")),
        letter=site_letter,
        title=site_title,
        subtitle=str(site_block.get("subtitle", "")),
        footprintAcres=float(site_block.get("footprintAcres", 0.0)),
        enduranceHrs=float(site_block.get("enduranceHrs", 0.0)),
        hasPump=bool(site_block.get("hasPump", False)),
        hasCapture=bool(site_block.get("hasCapture", False)),
        recommended=bool(site_block.get("recommended", False)),
        iso_array=iso,
        equipment=tuple(equipment),
        cinematic_title=cinematic_title,
        cinematic_kicker=cinematic_kicker,
        source_path=path,
    )
