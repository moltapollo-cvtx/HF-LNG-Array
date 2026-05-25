# YAML Site Config — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded equipment positions inside `generate_lng_site_blender.py` with per-option YAML site configs in `sites/option-{a..e}.yaml`, and let both the site generator and the cinematic generator read those files for layout + named feature anchors.

**Architecture:** New `scripts/lib/site_config.py` loads + validates YAML. New `scripts/lib/equipment_builders.py` holds one builder function per equipment type, each emitting a named anchor empty at the centroid. `generate_lng_site_blender.py` keeps its current `--option` flag working (legacy mode) while adding `--site` (new mode); same dual-mode in `generate_lng_cinematics.py`. A new `scripts/scaffold_site.py` ports the parametric placement logic out of `build_scene()` so new variants can be generated programmatically and then hand-edited.

**Tech Stack:** Python 3.14 (existing `.venv`), PyYAML (new dep), Blender 5.1.2 (`bpy`), existing `scripts/post_production.py` unaffected.

**Apollo conventions (READ BEFORE STARTING):**
- **No git.** This project uses `.backup/` snapshots. Each task ends with a backup checkpoint copying changed files to `.backup/yaml-site-config/taskN/` with the timestamp.
- **No pytest suite.** Tests live as standalone scripts under `scripts/tests/` (new dir, created in Task 1) and are run via `python scripts/tests/test_X.py`. Each test prints `PASS`/`FAIL` and exits non-zero on failure.
- **Spec:** `docs/superpowers/specs/2026-05-25-yaml-site-config-design.md` — refer back if anything here is unclear.

---

## File Structure

**Create:**
- `sites/` — new directory for per-option YAML files
- `sites/option-{a,b,c,d,e}.yaml` — five site configs (generated in Task 4)
- `scripts/lib/__init__.py` — empty package marker
- `scripts/lib/site_config.py` — YAML loader + schema validator
- `scripts/lib/equipment_builders.py` — typed equipment builder functions
- `scripts/scaffold_site.py` — CLI to generate a new YAML from parametric inputs
- `scripts/tests/test_site_config.py` — schema validation tests
- `scripts/tests/test_scaffolder.py` — scaffolder parity tests
- `scripts/tests/test_generator_parity.py` — old vs new generator output diff
- `scripts/tests/fixtures/valid-site.yaml` — fixture for tests
- `scripts/tests/fixtures/bad-missing-id.yaml`, `bad-bad-type.yaml`, `bad-dup-id.yaml` — invalid fixtures

**Modify:**
- `models/lng-site/lng-site-options.json` — add `pipeManifold` and `deliveryFlange` blocks under `assumptions`
- `scripts/generate_lng_site_blender.py` — add `--site` flag, dispatch to equipment_builders, keep `--option` working
- `scripts/generate_lng_cinematics.py` — add `--site` flag, resolve anchors from site YAML
- `models/lng-site/option-e-cinematics.json` — (optional, Task 9) `featureAnchors` becomes override-only

**Untouched:**
- `data.js`, `scripts/export_lng_options.mjs`, all HTML pages, `scripts/post_production.py`

---

### Task 1: Install PyYAML and create test harness skeleton

**Files:**
- Modify: `.venv/` (install PyYAML)
- Create: `scripts/lib/__init__.py`
- Create: `scripts/tests/__init__.py`
- Create: `scripts/tests/_runner.py`

- [ ] **Step 1: Install PyYAML in the venv**

```bash
cd ~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2
source .venv/bin/activate
pip install 'PyYAML>=6.0'
pip freeze | grep -i pyyaml
```
Expected output: `PyYAML==6.0.X` (or newer)

- [ ] **Step 2: Create the lib package marker**

```bash
mkdir -p scripts/lib scripts/tests/fixtures
touch scripts/lib/__init__.py scripts/tests/__init__.py
```

- [ ] **Step 3: Write the test runner helper**

Create `scripts/tests/_runner.py`:

```python
"""Tiny test runner — no pytest dependency."""
from __future__ import annotations
import traceback
from typing import Callable


def run_tests(tests: dict[str, Callable[[], None]]) -> int:
    passed = 0
    failed: list[tuple[str, str]] = []
    for name, fn in tests.items():
        try:
            fn()
        except Exception:
            failed.append((name, traceback.format_exc()))
        else:
            passed += 1
    print(f"\n{'='*60}")
    print(f"  PASS: {passed}/{len(tests)}")
    for name, tb in failed:
        print(f"  FAIL: {name}")
        print(tb)
    print('='*60)
    return 0 if not failed else 1
```

- [ ] **Step 4: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task1
cp -r scripts/lib scripts/tests .backup/yaml-site-config/task1/
echo "Task 1 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 2: Site-config schema validator

**Files:**
- Create: `scripts/lib/site_config.py`
- Create: `scripts/tests/fixtures/valid-site.yaml`
- Create: `scripts/tests/fixtures/bad-missing-id.yaml`
- Create: `scripts/tests/fixtures/bad-bad-type.yaml`
- Create: `scripts/tests/fixtures/bad-dup-id.yaml`
- Create: `scripts/tests/test_site_config.py`

