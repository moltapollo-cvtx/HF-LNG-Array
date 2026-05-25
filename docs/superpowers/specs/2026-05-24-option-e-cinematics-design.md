# Option E Cinematics — Design Spec

Author scripted drone-style camera flythroughs of the Apollo LNG **Option E** Blender scene (24-ISO array with BOG capture). Three 45-second cinematics with three distinct narratives, played back two ways: as pre-rendered MP4 files in the customer deck, and as in-browser camera animations on the `option-e.html` page.

## Goals

- Render three 45-second cinematics of `models/lng-site/option-e.blend`, each telling a different story about the same site.
- Make the choreography reproducible — re-run the generator after geometry edits and the cinematics still hit the right features.
- Drive the same waypoints in-browser via `<model-viewer>` so the user can replay the flights live on the Option E page.

## Out of scope

- Cinematics for Options A–D. Architecture supports them but only Option E is authored.
- Music, narration, post-production. Renders are silent and unbranded.
- Vendor-CAD-quality geometry. We render the existing draft engineering model as-is.

## The three cinematics

| ID | Name | Story |
|---|---|---|
| `process-flow` | Process-Flow Narrative | Follow the LNG: establishing wide → transport offload → ISO array → manifold → HP Smart Queens → vaporizer → **BOG capture skid** (highlight) → delivery flange. |
| `differentiator` | Differentiator-First | Slow push-in on BOG capture skid → pull back to reveal full 2.3-acre array → sweep remaining equipment as supporting cast. |
| `scale-detail` | Scale-Then-Detail | High-altitude orbital establishing shot of pad + fence → drop to low-altitude detail pass over each major skid. |

Each: 45 seconds, 1920×1080, 30 fps, Eevee render, MP4 (H.264, yuv420p).

## Single source of truth: `option-e-cinematics.json`

One JSON file defines all three cinematics. Both the Blender generator and the browser player read it. Schema:

```jsonc
{
  "fps": 30,
  "resolution": [1920, 1080],
  "cinematics": {
    "process-flow": {
      "durationSec": 45,
      "label": "Process Flow",
      "description": "Follow the LNG through the site",
      "waypoints": [
        {
          "t": 0.0,                       // seconds from start
          "pos": [80, -60, 45],           // camera position (Blender world space)
          "lookAt": [-15, -2, 2],         // target the camera aims at
          "focal": 28,                    // mm, on 36mm sensor
          "ease": "easeInOut",            // see Easing below
          "feature": "establishing",      // optional - drives the on-screen caption
          "caption": "Apollo LNG · Option E"
        },
        { "t": 5.0, "pos": [-40, 30, 12], "lookAt": [-50, 18, 3], "focal": 35, "ease": "easeInOut", "feature": "transportOffload", "caption": "Transport Offload Bay" },
        ...
      ]
    },
    "differentiator": { ... },
    "scale-detail": { ... }
  }
}
```

**Waypoint interpolation:** between any two consecutive waypoints `A` (at `t_A`) and `B` (at `t_B`), camera position, look-at target, and focal length are interpolated along `[t_A, t_B]` using `A.ease`. Both consumers (Blender and browser) implement the same easing functions so visuals match.

**Easing modes:** `linear`, `easeIn`, `easeOut`, `easeInOut` (cubic). Applied to the normalized time parameter `(t - t_A) / (t_B - t_A)` before interpolating each channel.

**Captions:** optional `feature` + `caption` on a waypoint causes a lower-third caption to appear during that waypoint's segment. Renders as a Blender text overlay during MP4 generation and a DOM element during browser playback.

## Architecture

```
scripts/
  generate_lng_site_blender.py        (existing, unchanged)
  generate_lng_cinematics.py          NEW

models/lng-site/
  option-e.blend                       (existing)
  option-e.glb                         (existing)
  option-e-cinematics.json             NEW - hand-authored waypoints
  cinematics/                          NEW
    option-e-process-flow.mp4
    option-e-differentiator.mp4
    option-e-scale-detail.mp4

cinematic-player.js                    NEW - in-browser playback
option-e.html                          MODIFIED - mounts the player
styles.css                             MODIFIED - cinematic UI styles
```

