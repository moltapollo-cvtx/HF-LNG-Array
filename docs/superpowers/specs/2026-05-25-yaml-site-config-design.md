# YAML Site Config — Design (2026-05-25)

Move LNG-site layout from `build_scene()` Python into per-option YAML files so non-coders can edit positions, scaffold new variants, and reuse one set of feature anchors across the generator and cinematics.

## Why

Today, equipment **positions** are computed inside `scripts/generate_lng_site_blender.py` (`build_scene()`, lines 292–419). Counts and dimensions are config-driven via `models/lng-site/lng-site-options.json`, but the manifold, queens, vaporizer, BOG skid, transport offload, and delivery are placed by code. Same coordinates are also hand-duplicated in `models/lng-site/option-e-cinematics.json` as `featureAnchors`.

Walker wants to (a) tweak standard options, (b) create bespoke variants (Option F, G…), and (c) test cinematics against multiple site variants — all without touching Python. The hand-duplication of anchors between the generator and cinematic JSON is a known wart.

## Scope

**In:**
- New per-option YAML files in `sites/option-{a..e}.yaml` carrying layout (equipment positions + rotation, ISO grid origin).
- A `--site` flag added to `generate_lng_site_blender.py` and `generate_lng_cinematics.py` so both read the same site file.
- A scaffolder `scripts/scaffold_site.py` that emits a YAML file from the existing parametric logic (count → cols/rows → x,y).
- The cinematic JSON drops its `featureAnchors` block; anchors flow from the site YAML.