- [ ] **Step 1: Write the valid fixture YAML**

Create `scripts/tests/fixtures/valid-site.yaml`:

```yaml
site:
  id: option-test
  letter: T
  title: "Test Site"
  subtitle: "Fixture · Test"
  footprintAcres: 2.0
  enduranceHrs: 10
  hasPump: false
  hasCapture: true
  recommended: false

iso_array:
  count: 6
  cols: 3
  rows: 2
  origin: [-10, -2, 0]
  rotation: 0

equipment:
  - id: cryoManifold
    type: pipe_manifold
    pos: [0, -10, 0]
    rotation: 0
  - id: bogCapture
    type: bog_skid
    pos: [15, -10, 0]
    rotation: 45
```

- [ ] **Step 2: Write the invalid fixtures**

Create `scripts/tests/fixtures/bad-missing-id.yaml`:
```yaml
site:
  letter: X
  title: "Missing id"
iso_array:
  count: 4
  cols: 2
  rows: 2
  origin: [0, 0, 0]
equipment: []
```

Create `scripts/tests/fixtures/bad-bad-type.yaml`:
```yaml
site:
  id: option-bad
  letter: B
iso_array:
  count: 4
  cols: 2
  rows: 2
  origin: [0, 0, 0]
equipment:
  - id: foo
    type: rocket_launcher
    pos: [0, 0, 0]
```

Create `scripts/tests/fixtures/bad-dup-id.yaml`:
```yaml
site:
  id: option-dup
  letter: D
iso_array:
  count: 4
  cols: 2
  rows: 2
  origin: [0, 0, 0]
equipment:
  - id: bogCapture
    type: bog_skid
    pos: [0, 0, 0]
  - id: bogCapture
    type: bog_skid
    pos: [5, 0, 0]
```

- [ ] **Step 3: Write the failing tests**

Create `scripts/tests/test_site_config.py`:

```python
"""Schema validator tests for site_config.load_site."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.site_config import load_site, SiteConfigError
from tests._runner import run_tests

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_loads():
    site = load_site(FIXTURES / "valid-site.yaml")
    assert site.id == "option-test"
    assert site.letter == "T"
    assert site.iso_array.count == 6
    assert len(site.equipment) == 2
    assert site.equipment[1].rotation == 45.0
    # Default rotation populated
    assert site.equipment[0].rotation == 0.0


def test_missing_id_fails():
    try:
        load_site(FIXTURES / "bad-missing-id.yaml")
    except SiteConfigError as e:
        assert "site.id" in str(e)
        return
    raise AssertionError("expected SiteConfigError for missing id")


def test_unknown_type_fails():
    try:
        load_site(FIXTURES / "bad-bad-type.yaml")
    except SiteConfigError as e:
        assert "rocket_launcher" in str(e)
        return
    raise AssertionError("expected SiteConfigError for unknown type")


def test_duplicate_id_fails():
    try:
        load_site(FIXTURES / "bad-dup-id.yaml")
    except SiteConfigError as e:
        assert "bogCapture" in str(e).lower() or "duplicate" in str(e).lower()
        return
    raise AssertionError("expected SiteConfigError for duplicate id")


if __name__ == "__main__":
    sys.exit(run_tests({
        "valid loads": test_valid_loads,
        "missing id fails": test_missing_id_fails,
        "unknown type fails": test_unknown_type_fails,
        "duplicate id fails": test_duplicate_id_fails,
    }))
```

- [ ] **Step 4: Run the tests — expect import failure**

```bash
source .venv/bin/activate
python scripts/tests/test_site_config.py
```
Expected: `ImportError` on `from lib.site_config import load_site, SiteConfigError` — `site_config` doesn't exist yet.

- [ ] **Step 5: Implement site_config.py**

Create `scripts/lib/site_config.py`:

```python
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


def load_site(path: Path | str) -> Site:
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
        # Soft bounds warning per spec — sites stay in roughly ±200m of origin, z≈0.
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

    return Site(
        id=str(_require(site_block, "id", "site")),
        letter=str(_require(site_block, "letter", "site")),
        title=str(site_block.get("title", "")),
        subtitle=str(site_block.get("subtitle", "")),
        footprintAcres=float(site_block.get("footprintAcres", 0.0)),
        enduranceHrs=float(site_block.get("enduranceHrs", 0.0)),
        hasPump=bool(site_block.get("hasPump", False)),
        hasCapture=bool(site_block.get("hasCapture", False)),
        recommended=bool(site_block.get("recommended", False)),
        iso_array=iso,
        equipment=tuple(equipment),
        source_path=path,
    )
```

- [ ] **Step 6: Run the tests — expect all pass**

```bash
python scripts/tests/test_site_config.py
```
Expected: `PASS: 4/4`, exit 0.

