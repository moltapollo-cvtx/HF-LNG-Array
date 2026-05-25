# Shot-list DSL — Design (2026-05-25)

Add a build-time DSL on top of the existing cinematic JSON so Walker (and Claude) can author cinematics in terms of *shot intent* (`hero`, `push`, `pan`, `land`) against named anchors from the site YAML, instead of editing raw `[x, y, z]` waypoint coordinates. Compiler emits the same JSON the renderer already consumes — no renderer changes.

## Why

Today, cinematics live in `models/lng-site/option-e-cinematics.json` as ~12–15 waypoints each. Every waypoint hand-codes `pos: [x, y, z]`, `lookAt: [x, y, z]`, `focal`, `ease`, `caption`. Two pain points:

1. **Authoring cost.** Editing the BOG-zoom in v1.6 required hand-computing distance/focal for two waypoints. Moving the BOG anchor in `sites/option-e.yaml` *doesn't* automatically update cinematic JSON; coordinates are duplicated.
2. **Token cost.** The cinematic JSON is ~80 lines per cinematic; a shot list of the same content would be ~20 lines with no raw coordinates. Claude reads/edits it for 1/5 the tokens, and Walker can author from scratch by writing prose-shaped YAML.

The YAML site config (Task 10 of `2026-05-25-yaml-site-config-design.md`) already provides anchor resolution at the renderer level (`{anchor: cryoManifold}` syntax). This DSL is the authoring layer above it.

## Scope

**In:**
- New per-site shot-list files at `cinematics/option-{a..e}.shots.yaml`.
- Each file groups all cinematics for that site (`process-flow`, `differentiator`, `scale-detail` for Option E).
- A compiler `scripts/compile_shots.py` that reads `*.shots.yaml` and writes `models/lng-site/*-cinematics.json`.
- A closed vocabulary of 9 shot types with smart defaults; per-shot overrides for the common knobs.
- A one-time port of the current v1.6 Option E cinematics from JSON → DSL.
- Parity tests: compiled JSON renders pixel-equivalent to today's v1.6 (within tolerance).

**Out:**
- Changes to the renderer (`scripts/generate_lng_cinematics.py`). It keeps reading JSON.
- Music sync / audio track timing.
- Absolute-time placement (`at:`) — shots are back-to-back chained; `hold` shot type fills gaps.
- Open shot vocabulary or user-defined shot macros.
- Per-shot direct `pos`/`lookAt` overrides. Shots are intent-based; if Walker needs raw coords, edit the JSON directly.

## File structure

```
cinematics/
  option-a.shots.yaml
  option-b.shots.yaml
  option-c.shots.yaml
  option-d.shots.yaml
  option-e.shots.yaml      # Walker authors here

scripts/
  compile_shots.py          # CLI: .shots.yaml → -cinematics.json
  lib/
    shot_compiler.py        # core compilation logic
    shot_types.py           # closed vocabulary + smart defaults

scripts/tests/
  test_shot_compiler.py     # unit tests on each shot type
  test_compile_parity.py    # compiled JSON should render parity to v1.6

models/lng-site/
  option-e-cinematics.json  # generated; not hand-edited going forward
```

## Schema

`cinematics/option-e.shots.yaml`:

```yaml
# Walker's source-of-truth shot list for Option E.
# Compile with: python scripts/compile_shots.py cinematics/option-e.shots.yaml

site: option-e                  # references sites/option-e.yaml for anchor resolution
fps: 30                         # optional; default 30
resolution: [1920, 1080]        # optional; default [1920, 1080]
blendFile: "models/lng-site/option-e.blend"   # optional; default per site letter
glbFile: "models/lng-site/option-e.glb"

cinematics:
  process-flow:
    label: "Process Flow"
    description: "Follow the LNG through the site, ending on delivery. Pitch-deck cut."
    duration: 45              # optional target; warn if sum of shot dur differs
    shots:
      - type: wide
        dur: 5
        subject: site
        caption: "Apollo LNG · Option E"

      - type: push
        dur: 5
        subject: transportOffload
        from: NW
        caption: "Transport Offload Bay"

      - type: hero
        dur: 4
        subject: transportOffload
        caption: "Transport Offload Bay"

      - type: fly
        dur: 8
        subject: isoArrayCenter
        caption: "24× 10K LNG ISO"

      - type: pan
        dur: 4
        subject: cryoManifold
        caption: "Cryogenic Manifold"

      - type: hero
        dur: 4
        subject: queens
        caption: "HP Smart Queens (×2)"

      - type: push
        dur: 4
        subject: vaporizer
        from: W
        caption: "Glycol-Bath Vaporizer + Stack"

      - type: hero
        dur: 5
        subject: bogCapture
        distance: 30
        focal: 40
        caption: "BOG Capture — Option E Differentiator"

      - type: land
        dur: 3
        subject: delivery
        caption: "Delivery — 550–650 PSIG"

  differentiator:
    label: "Differentiator First"
    description: "Open on BOG capture, pull back to reveal site context."
    duration: 45
    shots:
      - type: hero, dur: 4, subject: bogCapture, caption: "BOG Capture System"
      - type: pull, dur: 4, subject: bogCapture, caption: "Zero LNG Loss Without Pumps"
      - type: pull, dur: 5, subject: bogCapture, caption: "Boil-off Capture — Option E"
      - type: wide, dur: 5, subject: site, caption: "Apollo LNG — Option E"
      - type: fly,  dur: 5, subject: isoArrayCenter, caption: "24× 10K LNG ISO"
      - type: hero, dur: 4, subject: queens, caption: "HP Smart Queens"
      - type: push, dur: 4, subject: vaporizer, from: W, caption: "Glycol-Bath Vaporizer"
      - type: hero, dur: 4, subject: delivery, caption: "Delivery Flange"
      - type: hero, dur: 10, subject: bogCapture, caption: "Boil-off Capture — Option E"

  scale-detail:
    label: "Scale → Detail"
    description: "Orbital establishing then documentary detail pass."
    duration: 45
    shots:
      - type: orbit, dur: 12, subject: site, caption: "Apollo LNG · Option E"
      - type: fly, dur: 4, subject: transportOffload, caption: "Transport Offload Bay"
      - type: hero, dur: 5, subject: isoArrayCenter, caption: "24× 10K LNG ISO"
      - type: hero, dur: 4, subject: cryoManifold, caption: "Cryogenic Manifold"
      - type: hero, dur: 4, subject: queens, caption: "HP Smart Queens (×2)"
      - type: hero, dur: 4, subject: vaporizer, caption: "Glycol-Bath Vaporizer + Stack"
      - type: hero, dur: 4, subject: bogCapture, caption: "BOG Capture Skid"
      - type: land, dur: 5, subject: delivery, caption: "Delivery · 550–650 PSIG"
      - type: wide, dur: 3, subject: site, caption: "Apollo LNG · Option E"
```

### Shot vocabulary (closed, 9 types)

Each shot is a dict with `type:` (required), `dur:` (required), `subject:` (required), and any number of overrides.

| Type | Intent | Waypoints emitted | Default focal | Default distance | Default height |
|------|--------|-------------------|---------------|------------------|----------------|
| `wide` | High aerial establishing | 1 | 24mm | 100m | 60m |
| `push` | Moving toward subject | 2 (far→close) | 35→42mm | 50→25m | 12→8m |
| `pull` | Moving away from subject | 2 (close→far) | 42→35mm | 25→50m | 8→12m |
| `hero` | Held framing on subject | 2 (slow drift) | 40mm | 30m | 8m |
| `pan` | Sweeping arc past subject | 2 (entry, exit) | 38mm | 25m | 6m |
| `orbit` | Camera circles subject | N (90° / 3s) | 28mm | 80m | 40m |
| `fly` | Moving aerial pass | 2 (high+far → mid+close) | 28mm | 80→30m | 40→15m |
| `land` | Final settling shot | 1 | 50mm | 20m | 5m |
| `hold` | Extends previous pose | 0 (time-only) | — | — | — |

### Shot fields