### `scripts/generate_lng_cinematics.py`

Blender Python script. Invoked:

```sh
blender --background "models/lng-site/option-e.blend" \
  --python scripts/generate_lng_cinematics.py -- \
  --cinematic process-flow \
  --output models/lng-site/cinematics/option-e-process-flow.mp4
```

CLI flags:
- `--cinematic <id>` — which cinematic to render. `all` renders all three sequentially.
- `--output <path>` — output MP4 path (when single). Ignored if `--all`.
- `--engine eevee|cycles` — default `eevee`. Cycles only used for final-quality passes.
- `--resolution-scale <0.0-1.0>` — defaults to 1.0. Use `0.25` for fast previews.
- `--data <path>` — defaults to `models/lng-site/option-e-cinematics.json`.

Behavior:
1. Read the JSON.
2. Add (or reuse) a Camera named `Cinematic Camera` and a target Empty named `Cinematic Target`.
3. Camera has a `TRACK_TO` constraint pointing at the Empty — gives a true look-at without computing Euler rotations.
4. For each waypoint, set frame `= round(t * fps)`, keyframe camera location + camera lens + Empty location.
5. Set F-curve interpolation modes per the `ease` field of each waypoint.
6. Add text overlay using Blender's Compositor — driven by caption metadata (Eevee writes captions directly into the video).
7. Configure render: 1920×1080, 30 fps, frame range `[1, durationSec * fps]`, Eevee with 16 samples + bloom + screen-space reflections, FFmpeg MP4 muxer, H.264, yuv420p.
8. `bpy.ops.render.render(animation=True)`.

### `cinematic-player.js`

Vanilla JS module loaded by `option-e.html`. Public API:

```js
window.CinematicPlayer.attach(modelViewerElement, cinematicsJsonUrl);
// → adds UI controls beneath the model-viewer, returns a controller:
//   { play(id), pause(), stop(), on(event, fn) }
```

Implementation:
- On `play(id)`, disable `<model-viewer>`'s `auto-rotate` and `camera-controls`.
- Run a `requestAnimationFrame` loop. Each frame:
  - Compute elapsed seconds since `play()` was called.
  - Find the current segment `[A, B]` in the waypoint list.
  - Compute `u = ease((t - t_A) / (t_B - t_A))`.
  - Interpolate `pos`, `lookAt`, `focal`.
  - Convert Cartesian `(pos, lookAt)` to `<model-viewer>` spherical coords:
    - `radius = ||pos - lookAt||`
    - `theta = atan2(pos.x - lookAt.x, pos.z - lookAt.z)` (deg)
    - `phi = acos((pos.y - lookAt.y) / radius)` (deg)
  - Set `viewer.cameraTarget = "{x}m {y}m {z}m"` and `viewer.cameraOrbit = "{theta}deg {phi}deg {radius}m"`.
  - Convert focal to `field-of-view` using `fov = 2 * atan(18 / focal) * 180/π`.
- Surface the active waypoint's caption in a DOM element below the viewer.
- On completion (or `stop()`), re-enable `camera-controls` and `auto-rotate`.

### Coordinate system notes