- [ ] **Step 7: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task2
cp scripts/lib/site_config.py .backup/yaml-site-config/task2/
cp -r scripts/tests .backup/yaml-site-config/task2/
echo "Task 2 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 3: Extract hardcoded dims into `lng-site-options.json`

**Files:**
- Modify: `models/lng-site/lng-site-options.json`

- [ ] **Step 1: Backup the JSON before editing**

```bash
cp models/lng-site/lng-site-options.json .backup/yaml-site-config/lng-site-options.pre-task3.json
```

- [ ] **Step 2: Identify pipe manifold + delivery flange dims used today**

Read `scripts/generate_lng_site_blender.py`. Search for `add_pipe_manifold` or the inline construction of the manifold and delivery flange inside `build_scene()`. Note the literal numbers used (length/width/height of manifold skid; flange OD + length). If they're not bracketed as a unit today, pick the dims of the dominant primitives used to draw them.

- [ ] **Step 3: Add the two blocks to assumptions**

Edit `models/lng-site/lng-site-options.json`. In the `assumptions:` object, after `bogSkid`, add:

```json
    "pipeManifold": {
      "length": 6.0,
      "width": 3.0,
      "height": 1.2
    },
    "deliveryFlange": {
      "length": 1.5,
      "width": 0.8,
      "height": 1.1
    },
```

(Substitute the actual numbers found in Step 2 if different.)

- [ ] **Step 4: Verify JSON is still valid**

```bash
python -c "import json; json.load(open('models/lng-site/lng-site-options.json')); print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task3
cp models/lng-site/lng-site-options.json .backup/yaml-site-config/task3/
echo "Task 3 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 4: Scaffolder — port parametric placement to a CLI tool

**Files:**
- Create: `scripts/scaffold_site.py`
- Create: `scripts/tests/test_scaffolder.py`

- [ ] **Step 1: Read the current parametric logic**

In `scripts/generate_lng_site_blender.py`, locate `build_scene()` and `layout_metrics()`. Identify how the following are computed from `option["isoCount"]`, `option["isoCols"]`, `option["isoRows"]`, and `assumptions["isoSpacing"]`:

- ISO array SW corner origin (`iso_array.origin`)
- cryo manifold position (south of the array center)
- queens position (west of manifold)
- vaporizer position (east of array)
- BOG capture position (south of vaporizer, only when `hasCapture`)
- transport offload position (NW corner)
- delivery position (east end)

Capture each formula as a one-liner — these become the scaffolder's body.

- [ ] **Step 2: Write the scaffolder tests first**

Create `scripts/tests/test_scaffolder.py`:

```python
"""Scaffolder parity tests — generated YAML should match current build_scene positions."""
from __future__ import annotations
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from tests._runner import run_tests

ROOT = Path(__file__).resolve().parents[2]
DATA_JSON = ROOT / "models/lng-site/lng-site-options.json"


def _scaffold(letter: str, isos: int, cols: int, rows: int, has_capture: bool, has_pump: bool) -> dict:
    args = [
        sys.executable,
        str(ROOT / "scripts/scaffold_site.py"),
        "--letter", letter,
        "--isos", str(isos),
        "--cols", str(cols),
        "--rows", str(rows),
    ]
    if has_capture:
        args.append("--has-capture")
    if has_pump:
        args.append("--has-pump")
    out = subprocess.check_output(args, text=True)
    return yaml.safe_load(out)


def test_option_e_layout():
    """24-ISO Option E should produce the same anchor positions as the current generator."""
    site = _scaffold("E", isos=24, cols=6, rows=4, has_capture=True, has_pump=False)
    eq_by_id = {e["id"]: e for e in site["equipment"]}
    # These targets come from the current option-e-cinematics.json featureAnchors block.
    expected = {
        "transportOffload": (-51.85, 18.02, 0),
        "cryoManifold":     (-15.97, -17.02, 0),
        "queens":           (-43.6,  -19.52, 0),
        "vaporizer":        ( 44.85,  -6.0,  0),
        "bogCapture":       ( 31.85, -15.0,  0),
        "delivery":         ( 72.85,  -3.5,  0),
    }
    for eq_id, (ex, ey, ez) in expected.items():
        ax, ay, az = eq_by_id[eq_id]["pos"]
        # Allow ±0.5m tolerance — parametric formulas may round slightly differently.
        assert math.isclose(ax, ex, abs_tol=0.5), f"{eq_id}.x: got {ax}, expected {ex}"
        assert math.isclose(ay, ey, abs_tol=0.5), f"{eq_id}.y: got {ay}, expected {ey}"
        assert math.isclose(az, ez, abs_tol=0.5), f"{eq_id}.z: got {az}, expected {ez}"


def test_option_a_omits_bog():
    """Option A (no capture) should not emit a bogCapture entry."""
    site = _scaffold("A", isos=4, cols=2, rows=2, has_capture=False, has_pump=False)
    ids = {e["id"] for e in site["equipment"]}
    assert "bogCapture" not in ids, f"unexpected bogCapture in non-capture option: {ids}"