- `type:` (required) — one of the 9 above.
- `dur:` (required) — duration in seconds. Floats allowed.
- `subject:` (required) — anchor name from the site YAML, OR `site` (uses site centroid). Validated at compile time.
- `caption:` (optional, default empty) — single string for the duration of the shot.
- `from:` (optional, applies to `push`/`fly`) — approach direction as a compass token: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`. Default `S`.
- `focal:` (optional) — override default focal length (mm). When the shot emits 2 waypoints with differing defaults, this sets both.
- `distance:` (optional) — override default subject distance (m).
- `height:` (optional) — override camera height z (m).
- `ease:` (optional) — `linear` | `easeIn` | `easeOut` | `easeInOut`. Default `easeInOut`.

### Compile output

The compiler emits a JSON file structurally identical to today's `option-e-cinematics.json`:

```json
{
  "source": "Compiled from cinematics/option-e.shots.yaml on 2026-05-25T20:00:00",
  "fps": 30,
  "resolution": [1920, 1080],
  "blendFile": "models/lng-site/option-e.blend",
  "glbFile": "models/lng-site/option-e.glb",
  "cinematics": {
    "process-flow": {
      "label": "Process Flow",
      "description": "...",
      "durationSec": 42.0,
      "waypoints": [
        {"t": 0.0, "pos": [...], "lookAt": [...], "focal": 24, "ease": "easeInOut", "feature": "site", "caption": "Apollo LNG · Option E"},
        ...
      ]
    },
    ...
  }
}
```

- `featureAnchors` block is **omitted** from the emitted JSON. The renderer's `--site` flag resolves anchors live; per-cinematic JSON no longer duplicates positions.
- `feature` waypoint field is set to the `subject:` from the shot, so the renderer keeps existing caption/feature behavior.
- `source:` field carries a timestamp + the source `.shots.yaml` path for debugging.

## Compilation logic per shot type

### `wide` (1 waypoint)

Emits one waypoint at `t = start_t`. `from:` is ignored (wide is always a fixed aerial pose to the SE for visual consistency across cinematics):
```
pos    = subject_pos + offset(SE, distance=100, height=60)
lookAt = subject_pos + (0, 0, 5)
focal  = 24
```

### `push` (2 waypoints)

Emits two waypoints at `t = start_t` and `t = start_t + dur`:
```
start: pos = subject_pos + offset(from, distance=50, height=12), focal=35
end:   pos = subject_pos + offset(from, distance=25, height=8),  focal=42
both:  lookAt = subject_pos + (0, 0, 1.5)
```

### `pull` (2 waypoints)

Inverse of `push`. Start close, end far.

### `hero` (2 waypoints with slow drift)

Emits two waypoints at `t = start_t` and `t = start_t + dur`:
```
start: pos = subject_pos + offset(SW, distance=30, height=8)
end:   pos = subject_pos + offset(SW, distance=32, height=9)   # 2m drift back+up
both:  lookAt = subject_pos + (0, 0, 1.5)
focal: 40
```

The drift gives a subtle Ken-Burns feel and reads as more cinematic than a frozen frame, while still feeling like a "held" hero shot.

### `pan` (2 waypoints)

Emits two waypoints at `t = start_t` and `t = start_t + dur`:
```
start: pos = subject_pos + offset(SW, distance=25, height=6)
end:   pos = subject_pos + offset(SE, distance=25, height=6)
both:  lookAt = subject_pos + (0, 0, 1.5)
focal: 38
```

Camera arcs from SW to SE around the subject — a 90° sweep that lets the audience see the subject from changing angles.

### `orbit` (N waypoints)

Emits `ceil(dur / 3) + 1` waypoints (quarter turn per ~3s):
```
For i in 0..N-1:
  angle = i * (360° / N)
  pos = subject_pos + (cos(angle)*80, sin(angle)*80, 40)
  lookAt = subject_pos + (0, 0, 2)
  focal: 28
```

### `fly` (2 waypoints)

Emits two waypoints:
```
start: pos = subject_pos + offset(from, distance=80, height=40)
end:   pos = subject_pos + offset(from, distance=30, height=15)
both:  lookAt = subject_pos + (0, 0, 2)
focal: 28
```

### `land` (1 waypoint)

Emits one waypoint at `t = start_t + dur`:
```
pos = subject_pos + offset(SE, distance=20, height=5)
lookAt = subject_pos + (0, 0, 2)
focal: 50
```

### `hold` (0 waypoints)

Adds `dur` seconds to the timeline without emitting a waypoint. The previous shot's end pose is held via the renderer's interpolation (linear hold).

### `offset(direction, distance, height)`

```
direction → unit vector in XY:
  N:  ( 0,  1, 0)
  NE: ( √2/2,  √2/2, 0)
  E:  ( 1,  0, 0)
  SE: ( √2/2, -√2/2, 0)
  S:  ( 0, -1, 0)
  SW: (-√2/2, -√2/2, 0)
  W:  (-1,  0, 0)
  NW: (-√2/2,  √2/2, 0)

