# HF-LNG-Array — Apollo LNG Option E Cinematic Pipeline

A configurable CAD-to-cinematic toolkit. Drives a virtual drone through a 3D
LNG site (Blender `.blend`), produces polished MP4 flyaround videos with
captions, title cards, color grade, and motion blur. Built for the Apollo
"BOG Capture Array" (Option E) layout.

## Pipeline

```
sites/option-e.yaml                  cinematics/option-e.shots.yaml
       │                                       │
       │  geometry + cinematic                 │  shot DSL + caption schema
       │  title/kicker overrides               │  + velocity_cap
       ▼                                       ▼
generate_lng_site_blender.py     →   compile_shots.py
       │  builds the .blend              │  emits per-cinematic JSON
       │                                 │  with velocity-retimed waypoints
       ▼                                 ▼
models/lng-site/option-e.blend   models/lng-site/option-e-cinematics.json
                       \           /
                        \         /
                         ▼       ▼
              render_with_progress.py
              (wraps `blender --background`; live tqdm bar)
                         │
                         ▼
              models/lng-site/cinematics/no-captions/option-e-*.mp4
                         │
                         ▼
              recaption.py
              (overlay captions + grade + title/end cards + grain)
                         │
                         ▼
              models/lng-site/cinematics/v2.02/option-e-*.mp4
```

## Quickstart

```bash
# 1. Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Compile the shot list (YAML → JSON) — fast
python scripts/compile_shots.py cinematics/option-e.shots.yaml

# 3. Quick FOV check at any (cinematic, t) — ~1 sec
python scripts/preview_shot.py --site option-e --cinematic differentiator --t 5

# 4. Full Blender render with live progress (one-time per camera change, ~95 min)
python scripts/render_with_progress.py -- \
  --cinematic all --no-captions \
  --output-dir models/lng-site/cinematics/no-captions \
  --site sites/option-e.yaml

# 5. Caption-only iteration (~19 min, no Blender)
python scripts/recaption.py cinematics/option-e.shots.yaml \
  --polish-output models/lng-site/cinematics/v2.02
```

Blender 5.x is required on `PATH` (or set `BLENDER_BIN`).

## Configuration surfaces

### `sites/option-e.yaml`
Site geometry: ISO array, equipment positions, plus cinematic-display fields:
- `cinematic_title` — title card text (default derived: `Apollo LNG · {title}`)
- `cinematic_kicker` — opening kicker (default derived: `{TITLE} · DRONE FLYTHROUGH`)

### `cinematics/option-e.shots.yaml`
Shot list DSL + caption schema:
- `velocity_cap: 10` — m/s cap; segments exceeding this get stretched
- Per-cinematic `shots:` list (types: wide, push, pull, hero, pan, orbit, fly, land, hold)
- Optional per-cinematic `captions:` block with full effect control:
  ```yaml
  captions:
    - text: "Cryogenic Manifold"
      t: 14.0
      duration: 4.0
      fade_in: 0.3
      fade_out: 0.4
      position: lower-center   # lower-center | upper-center | left | right
      font: Satoshi-Bold       # bundled stem OR /abs/path/to/font.ttf
      effect: slide-in         # fade | slide-in | typewriter | scale-up | pulse
      bold_word: Manifold      # optional teal highlight on a single word
  ```

## Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `compile_shots.py` | YAML shot list → cinematic JSON, with velocity retiming and caption schema validation |
| `generate_lng_cinematics.py` | Blender render; hides blueprint labels in cinematic mode; Eevee motion blur on by default |
| `generate_lng_site_blender.py` | Build the `.blend` from a `sites/<id>.yaml` |
| `scaffold_site.py` | Bootstrap a new site config |
| `render_with_progress.py` | Wraps the Blender run with a live tqdm progress bar (per cinematic + overall ETA) |
| `preview_shot.py` | Render a single frame at any `(cinematic, t)` for surgical FOV verification |
| `post_production.py` | Polish pipeline: re-render captions, color grade, vignette, grain, title/end cards |
| `recaption.py` | One-command caption-only iteration (no Blender required after the one-time `--no-captions` pass) |

`scripts/lib/` holds the shot-compiler internals, shot-type vocabulary, and site-config schema.

## Tests

```bash
python -m unittest discover scripts/tests
```

Coverage: shot compiler, anchor resolver, site config schema, generator parity,
shot type vocab, scaffolder.

## Project docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` carry the design specs
and execution plans for each feature pass (DSL design, YAML site config,
cinematics polish v2, caption-only re-render handoff, etc).