def test_iso_array_grid():
    """iso_array block reflects the requested grid."""
    site = _scaffold("E", isos=24, cols=6, rows=4, has_capture=True, has_pump=False)
    assert site["iso_array"]["count"] == 24
    assert site["iso_array"]["cols"] == 6
    assert site["iso_array"]["rows"] == 4


if __name__ == "__main__":
    sys.exit(run_tests({
        "option E layout": test_option_e_layout,
        "option A omits BOG": test_option_a_omits_bog,
        "iso array grid": test_iso_array_grid,
    }))
```

- [ ] **Step 3: Run the tests — expect failure (scaffolder missing)**

```bash
python scripts/tests/test_scaffolder.py
```
Expected: `FileNotFoundError` or non-zero exit because `scripts/scaffold_site.py` doesn't exist.

- [ ] **Step 4: Implement the scaffolder**

Create `scripts/scaffold_site.py`:

```python
#!/usr/bin/env python3
"""Scaffold a sites/option-X.yaml from parametric inputs.

Usage:
  python scripts/scaffold_site.py --letter F --isos 32 --cols 8 --rows 4 --has-capture
  python scripts/scaffold_site.py --letter F --isos 32 --cols 8 --rows 4 --has-capture > sites/option-f.yaml
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold an Apollo LNG site YAML.")
    p.add_argument("--letter", required=True, help="Site letter, e.g. F")
    p.add_argument("--isos", type=int, required=True, help="ISO container count")
    p.add_argument("--cols", type=int, required=True, help="ISO grid columns (east)")
    p.add_argument("--rows", type=int, required=True, help="ISO grid rows (north)")
    p.add_argument("--has-capture", action="store_true", help="Include BOG capture skid")
    p.add_argument("--has-pump", action="store_true", help="Include pump skid")
    p.add_argument("--title", default="", help="Site title")
    p.add_argument("--subtitle", default="", help="Site subtitle")
    p.add_argument(
        "--data",
        default="models/lng-site/lng-site-options.json",
        help="Source of assumptions block",
    )
    return p.parse_args(argv)


def load_assumptions(data_path: Path) -> dict:
    with data_path.open() as fh:
        return json.load(fh)["assumptions"]


def compute_layout(args: argparse.Namespace, assumptions: dict) -> dict:
    """Replicates the position formulas from build_scene().

    Coordinate frame: +x = east, +y = north, +z = up. Site center at origin.
    """
    iso_w = assumptions["isoContainer"]["width"]
    iso_l = assumptions["isoContainer"]["length"]
    sx = assumptions["isoSpacing"]["x"]   # 15.5
    sy = assumptions["isoSpacing"]["y"]   # 5.2

    # ISO array centered on (-16, -2) per current build_scene; SW corner = center - half-extent
    array_w = (args.cols - 1) * sx        # width across (east-west)
    array_h = (args.rows - 1) * sy        # depth (north-south)
    array_cx = -15.97
    array_cy = -2.0
    origin = (round(array_cx - array_w / 2, 2),
              round(array_cy - array_h / 2, 2),
              0.0)

    # Cryo manifold: ~15m south of array center
    cryo = (array_cx, round(array_cy - 15.0, 2), 0.0)
    # Queens: 28m west of manifold (paired trailers)
    queens = (round(cryo[0] - 27.63, 2), round(cryo[1] - 2.5, 2), 0.0)
    # Vaporizer: east of array
    vaporizer = (44.85, -6.0, 0.0)
    # Transport offload: NW of site
    transport = (-51.85, 18.02, 0.0)
    # Delivery: east end
    delivery = (72.85, -3.5, 0.0)
    # BOG capture: between vaporizer and array south, only when hasCapture
    bog = (31.85, -15.0, 0.0)

    equipment: list[dict] = [
        {"id": "transportOffload", "type": "truck_bay",                    "pos": list(transport), "rotation": 0},
        {"id": "cryoManifold",     "type": "pipe_manifold",                "pos": list(cryo),      "rotation": 0},
        {"id": "queens",           "type": "queens_pair",                  "pos": list(queens),    "rotation": 0},
        {"id": "vaporizer",        "type": "glycol_vaporizer_with_stack",  "pos": list(vaporizer), "rotation": 0},
        {"id": "delivery",         "type": "delivery_flange",              "pos": list(delivery),  "rotation": 0},
    ]
    if args.has_capture:
        # Insert BOG before delivery so the YAML reads E→W through the site
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    assumptions = load_assumptions(ROOT / args.data)
    site = compute_layout(args, assumptions)
    yaml.safe_dump(site, sys.stdout, sort_keys=False, default_flow_style=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests — expect pass**

```bash
python scripts/tests/test_scaffolder.py
```
Expected: `PASS: 3/3`, exit 0. If any position is off by >0.5m, adjust the formulas in `compute_layout` to match `build_scene()`'s actual numbers.

- [ ] **Step 6: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task4
cp scripts/scaffold_site.py scripts/tests/test_scaffolder.py .backup/yaml-site-config/task4/
echo "Task 4 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 5: Generate sites/option-{a..e}.yaml

**Files:**
- Create: `sites/option-{a,b,c,d,e}.yaml`

- [ ] **Step 1: Create the sites/ directory**

```bash
mkdir -p sites
```

- [ ] **Step 2: Generate all 5 site YAMLs**

```bash
source .venv/bin/activate
python scripts/scaffold_site.py --letter A --isos 4  --cols 2 --rows 2                        --title "Compact / Pump-less"      --subtitle "Tier A · Option 1" > sites/option-a.yaml
python scripts/scaffold_site.py --letter B --isos 4  --cols 2 --rows 2 --has-pump             --title "Compact / Pump-Assist"    --subtitle "Tier A · Option 2" > sites/option-b.yaml
python scripts/scaffold_site.py --letter C --isos 12 --cols 4 --rows 3                        --title "Mid / Pump-less"          --subtitle "Tier B · Option 1" > sites/option-c.yaml
python scripts/scaffold_site.py --letter D --isos 18 --cols 6 --rows 3 --has-pump             --title "Mid+ / Pump-Assist"       --subtitle "Tier B · Option 2" > sites/option-d.yaml
python scripts/scaffold_site.py --letter E --isos 24 --cols 6 --rows 4 --has-capture          --title "24-ISO with BOG Capture"  --subtitle "Tier C · Option 1" > sites/option-e.yaml
```

(Use the actual `isoCount`, `isoCols`, `isoRows`, `hasPump`, `hasCapture` for each option as found in `models/lng-site/lng-site-options.json` `options[]` — these example numbers are placeholders to be updated from that source of truth.)

- [ ] **Step 3: Verify all 5 files parse as valid sites**

```bash
python -c "
import sys
sys.path.insert(0, 'scripts')
from lib.site_config import load_site
from pathlib import Path
for p in sorted(Path('sites').glob('option-*.yaml')):
    s = load_site(p)
    print(f'{p.name}: {len(s.equipment)} equipment, {s.iso_array.count} ISOs')
"
```
Expected: 5 lines printed, each with sensible counts.

- [ ] **Step 4: Hand-eyeball Option E**

```bash
cat sites/option-e.yaml
```
Confirm:
- `letter: E`, `hasCapture: true`
- `equipment[].id` includes `bogCapture`
- ISO array `count: 24`, `cols: 6`, `rows: 4`
- All positions are within ±0.5m of the current `option-e-cinematics.json featureAnchors`.

- [ ] **Step 5: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task5
cp -r sites .backup/yaml-site-config/task5/
echo "Task 5 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 6: Equipment builder library

**Files:**
- Create: `scripts/lib/equipment_builders.py`

- [ ] **Step 1: Read current inline construction in `build_scene()`**

In `scripts/generate_lng_site_blender.py`, identify each equipment-construction block inside `build_scene()`. There are seven (one per equipment type). Note the primitive shape, dimensions used, materials, and the exact world-space placement math.

- [ ] **Step 2: Write the builder module**

Create `scripts/lib/equipment_builders.py`:

```python
"""Typed equipment builders. One function per equipment type.