- Blender: right-handed, Z-up, Y-forward.
- `<model-viewer>` (Three.js / glTF): right-handed, Y-up, Z-forward. The existing `.glb` export uses `export_yup=True`, so the published GLB is Y-up.
- Waypoints are authored in **Blender world space (Z-up)**. The browser player swaps axes on read: `(x, y, z) → (x, z, -y)`. This is the same convention the existing `cameraOrbit` / `cameraTarget` defaults in `lng-site-model.jsx` already use (look at the `-2m` Y vs. Blender's `-2.0` for `array_center_y`).

## Feature coordinates (Option E, derived from `generate_lng_site_blender.py`)

These are the named anchors the waypoint files reference. Coordinates are in Blender world space, meters. Computed once and recorded here so waypoint authoring is grounded.

| Feature key | Position (x, y, z) | Notes |
|---|---|---|
| `siteCenter` | `(0, 0, 0)` | Geometric center of the pad |
| `transportOffload` | `(-51.85, 18.02, 1.65)` | Truck bay, center |
| `isoArrayCenter` | `(-15.97, -2.0, 1.45)` | Center of 6×4 ISO grid |
| `isoArrayNearCorner` | `(-60.81, -11.02, 1.45)` | SW corner — good for raking shot |
| `isoArrayFarCorner` | `(28.88, 7.02, 1.45)` | NE corner |
| `cryoManifold` | `(-15.97, -17.02, 1.0)` | Center of common header |
| `queens` | `(-43.6, -19.52, 1.8)` | Midpoint of the two HP Smart Queens |
| `vaporizer` | `(44.85, -6.0, 2.1)` | Vaporizer skid, top of stack at z≈6.9 |
| `bogCapture` | `(31.85, -15.0, 1.4)` | Differentiator |
| `delivery` | `(72.85, -3.5, 1.1)` | Delivery flange riser |
| `siteWideHigh` | `(80, -60, 60)` | Composed wide for establishing shots |
| `siteWideLow` | `(80, -45, 20)` | Composed wide, lower altitude |

Site dimensions for Option E: 159.69m × 63.04m. Computed from `layout_metrics` in the existing script.

## Easing semantics (both consumers)

```text
linear(u)    = u
easeIn(u)    = u^3
easeOut(u)   = 1 - (1 - u)^3
easeInOut(u) = u<0.5 ? 4u^3 : 1 - (-2u + 2)^3 / 2
```

Implemented identically in Python (Blender) and JS.

## UI on `option-e.html`

A new section below the existing `LngSiteModelViewer`. Three pill buttons ("Process Flow", "Differentiator First", "Scale → Detail"), a slim progress bar, and a captions slot. While a cinematic plays, `camera-controls` is disabled on the viewer (it would fight the animation) and a "Skip" button replaces "Play". On finish, the viewer returns to its default orbit and auto-rotate resumes.

## Risks

- **Eevee fidelity vs. Cycles.** Eevee won't match the static Cycles renders in the screenshots. Acceptable because the geometry is draft. Cycles available via flag for a final pass.
- **Browser/Blender camera mismatch.** The two pipelines must produce visually similar shots. Tested by playing a cinematic in-browser, then comparing to the rendered MP4 of the same JSON. Easing functions must be byte-identical.
- **Render time.** 3 × 45s × 30fps = 4,050 frames. At ~1–3 seconds/frame in Eevee, that's 1–3 hours total on a laptop. Acceptable; ran once, archived.
- **Caption compositor.** Blender's text-overlay-in-compositor adds complexity. If it's flaky, fall back to baking captions in via ffmpeg post-pass.

## Verification

1. **Dry-run mode** — `--dry-run` flag prints waypoint timings, frame numbers, and feature anchors without invoking `bpy`. Confirms the JSON is well-formed.
2. **Preview render** — `--resolution-scale 0.25` produces a 480p version of all three in ~5 minutes total. Used to validate choreography before committing to full renders.
3. **Browser parity check** — open `option-e.html`, play each cinematic, eyeball-compare to the matching MP4 frame ranges.
4. **Open the .blend in Blender GUI** after the script runs (the keyframes persist) and scrub the timeline visually.

## Build sequence

1. Spec written (this file). User reviews.
2. Author `option-e-cinematics.json` with all three cinematics.
3. Write `scripts/generate_lng_cinematics.py`.
4. Dry-run to validate JSON shape.
5. Render at 0.25 scale to validate choreography.
6. Render full 1080p × 3.
7. Write `cinematic-player.js`.
8. Patch `option-e.html` + add styles.
9. Manually verify in browser.