**Out:**
- New equipment types beyond the existing library (truck_bay, pipe_manifold, queens_pair, glycol_vaporizer_with_stack, bog_skid, delivery_flange, iso_unit). Confirmed with Walker.
- Visual editor (Blender's editor is the visual editor).
- Replacing `lng-site-options.json`. That file keeps `assumptions` (equipment dimensions) and `designBasis`. Only layout/option-metadata move to YAML.
- Multiple ISO arrays per site (one is fine, confirmed).

## Schema

`sites/option-e.yaml`:

```yaml
# Site config for Apollo LNG Option E
# Read by: generate_lng_site_blender.py, generate_lng_cinematics.py
# Dimensions + design basis still come from lng-site-options.json.

site:
  id: option-e                # unique slug; used in output paths
  letter: E                   # for legacy compatibility with build_scene
  title: "24-ISO with BOG Capture"
  subtitle: "Tier C · Option 1"
  footprintAcres: 2.3
  enduranceHrs: 22
  hasPump: false
  hasCapture: true
  recommended: true

iso_array:
  count: 24
  cols: 6
  rows: 4
  origin: [-30, -2, 0]        # SW corner of the array, ground plane
  rotation: 0                 # degrees around Z (whole array)
  # spacing: inherited from lng-site-options.json assumptions.isoSpacing

equipment:
  - id: transportOffload
    type: truck_bay
    pos: [-51.85, 18.02, 0]
    rotation: 0

  - id: cryoManifold
    type: pipe_manifold
    pos: [-15.97, -17.02, 0]
    rotation: 0

  - id: queens
    type: queens_pair
    pos: [-43.6, -19.52, 0]
    rotation: 0

  - id: vaporizer
    type: glycol_vaporizer_with_stack
    pos: [44.85, -6.0, 0]
    rotation: 0

  - id: bogCapture
    type: bog_skid
    pos: [31.85, -15.0, 0]
    rotation: 0

  - id: delivery
    type: delivery_flange
    pos: [72.85, -3.5, 0]
    rotation: 0
```

### Field rules

- `pos` is `[x, y, z]` in meters. `x`/`y` are world coordinates of the equipment's footprint center; `z` is the *base* (ground contact, almost always 0). The equipment type's builder function adds its own height/center offset on top — matches today's `build_scene()` behavior.
- `rotation` is degrees around the Z axis applied at the equipment's footprint center (same `(x, y)` as `pos`). Default 0 if omitted. Counter-clockwise from +X (right-hand rule).
- `id` is the public anchor name. Cinematics reference `id` directly: `lookAt: {anchor: cryoManifold}` (see Cinematic integration below).
- `type` must match one of the closed equipment-type vocabulary.
- `iso_array.origin` is the SW corner; the grid lays out `cols` units east (+x) and `rows` units north (+y), with spacing from `lng-site-options.json` assumptions.

### Equipment-type vocabulary (closed)

| `type:` value                  | Python builder        | Source dims          |
|--------------------------------|-----------------------|----------------------|
| `iso_unit`                     | `add_iso_unit`        | `isoContainer`       |
| `truck_bay`                    | `add_truck_bay`       | `truckBay`           |
| `pipe_manifold`                | `add_pipe_manifold`   | (hardcoded today; will move to assumptions) |
| `queens_pair`                  | `add_queens_pair`     | `queenTrailer`       |
| `glycol_vaporizer_with_stack`  | `add_vaporizer_stack` | `vaporizerSkid`      |
| `bog_skid`                     | `add_bog_skid`        | `bogSkid`            |
| `delivery_flange`              | `add_delivery_flange` | (hardcoded today; will move to assumptions) |

Names that need new builder fns get refactored from inline code in `build_scene()`. Each builder takes `(bpy, mats, name, pos, rotation, dims)` and emits one or more Blender objects + an empty named `anchor_<id>` at the centroid (cinematics target this empty).

## Workflow

```bash
# Scaffold a new variant from the parametric defaults
python scripts/scaffold_site.py --letter F --isos 32 --has-capture > sites/option-f.yaml

# Hand-edit positions
$EDITOR sites/option-f.yaml         # e.g. move bogCapture 5m east

# Build the .blend
blender --background --python scripts/generate_lng_site_blender.py -- \
  --site sites/option-f.yaml

# Render any cinematic against any site
blender --background --python scripts/generate_lng_cinematics.py -- \
  --site sites/option-f.yaml \
  --cinematic process-flow
```

## Migration

1. **Venv:** add `PyYAML` to `.venv` (`pip install PyYAML`). No other dependency changes.
2. **Scaffold tool first:** build `scripts/scaffold_site.py` by porting the parametric placement logic currently inside `build_scene()`. Generate `sites/option-{a..e}.yaml` by running the scaffolder for each existing option and diffing the result against the live `build_scene()` output to confirm parity.
3. **Generator dual-mode:** `generate_lng_site_blender.py` accepts either `--site sites/option-X.yaml` (new path) or `--option X` (legacy path → reads `lng-site-options.json`). Default flips to `--site` once parity is confirmed.
4. **Equipment builder refactor:** split `build_scene()`'s inline equipment construction into typed builder functions (`add_truck_bay`, `add_pipe_manifold`, etc.). Each emits a named empty at the centroid for cinematic anchoring.
5. **Cinematic integration:** `generate_lng_cinematics.py` accepts `--site`. When provided, `featureAnchors` are resolved from the site YAML; the cinematic JSON's own `featureAnchors` block becomes optional/override-only. Existing waypoints can reference anchors by name: `"lookAt": {"anchor": "cryoManifold"}` resolves at render time.
6. **Add missing dimensions to `lng-site-options.json` `assumptions`:** `pipeManifold` and `deliveryFlange` blocks (length/width/height). Today these are hardcoded inside `build_scene()`; once equipment is config-driven, all type dimensions need a source.
7. **Cleanup:** once all 5 options are migrated and cinematics tested, remove the legacy `--option` path from the Python generator. **Leave `lng-site-options.json`'s `options[]` array alone** — it's regenerated from `data.js` by `export_lng_options.mjs` and is still consumed by the browser pages (`option-a.html` through `option-e.html`). The generator simply stops reading from it.

## Validation

- Load-time schema check in `generate_lng_site_blender.py`: required keys (`site.id`, `site.letter`, `iso_array`, `equipment`), all `equipment[].type` values in the closed vocabulary, all positions are 3-element numeric arrays, all rotations are numeric. Fail fast with a line-pointing error message.
- `id` collision check: every `equipment[].id` must be unique within the file.
- Sanity bounds: warn (don't fail) if `|pos.x| > 200` or `|pos.y| > 200` or `pos.z != 0` — most sites stay within those bounds and out-of-bounds positions usually mean a typo.

## Compatibility / risk

- **Risk:** parity break — the scaffolder must reproduce existing `build_scene()` positions exactly, or Option E's cinematics will look different against the new YAML-driven build. Mitigation: render a frame from both old and new pipelines at the same camera waypoint and compare pixel-by-pixel before flipping the default.
- **Risk:** cinematic JSON anchor migration — the cinematic JSON currently has `featureAnchors` populated. Once the site YAML is authoritative, those values should either be removed (clean) or kept as override (safer during transition). Spec chooses keep-as-override to allow fallback.
- **No git** in this project (per project memory); migration runs with `.backup/` before each step. Standard practice for this codebase.

## Out of scope (followups for future sessions)

- **YAML-driven cinematics** (the "shot list DSL" Walker mentioned as #3 in the original conversation). This spec deliberately keeps cinematics in JSON.
- **Caption-only re-render path** as the routine update workflow (separate, smaller spec).
- **A second ISO array** per site (Tier-D dual-bank). Schema would extend `iso_array` to `iso_arrays:` list. Defer until a use case shows up.
- **Custom equipment types** beyond the closed vocabulary. Defer.

## Acceptance criteria

1. `python scripts/scaffold_site.py --letter F --isos 32 --has-capture` writes a valid YAML to stdout.
2. `blender --background --python scripts/generate_lng_site_blender.py -- --site sites/option-e.yaml` produces a `.blend` byte-identical (or pixel-identical in render) to the current `--option E` output.
3. `blender --background --python scripts/generate_lng_cinematics.py -- --site sites/option-e.yaml --cinematic process-flow` produces an MP4 indistinguishable from today's v1 process-flow render.
4. Editing `sites/option-e.yaml` to shift `bogCapture` by `+5 0 0` and re-running the generator visibly moves the BOG skid 5m east in the rendered output.
5. A new `sites/option-f.yaml` (hand-written or scaffolded) builds without code changes.