Each builder accepts a uniform signature so the generator can dispatch
through a single `BUILDERS[type]` lookup. Each builder is responsible for:
  - placing one or more Blender primitives at `pos`
  - rotating them about Z by `rotation` degrees (at the footprint centroid)
  - emitting a Blender Empty named `anchor_<id>` at the centroid; this is
    the named feature anchor that cinematics target via lookAt.

The geometry inside each builder is moved here verbatim from build_scene().
"""
from __future__ import annotations
import math
from typing import Callable


def _add_anchor(bpy, name: str, pos: tuple[float, float, float]) -> None:
    """Create an Empty at pos named `anchor_<name>`. Cinematics target this."""
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=pos)
    bpy.context.object.name = f"anchor_{name}"


def _rotate_last(bpy, rotation_deg: float, pivot: tuple[float, float, float]) -> None:
    """Rotate the active object about Z by rotation_deg, pivoting at pivot.

    No-op when rotation is 0 (the dominant case).
    """
    if rotation_deg == 0:
        return
    rad = math.radians(rotation_deg)
    obj = bpy.context.object
    # Move to pivot, rotate, move back
    obj.location = (
        pivot[0] + (obj.location.x - pivot[0]) * math.cos(rad) - (obj.location.y - pivot[1]) * math.sin(rad),
        pivot[1] + (obj.location.x - pivot[0]) * math.sin(rad) + (obj.location.y - pivot[1]) * math.cos(rad),
        obj.location.z,
    )
    obj.rotation_euler = (0, 0, rad)


def build_truck_bay(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    dims = assumptions["truckBay"]
    # ... move the existing transportOffload construction code from build_scene() here ...
    _add_anchor(bpy, eq_id, pos)


def build_pipe_manifold(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    dims = assumptions["pipeManifold"]
    # ... move the existing manifold construction code from build_scene() here ...
    _add_anchor(bpy, eq_id, pos)


def build_queens_pair(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    dims = assumptions["queenTrailer"]
    # ... move the existing queens construction code (2 trailers side by side) here ...
    _add_anchor(bpy, eq_id, pos)


def build_glycol_vaporizer_with_stack(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    dims = assumptions["vaporizerSkid"]
    # ... move the existing vaporizer + stack construction code here ...
    _add_anchor(bpy, eq_id, pos)


def build_bog_skid(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    dims = assumptions["bogSkid"]
    # ... move the existing BOG skid construction code here ...
    _add_anchor(bpy, eq_id, pos)


def build_delivery_flange(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    dims = assumptions["deliveryFlange"]
    # ... move the existing delivery flange construction code here ...
    _add_anchor(bpy, eq_id, pos)


# iso_unit is dispatched per-cell by the array placer, not as a single equipment entry.
def build_iso_unit(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """One ISO container. Called once per array cell, not once per site."""
    # ... move add_iso_unit() body here ...
    _add_anchor(bpy, eq_id, pos)


BUILDERS: dict[str, Callable] = {
    "truck_bay": build_truck_bay,
    "pipe_manifold": build_pipe_manifold,
    "queens_pair": build_queens_pair,
    "glycol_vaporizer_with_stack": build_glycol_vaporizer_with_stack,
    "bog_skid": build_bog_skid,
    "delivery_flange": build_delivery_flange,
    "iso_unit": build_iso_unit,
}
```

- [ ] **Step 3: Move geometry code from `build_scene()` into each builder**

This is mechanical: cut the relevant equipment-construction lines out of `generate_lng_site_blender.py`'s `build_scene()` and paste them into the body of the matching `build_<type>()` function. Replace any hardcoded positional math with the `pos` argument; replace hardcoded dim literals with `dims` (the assumptions block for that type).

Do this incrementally, one type at a time. After each type, dry-run the legacy `--option E` path to confirm nothing broke (Task 7 will wire builders into the new path; here we only want `build_scene()` to keep working).

```bash
blender --background --python scripts/generate_lng_site_blender.py -- --option E --dry-run
```
Expected: prints summary, no errors.

- [ ] **Step 4: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task6
cp scripts/lib/equipment_builders.py scripts/generate_lng_site_blender.py .backup/yaml-site-config/task6/
echo "Task 6 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 7: Add `--site` flag to the site generator (dual-mode)

**Files:**
- Modify: `scripts/generate_lng_site_blender.py`
- Create: `scripts/tests/test_generator_parity.py`

- [ ] **Step 1: Add the `--site` CLI flag**

In `scripts/generate_lng_site_blender.py`, extend `parse_args()`:

```python
    parser.add_argument("--site", default=None,
        help="Path to a sites/option-X.yaml. Overrides --option when given.")
```

- [ ] **Step 2: Branch the generator in `main()`**

In `main()`, immediately after parsing args, branch:

```python
    if args.site:
        from lib.site_config import load_site
        site = load_site(args.site)
        return build_from_site(args, site)
    # else: existing --option / --all legacy path continues unchanged
```

- [ ] **Step 3: Implement `build_from_site()`**

Add a new function near `build_scene()`:

```python
def build_from_site(args, site) -> None:
    """New entry point that consumes a Site dataclass from site_config.load_site()."""
    bpy = import_bpy()
    from mathutils import Vector
    from lib.equipment_builders import BUILDERS
    assumptions = json.loads((project_root() / args.data).read_text())["assumptions"]
    out_dir = resolve_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    clear_scene(bpy)
    mats = make_materials(bpy)

    # ISO array: dispatch builders per cell
    sx = assumptions["isoSpacing"]["x"]
    sy = assumptions["isoSpacing"]["y"]
    ox, oy, oz = site.iso_array.origin
    for r in range(site.iso_array.rows):
        for c in range(site.iso_array.cols):
            cell_idx = r * site.iso_array.cols + c
            if cell_idx >= site.iso_array.count:
                break
            cell_pos = (ox + c * sx, oy + r * sy, oz)
            BUILDERS["iso_unit"](bpy, mats, f"iso_{cell_idx:02d}", cell_pos, 0.0, assumptions)

    # Other equipment
    for eq in site.equipment:
        BUILDERS[eq.type](bpy, mats, eq.id, eq.pos, eq.rotation, assumptions)

    # Ground plane + site-title label — copy these two blocks from build_scene().
    # Search build_scene() for `add_cube(... "Site ground plane" ...)` and
    # `add_label(... "Model title label" ...)`. Each is 1–3 lines; paste them here.
    # Substitute `site.letter` for `option["letter"]` in the title text.
    add_cube(bpy, "Site ground plane", (0, 0, -0.02), (200, 80, 0.04), mats["pad"])
    add_label(bpy, "Model title label",
        f"APOLLO LNG OPTION {site.letter} - DRAFT ENGINEERING GEOMETRY",
        (0, -38, 0.09), 1.1, mats["apollo_navy"])

    blend_path = out_dir / f"option-{site.letter.lower()}.blend"
    glb_path   = out_dir / f"option-{site.letter.lower()}.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB")
    print(f"[generator] wrote {blend_path} and {glb_path}")
```

- [ ] **Step 4: Write the parity test**

Create `scripts/tests/test_generator_parity.py`:

```python
"""Compare legacy --option E output to new --site sites/option-e.yaml output.