return (unit.x * distance, unit.y * distance, height)
```

So `offset(NW, 50, 12)` from subject `[0, 0, 0]` is `[-35.36, 35.36, 12]`.

### Smart-default override resolution

When the shot has explicit `focal:`, `distance:`, `height:`, or `ease:`, the compiler uses those instead of the shot-type defaults.

For 2-waypoint shots, an explicit `focal:` sets both waypoints to that value (no interpolation). Explicit `distance:` and `height:` apply to BOTH waypoints (the user is overriding the motion to "no zoom-in", essentially a static hero pose). To preserve the push/pull motion while overriding focal, set `focal:` explicitly but leave `distance:` and `height:` to defaults.

## Error handling

Compile is strict — exit nonzero with a line-pointing message on:

1. **Unknown shot type** (`type: zoom` when zoom isn't in the vocabulary). Message: `cinematics/option-e.shots.yaml:42: unknown shot type 'zoom'. Allowed: wide, push, pull, hero, pan, orbit, fly, land, hold.`
2. **Unknown subject** (anchor not in site YAML). Message: `cinematics/option-e.shots.yaml:42: subject 'bogCapture' not found in sites/option-e.yaml. Known anchors: site, transportOffload, cryoManifold, queens, vaporizer, delivery.`
3. **Missing required field** (`type:`, `dur:`, `subject:`). Message: `cinematics/option-e.shots.yaml:42: shot missing required field 'dur'.`
4. **Bad `from:` direction** (not in the compass token set). Message: `cinematics/option-e.shots.yaml:42: 'from: northwest' invalid. Use N|NE|E|SE|S|SW|W|NW.`
5. **Empty `shots:` list** in any cinematic. Message: `cinematics/option-e.shots.yaml: 'process-flow' has no shots.`
6. **Negative or zero `dur:`** on any shot. Message: `cinematics/option-e.shots.yaml:42: dur must be positive, got 0.`

Compile is lenient on:

1. **Sum of `dur:` ≠ target `duration:`** — emit a warning to stderr; the actual cinematic duration is the sum.
2. **`fps:`, `resolution:`, `blendFile:`, `glbFile:` omitted** — defaults applied.

## Compatibility / risk

- **Risk:** the smart-default poses don't reproduce Walker's v1.6 hand-tuned cinematics. Mitigation: parity test renders Option E via both paths and compares pixel diff; if diff > threshold, tune default values until acceptable, OR adjust the one-time port to use explicit overrides for the divergent shots.
- **Risk:** the YAML port loses subtle motion variety in v1.6. v1.6 has 15 process-flow waypoints; a 9-shot DSL version emits 14-16 waypoints (count varies by shot type). If specific motion is lost, increase shot granularity (smaller `dur:`, more shots) or fall back to JSON for that cinematic.
- **No git** in this project; backup-first as in prior specs.
- **Renderer untouched** — the existing `option-e-cinematics.json` keeps working. The DSL is purely build-time. Worst case: revert by not running `compile_shots.py`.

## Out of scope (deferred to followups)

- **Variable shot types** beyond the 9 listed.
- **Per-shot waypoint overrides** (`pos: {anchor: X, offset: [...]}`). Use raw JSON if needed.
- **Music / audio synchronization** (`at:` timestamps).
- **Looping / sub-clip references** in shot lists.
- **Cross-site cinematics** (a cinematic that traverses Option E + Option F). Out of scope.

## Acceptance criteria

1. `python scripts/compile_shots.py cinematics/option-e.shots.yaml --out /tmp/out.json` exits 0 and writes a valid JSON.
2. The generated JSON renders via `generate_lng_cinematics.py` without errors.
3. A parity test renders Option E via the compiled JSON and via the hand-tuned v1.6 JSON, then frame-diffs them. Mean pixel diff across 3 sampled frames is **< 25/255** (looser than the site-config Task 9 bound because smart defaults won't reproduce hand-tuned poses exactly; cinematic backgrounds remain visually plausible).
4. Authoring a new cinematic for Option F: a fresh `cinematics/option-f.shots.yaml` written by hand compiles and renders without code changes.
5. Editing a position in `sites/option-e.yaml` (e.g. moving `bogCapture` +5m east) and recompiling Option E shots produces a new JSON whose `bogCapture`-targeting waypoints reflect the new position — no hand-touching the shots YAML or JSON.
6. Unit tests for the compiler (one per shot type) pass.