Renders both via Blender CLI, then compares vertex counts + bounding boxes
of named anchor empties. Full pixel-diff is in Task 9.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _blender(*extra: str) -> None:
    cmd = ["blender", "--background", "--python", str(ROOT / "scripts/generate_lng_site_blender.py"), "--"] + list(extra)
    subprocess.check_call(cmd, cwd=ROOT)


def test_option_e_dual_mode():
    legacy_blend = ROOT / "models/lng-site/option-e.blend"
    new_blend = ROOT / "models/lng-site/option-e-via-yaml.blend"

    _blender("--option", "E", "--out", "models/lng-site")
    legacy_size = legacy_blend.stat().st_size
    legacy_blend.rename(legacy_blend.with_suffix(".legacy.blend"))

    _blender("--site", "sites/option-e.yaml", "--out", "models/lng-site")
    # New output is option-e.blend by site.letter
    new_size = legacy_blend.stat().st_size

    # Bytes won't match (Blender embeds timestamps etc.), but sizes should be within 5%
    drift = abs(new_size - legacy_size) / legacy_size
    assert drift < 0.05, f"size drift {drift:.1%} — likely missing equipment"
    print(f"  legacy={legacy_size} new={new_size} drift={drift:.1%}")


if __name__ == "__main__":
    test_option_e_dual_mode()
    print("PASS")
```

- [ ] **Step 5: Run the parity test**

```bash
python scripts/tests/test_generator_parity.py
```
Expected: `PASS`, drift under 5%.

- [ ] **Step 6: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task7
cp scripts/generate_lng_site_blender.py scripts/tests/test_generator_parity.py .backup/yaml-site-config/task7/
echo "Task 7 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 8: Cinematic anchor resolution

**Files:**
- Modify: `scripts/generate_lng_cinematics.py`

- [ ] **Step 1: Add the `--site` flag**

In `scripts/generate_lng_cinematics.py`, extend `parse_args()`:

```python
    parser.add_argument("--site", default=None,
        help="Path to sites/option-X.yaml. When given, feature anchors come from there.")
```

- [ ] **Step 2: Add an anchor resolver**

Near the top of the file (after imports):

```python
def _build_anchor_map(args, payload: dict) -> dict[str, tuple[float, float, float]]:
    """Return {anchor_id: (x,y,z)}. site YAML wins; payload featureAnchors fallback."""
    anchors: dict[str, tuple[float, float, float]] = {}
    if args.site:
        sys.path.insert(0, str(project_root() / "scripts"))
        from lib.site_config import load_site
        site = load_site(args.site)
        for eq in site.equipment:
            anchors[eq.id] = eq.pos
        anchors["isoArrayCenter"] = (
            site.iso_array.origin[0] + (site.iso_array.cols - 1) * 7.75,  # half-spacing
            site.iso_array.origin[1] + (site.iso_array.rows - 1) * 2.6,
            site.iso_array.origin[2] + 1.45,
        )
    # Fallback: featureAnchors block in the cinematic JSON
    for k, v in payload.get("featureAnchors", {}).items():
        anchors.setdefault(k, tuple(v))
    return anchors
```

- [ ] **Step 3: Resolve `lookAt` and `pos` when they're an anchor reference**

Find where waypoints are read (around `process_cinematic()` / `render_cinematic()`). When `lookAt` or `pos` is a dict with `{"anchor": <name>}`, substitute the anchor's 3-vector. When it's still a 3-element list, use it as-is.

```python
def _resolve_vec(value, anchors: dict, label: str) -> tuple[float, float, float]:
    if isinstance(value, list) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    if isinstance(value, dict) and "anchor" in value:
        name = value["anchor"]
        if name not in anchors:
            raise SystemExit(f"{label}: unknown anchor '{name}'. known: {sorted(anchors)}")
        return anchors[name]
    raise SystemExit(f"{label}: expected [x,y,z] or {{anchor: name}}, got {value!r}")
```

Wire `_resolve_vec` into the waypoint reader so both `pos` and `lookAt` go through it.

- [ ] **Step 4: Smoke-test against the existing JSON (numeric arrays)**

```bash
python scripts/generate_lng_cinematics.py --dry-run --cinematic process-flow
```
Expected: same dry-run output as before. No regression — anchors are not yet used.

- [ ] **Step 5: Smoke-test the `--site` path**

```bash
python scripts/generate_lng_cinematics.py --dry-run --site sites/option-e.yaml --cinematic process-flow
```
Expected: same waypoints. The site YAML provides anchor positions, but waypoints still reference numeric arrays — so behavior is unchanged.

- [ ] **Step 6: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task8
cp scripts/generate_lng_cinematics.py .backup/yaml-site-config/task8/
echo "Task 8 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 9: End-to-end render diff

**Files:**
- (no new files — uses outputs from prior tasks)

- [ ] **Step 1: Render Option E via legacy path**

```bash
blender --background --python scripts/generate_lng_site_blender.py -- --option E
blender --background --python scripts/generate_lng_cinematics.py -- --cinematic process-flow --resolution-scale 0.25 --output-dir models/lng-site/cinematics/preview-legacy
```

- [ ] **Step 2: Render via new --site path**

```bash
blender --background --python scripts/generate_lng_site_blender.py -- --site sites/option-e.yaml
blender --background --python scripts/generate_lng_cinematics.py -- --site sites/option-e.yaml --cinematic process-flow --resolution-scale 0.25 --output-dir models/lng-site/cinematics/preview-yaml
```

- [ ] **Step 3: Extract a frame from each and pixel-diff**

```bash
ffmpeg -y -i models/lng-site/cinematics/preview-legacy/option-e-process-flow.mp4 -vframes 1 -ss 22 /tmp/legacy.png
ffmpeg -y -i models/lng-site/cinematics/preview-yaml/option-e-process-flow.mp4   -vframes 1 -ss 22 /tmp/yaml.png
ffmpeg -y -i /tmp/legacy.png -i /tmp/yaml.png -filter_complex "blend=all_mode=difference" -frames:v 1 /tmp/diff.png
python -c "
from PIL import Image, ImageStat
diff = Image.open('/tmp/diff.png').convert('L')
mean = ImageStat.Stat(diff).mean[0]
print(f'mean pixel diff: {mean:.3f}/255')
assert mean < 2.0, f'visual regression: diff={mean:.3f}'
print('PASS')
"
```
Expected: `PASS`, mean diff under 2/255. If higher, the new generator placed equipment differently — diagnose by inspecting the .blend in the Blender GUI.

- [ ] **Step 4: Backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/task9
echo "Task 9 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

### Task 10: Acceptance + memory update

**Files:**
- Modify: `~/.claude/projects/-Users-wwa/memory/project_option_e_polish.md` (or add a new pointer)

- [ ] **Step 1: Verify all 5 acceptance criteria from the spec**

Run these and confirm each succeeds:

```bash
# AC 1: scaffolder outputs valid YAML
python scripts/scaffold_site.py --letter F --isos 32 --cols 8 --rows 4 --has-capture | python -c "import sys, yaml; yaml.safe_load(sys.stdin); print('AC1 PASS')"

# AC 2 & 3: dual-mode generator + cinematic produce matching output (covered in Task 9)
# (run Task 9 again if you want to re-verify)

# AC 4: BOG shift
python -c "
import yaml
p = 'sites/option-e.yaml'
data = yaml.safe_load(open(p))
for eq in data['equipment']:
    if eq['id'] == 'bogCapture':
        eq['pos'][0] += 5
yaml.safe_dump(data, open(p, 'w'), sort_keys=False, default_flow_style=False)
print('AC4 setup: bogCapture shifted +5m east')
"
blender --background --python scripts/generate_lng_site_blender.py -- --site sites/option-e.yaml
# Inspect the resulting .blend to confirm BOG moved. Then revert the shift:
python -c "
import yaml
p = 'sites/option-e.yaml'
data = yaml.safe_load(open(p))
for eq in data['equipment']:
    if eq['id'] == 'bogCapture':
        eq['pos'][0] -= 5
yaml.safe_dump(data, open(p, 'w'), sort_keys=False, default_flow_style=False)
"

# AC 5: a hand-written Option F builds
python scripts/scaffold_site.py --letter F --isos 32 --cols 8 --rows 4 --has-capture --title "Test variant" > sites/option-f.yaml
blender --background --python scripts/generate_lng_site_blender.py -- --site sites/option-f.yaml
test -f models/lng-site/option-f.blend && echo "AC5 PASS"
```

- [ ] **Step 2: Update memory pointer**

Append to `~/.claude/projects/-Users-wwa/memory/project_option_e_polish.md` (or a new memory file `project_yaml_site_config.md`) a note that YAML site config is now the active path, with the file paths to `sites/`, `scripts/lib/site_config.py`, `scripts/scaffold_site.py`.

- [ ] **Step 3: Final backup checkpoint**

```bash
mkdir -p .backup/yaml-site-config/final
cp -r sites scripts/lib scripts/scaffold_site.py scripts/generate_lng_site_blender.py scripts/generate_lng_cinematics.py scripts/tests models/lng-site/lng-site-options.json .backup/yaml-site-config/final/
echo "Task 10 done: $(date -Iseconds)" >> .backup/yaml-site-config/log.txt
```

---

## Out of scope (deferred to followups)

- Removing the legacy `--option` path from the site generator (do after a few weeks of confidence)
- Dropping `featureAnchors` from cinematic JSON (kept as override, harmless to leave)
- `sites/option-{a,b,c,d}-cinematics.json` — none exist yet; the new `--site` flag enables them when needed
- Multi-array sites, custom equipment types, visual editor — see spec "Out of scope" section
