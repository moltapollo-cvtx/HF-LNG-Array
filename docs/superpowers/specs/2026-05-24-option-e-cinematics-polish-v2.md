# Option E Cinematics — Polish Pass v2 (Path C, full production)

**Status:** Session 1 complete (Phases 0, 5, 5.5). Sessions 2 + 3 queued.
**Started:** 2026-05-24
**Session 1 finished:** 2026-05-24 — v1.5 deliverable shipped at `models/lng-site/cinematics/v1.5/`
**Decision record:** Path C selected over Path A/B. Lighting vibe: golden-hour drama. Audio: NONE (user declined — leaves room for voiceover later, or stays silent).
**Predecessor:** `2026-05-24-option-e-cinematics-design.md` (original draft cinematics spec).

## Goal
Mature the 3 existing Option E cinematics from "draft engineering render" to "investor-pitch-grade deliverable." Original spec deferred audio, post-production, vendor CAD quality to "out of scope." This polish pass takes on post-production + lighting + camera polish + targeted geometry detail (but stays in the draft-engineering lineage — no full vendor CAD swap).

## Out of scope (carried forward)
- Audio bed, SFX, music (user declined)
- Voiceover narration (deferred — Phase 5 leaves silent headroom)
- Full vendor-CAD geometry replacement (Phase 1 adds *detail* to existing geometry, doesn't replace)
- 4K master (1080p stays the master; can upscale later)
- Vertical 9:16 social cut (not yet asked for)

## Inputs (untouched — copied to `.backup/` before any edits)
- `models/lng-site/option-e.blend`
- `models/lng-site/option-e-cinematics.json`
- `models/lng-site/cinematics/option-e-{process-flow,differentiator,scale-detail}.mp4` (3 originals, 17-20 MB each)
- `scripts/generate_lng_site_blender.py` (472 lines, do not edit — copy & extend)
- `scripts/generate_lng_cinematics.py` (445 lines, do not edit — copy & extend)
- `cinematic-player.js`, `option-e.html`, `styles.css`

## New files (this polish pass)
- `assets/hdri/kloppenheim_06_puresky_4k.exr` — golden-hour HDRI, Polyhaven CC0
- `assets/fonts/Satoshi-Variable.ttf` — Apollo design-system font
- `scripts/generate_lng_site_polished.py` — v2 generator (copy of generate_lng_site_blender.py + detail hooks + HDRI + lighting)
- `scripts/render_cinematics_polished.py` — v2 renderer (DOF, bezier, handheld, Cycles hero pass)
- `scripts/post_production.py` — pure-Python (Pillow + ffmpeg subprocess) post-production toolchain
- `models/lng-site/option-e-v2.blend` + `.glb`
- `models/lng-site/option-e-v2-night.blend` (for day-to-night variant)
- `models/lng-site/option-e-cinematics-v2.json` — bezier handles, DOF targets, handheld config
- `models/lng-site/cinematics/v2/option-e-{process-flow,differentiator,scale-detail}.mp4` — final polished
- `models/lng-site/cinematics/v2/option-e-scale-detail-night.mp4` — night variant
- `models/lng-site/cinematics/v1.5/option-e-{...}.mp4` — Phase-5-only pass over existing MP4s (immediate v1.5 release)

## Tooling state (verified 2026-05-24)
- Blender 5.1.2 at `/opt/homebrew/bin/blender`, bundled Pillow 12.2.0 (in `/Applications/Blender.app/Contents/Resources/5.1/python/bin/`)
- ffmpeg 8.1.1 at `/opt/homebrew/bin/ffmpeg`
- Disk free: 3.2 TB
- Apollo project: NOT a git repo → backup-first strategy required
- System Python (`/opt/homebrew/bin/python3.14`): no Pillow installed; post_production.py uses Blender's bundled Python OR system Python+venv (TBD; safer to invoke via Blender Python)

## Phases & estimates

| # | Phase | My-time | Render-time | Session | Status |
|---|---|---|---|---|---|
| 0 | Setup: backups, asset downloads, plan file | 0.5h | 0 | 1 | ✅ done |
| 5 | Post-production toolchain (title card, captions, grade, vignette, grain, concat) | 2-3h | 0 | 1 | ✅ done |
| 5.5 | Apply Phase 5 to existing MP4s → v1.5 deliverable | 0.25h | 0.5h | 1 | ✅ done (6:48) |
| 1 | Detailed geometry (BOG, vaporizer, beacons, signage) | 2-3h | 0 | 2 | pending |
| 2 | HDRI + ground extension + lighting | 1-1.5h | 0 | 2 |
| 3 | Camera path polish (bezier, shake, DOF) | 1-1.5h | 0 | 2 |
| 4 | Animated equipment (steam, beacons, truck) | 1.5-2h | 0 | 2 |
| 6 | Day-to-night variant scene setup | 0.5h | 0 | 3 |
| 7 | Render Eevee passes (3 day + 1 night) | 0 | 2-3h | 3 |
| 8 | Render Cycles hero passes (~16s footage) | 0 | 1-2h | 3 |
| 9 | Composite, post-prod, encode | 0.5h | 0.5h | 3 |
| 10 | Verify, integrate into sitecinema skill, regression | 0.5h | 0 | 3 |

## Phase 0 — Setup details

```bash
APOLLO=~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2
mkdir -p "$APOLLO/.backup" "$APOLLO/assets/hdri" "$APOLLO/assets/fonts" "$APOLLO/models/lng-site/cinematics/v1.5" "$APOLLO/models/lng-site/cinematics/v2"
cp "$APOLLO/models/lng-site/option-e.blend" "$APOLLO/.backup/"
cp "$APOLLO/models/lng-site/option-e-cinematics.json" "$APOLLO/.backup/"
cp -r "$APOLLO/models/lng-site/cinematics" "$APOLLO/.backup/cinematics-originals"
cp "$APOLLO/scripts/generate_lng_site_blender.py" "$APOLLO/.backup/"
cp "$APOLLO/scripts/generate_lng_cinematics.py" "$APOLLO/.backup/"

# Satoshi font (fontshare, free)
curl -L -o /tmp/satoshi.zip "https://api.fontshare.com/v2/fonts/download/satoshi"
unzip -j /tmp/satoshi.zip "Satoshi_Complete/Fonts/Variable/Satoshi-Variable.ttf" -d "$APOLLO/assets/fonts/"

# HDRI (deferred to Session 2 — Phase 5 doesn't need it)
# curl -L -o "$APOLLO/assets/hdri/kloppenheim_06_puresky_4k.exr" \
#   "https://dl.polyhaven.org/file/ph-assets/HDRIs/exr/4k/kloppenheim_06_puresky_4k.exr"
```

## Phase 5 — Post-production toolchain (THIS SESSION)

Build `scripts/post_production.py`. Pure Python. Uses Pillow (via system Python with venv OR Blender Python — TBD when writing). Calls ffmpeg as subprocess.

### Sub-features

**A. Title card generator** (5 sec @ 30fps = 150 frames)
- Background: Apollo navy `#0d1117` with subtle teal radial gradient toward upper-right
- Centered title text: site name, Satoshi 96pt bold weight, white, letter-spacing tightened
- Subtitle below: site subtitle, Satoshi 28pt medium, teal `#2dd4bf`
- Optional small mark/logo top-right (Apollo gold)
- Bottom-left tiny kicker: "DRONE FLYTHROUGH · OPTION E"
- Animation: fade in over 1.0s, hold 3.0s, fade out 1.0s
- Output: PNG sequence + ffmpeg-encoded short mp4 at same fps/resolution as main cinematic

**B. End card generator** (3 sec @ 30fps = 90 frames)
- Background: Apollo navy with subtle teal gradient bottom-up
- Title: "[Customer-supplied CTA, default to: Apollo Energy Group · LNG Solutions]"
- Subtitle: contact line (email/URL — placeholder until user provides)
- Fade in 0.5s, hold 2.0s, fade out 0.5s

**C. Caption burn-in (upgrade from existing Pillow burn)**
- Replaces `burn_captions_with_pillow` from generate_lng_cinematics.py:281
- New behavior:
  - Use Satoshi-Variable.ttf instead of HelveticaNeue fallback
  - Animate fade-in over 0.3s when caption changes, hold, fade-out 0.4s before next caption
  - Parse `**bold**` markdown in caption text → render bold portions in teal
  - Background: rounded pill, 16px radius, slight drop-shadow, `rgba(0,0,0,0.65)` fill
  - Position: lower-third (8% from bottom), centered
  - Font size: 36pt at 1080p (was ~34pt before — slightly bigger for readability)

**D. Color grade (ffmpeg curves filter)**
- Lift shadows toward Apollo navy: `r='0/30 64/96 128/144 192/192 255/255':g='0/35 64/90 128/138 192/188 255/255':b='0/50 64/100 128/148 192/198 255/255'`
- Crush deepest blacks slightly: blackpoint set to 8/255
- Warm midtones: +5% red, +3% yellow in 96-192 range
- Subtle teal cast in 192-255 highlights

**E. Vignette** (ffmpeg vignette filter)
- `vignette='PI/4.5':eval=init` — moderate corner darkening, no animation

**F. Film grain** (ffmpeg `noise` filter)
- `noise=alls=8:allf=t+u` — subtle temporal noise, simulates film grain

**G. Concatenation** (ffmpeg concat demuxer)
- title_card.mp4 → cinematic_with_captions_graded_grain_vignette.mp4 → end_card.mp4
- Stream copy where possible; re-encode only when stream specs differ

### CLI

```
python3 scripts/post_production.py \
  --input path/to/raw-cinematic.mp4 \
  --captions path/to/cinematics.json#process-flow \
  --title "Apollo LNG · Option E" \
  --subtitle "Tier C · BOG Recovery" \
  --end-title "Apollo Energy Group · LNG Solutions" \
  --end-subtitle "Contact: walker@apollogroup.energy" \
  --font assets/fonts/Satoshi-Variable.ttf \
  --grade golden-hour \
  --vignette \
  --grain \
  --output path/to/polished.mp4

# Batch:
python3 scripts/post_production.py batch \
  --input-dir models/lng-site/cinematics \
  --captions models/lng-site/option-e-cinematics.json \
  --output-dir models/lng-site/cinematics/v1.5 \
  --title "Apollo LNG · Option E" \
  --subtitle "Tier C · BOG Recovery"
```

## Phase 1 — Detailed geometry (SESSION 2)

`scripts/generate_lng_site_polished.py` — copy `generate_lng_site_blender.py`, augment:

1. **BOG capture skid** (`generate_lng_site_blender.py:add_equipment_skid` analog):
   - Pressure relief vents: 3× cylinders on top, h=0.6m r=0.08m, mat=apollo_navy
   - Pipework hookups: 2× cryo pipe stub on inlet face, 1× warm gas stub on outlet face (uses `add_pipe` from existing script)
   - Valve cluster on inlet: 4× sphere primitives (radius 0.12m) with cylinder stems
   - Instrumentation cabinet: small cube 0.6×0.4×0.8m on visible face, mat=apollo_navy + door indent
   - Gold nameplate: cube 0.6×0.04×0.18m, mat=apollo_gold, with `add_label` "BOG CAPTURE — APOLLO" 0.12 size
   - Knockout drum: horizontal cylinder 1.2m × r=0.4m at one end
   - Hazard signage strip: yellow-black cube along upper edge

2. **Vaporizer + stack** (existing has skid + cylinder):
   - Heat exchanger fins: array of thin cubes (0.05×0.45×0.8m) wrapped around lower body via Python loop
   - Drainage grating: subdivided plane around base, mat=fence
   - Glycol bath access panel: cube on top of skid with apollo_navy
   - Stack guy-wires: 3× pipe primitives from top of stack to ground at 120° spacing
   - Warning stripes near top: 2× thin yellow rings (torus primitives)
   - Gold nameplate: apollo_gold label on skid front

3. **Safety beacons** (new):
   - 4× perimeter poles at corners (height 8m, r=0.05m, apollo_navy)
   - Beacon at top: small sphere r=0.18m with emission material
   - Animation hook: emission strength keyframed in Phase 4

4. **ISO array (light upgrade)**:
   - Valve handles: small spheres (r=0.05m) on each valve cabinet face
   - Hose connections: 2× curved pipe segments between every 3rd ISO pair, mat=cryo

## Phase 2 — HDRI + lighting (SESSION 2)

In `generate_lng_site_polished.py`:

```python
def setup_world_hdri(bpy, hdri_path: Path):
    world = bpy.data.worlds["World"] if "World" in bpy.data.worlds else bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    env_tex = nt.nodes.new("ShaderNodeTexEnvironment")
    env_tex.image = bpy.data.images.load(str(hdri_path))
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env_tex.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    bpy.context.scene.world = world

def setup_ground_extension(bpy, mats):
    # 1000m × 1000m subdivided plane around the site, displaced w/ noise
    bpy.ops.mesh.primitive_plane_add(size=1000, location=(0, 0, -0.5))
    plane = bpy.context.object
    plane.name = "Ground extension"
    # Add subdivision + noise modifier for subtle terrain
    mod = plane.modifiers.new("Subdivide", "SUBSURF")
    mod.levels = 4
    assign(plane, mats["pad"])

def setup_golden_hour_sun(bpy):
    bpy.ops.object.light_add(type="SUN", location=(50, -50, 30))
    sun = bpy.context.object
    sun.data.energy = 3.5
    sun.data.color = (1.0, 0.72, 0.52)  # warm 4200K
    sun.data.angle = math.radians(2.5)  # softens shadows slightly
    sun.rotation_euler = (math.radians(70), 0, math.radians(35))  # low west-southwest
```

Eevee config:
```python
scene.eevee.taa_render_samples = 64
scene.eevee.use_bloom = True
scene.eevee.bloom_intensity = 0.04
scene.eevee.use_ssr = True
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 1.5
scene.view_settings.view_transform = "Filmic"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0.5
```

## Phase 3 — Camera path polish (SESSION 2)

`option-e-cinematics-v2.json` extends existing waypoint schema:

```jsonc
{
  "handheld": { "rotation_deg": 0.4, "position_m": 0.02, "frequency_hz": 1.5 },
  "cinematics": {
    "differentiator": {
      "waypoints": [
        {
          "t": 0.0, "pos": [...], "lookAt": [...], "focal": 70,
          "ease": "easeOut",
          "handle_left":  { "tension": 0.6, "bias": -0.1 },
          "handle_right": { "tension": 0.4, "bias":  0.0 },
          "dof": { "target_anchor": "bogCapture", "fstop": 2.8 }
        }
      ]
    }
  }
}
```

`render_cinematics_polished.py` extends `keyframe_cinematic` to:
- Apply `handle_left`/`handle_right` as Blender F-curve handle adjustments
- When `dof.target_anchor` present, enable camera DOF, set focus object to a small empty at that anchor position, keyframe `fstop`
- Read scene-level `handheld` config, add Perlin-noise driver to camera location and rotation

## Phase 4 — Animated equipment (SESSION 2)

- Vaporizer stack steam: smoke domain + flow object at top of stack
- Safety beacons: emission keyframed 0→1→0 every 1.5s (animation driver, no per-beacon keys)
- Truck roll-in (process-flow cinematic only, 8-15s window): single low-poly tractor-trailer animated along x-axis into the offload bay; hidden in other cinematics via scene collection visibility

## Phase 5.5 — Apply Phase 5 to existing v1 MP4s

After Phase 5 toolchain is built, run it against existing MP4s with `--no-rerender` (skip caption rebuild, since v1 already has captions burned in — just add title/end cards + color grade + vignette + grain):

```bash
for c in process-flow differentiator scale-detail; do
  python3 scripts/post_production.py \
    --input "models/lng-site/cinematics/option-e-${c}.mp4" \
    --no-rerender-captions \
    --title "Apollo LNG · Option E" \
    --subtitle "Tier C · BOG Recovery" \
    --output "models/lng-site/cinematics/v1.5/option-e-${c}.mp4"
done
```

This is the **visible immediate win** of session 1 — user sees polished cinematics before any geometry/lighting re-render.

## Phase 6 — Day-to-night variant (SESSION 3)

- Duplicate `option-e-v2.blend` → `option-e-v2-night.blend`
- Swap HDRI: load `belfast_sunset_puresky_4k.exr` or dial existing HDRI exposure to -3 EV
- Boost safety beacon emission strengths 20×
- Add 6× sodium-vapor area lights around the pad: 2200K, energy 80W, low intensity
- Re-render scale-detail only

## Phase 7 — Render commands

```bash
APOLLO=~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2

# Day Eevee passes (all 3 cinematics)
blender --background --python "$APOLLO/scripts/render_cinematics_polished.py" -- \
  --cinematics "$APOLLO/models/lng-site/option-e-cinematics-v2.json" \
  --blend "$APOLLO/models/lng-site/option-e-v2.blend" \
  --output-dir "$APOLLO/models/lng-site/cinematics/v2/eevee" \
  --engine eevee

# Cycles hero passes (BOG capture lingers only)
blender --background --python "$APOLLO/scripts/render_cinematics_polished.py" -- \
  --cinematics "$APOLLO/models/lng-site/option-e-cinematics-v2.json" \
  --blend "$APOLLO/models/lng-site/option-e-v2.blend" \
  --output-dir "$APOLLO/models/lng-site/cinematics/v2/cycles-hero" \
  --engine cycles --hero-only

# Night variant (scale-detail only)
blender --background --python "$APOLLO/scripts/render_cinematics_polished.py" -- \
  --cinematics "$APOLLO/models/lng-site/option-e-cinematics-v2.json" \
  --blend "$APOLLO/models/lng-site/option-e-v2-night.blend" \
  --output-dir "$APOLLO/models/lng-site/cinematics/v2/night" \
  --narrative scale-detail
```

## Phase 9 — Final composite + post-prod

```bash
# Composite Cycles hero shots into Eevee main pass (per-frame swap)
python3 scripts/composite_hero_pass.py \
  --eevee-dir models/lng-site/cinematics/v2/eevee \
  --cycles-dir models/lng-site/cinematics/v2/cycles-hero \
  --hero-frames "differentiator:1-240,process-flow:1050-1170" \
  --output models/lng-site/cinematics/v2/composited

# Apply Phase 5 post-production
python3 scripts/post_production.py batch \
  --input-dir models/lng-site/cinematics/v2/composited \
  --captions models/lng-site/option-e-cinematics-v2.json \
  --output-dir models/lng-site/cinematics/v2 \
  --title "Apollo LNG · Option E" \
  --subtitle "Tier C · BOG Recovery"
```

## Phase 10 — Verify + integrate

- Run `python3 ~/.claude/skills/sitecinema/tests/run_option_e_regression.py` to confirm v1 pipeline still passes (we didn't break anything)
- Update sitecinema skill: pull post_production.py logic into `~/.claude/skills/sitecinema/scripts/post_production.py`; add post-prod fields to site.schema.json
- Update `option-e.html` to embed v2 MP4s with a "v1 / v1.5 / v2" toggle for A/B comparison
- Re-zip sitecinema skill (`~/.claude/skills/sitecinema.zip`)

## Success criteria

1. **v1.5 deliverable** (Session 1): 3 MP4s with title cards, end cards, color grade, vignette, grain. Look immediately more "produced." Same camera, same geometry, same captions (burned-in v1 captions stay).
2. **v2 deliverable** (Session 3): 3 MP4s with new detailed geometry, golden-hour HDRI lighting, bezier camera motion + DOF, Cycles-quality hero shots, post-production from v1.5. Looks like a real LNG-vendor marketing video.
3. **Night variant** (Session 3): scale-detail rendered against night scene with practical lighting. Stylized counterpart.
4. **Regression intact**: sitecinema skill still validates Option E pipeline.
5. **Backup intact**: all originals in `.backup/`, available for rollback.

## Risks

- **Blender Python version mismatch**: Pillow lives in Blender's bundled Python; system Python doesn't have it. post_production.py must either use Blender Python OR install Pillow in a venv. **Mitigation:** prefer system Python + venv for post-prod (more portable), Blender Python only during render.
- **Render time**: 3 cinematics × 45s × 30fps + night variant = ~5,400 frames at full quality. Eevee ~1-2 sec/frame on M-series Mac = 1.5-3 hours. Cycles hero pass ~10-15 sec/frame for ~480 frames = 1-2 hours. **Mitigation:** Session 3 budget is afk render time.
- **Phase 5 → existing MP4s with re-burned captions**: existing MP4s already have captions burned in (Pillow over Eevee renders). Re-running caption pass would double-burn. **Mitigation:** add `--no-rerender-captions` flag; for v1.5 we ONLY add title/end cards + grade + vignette + grain.
- **HDRI download size**: 4K EXR is ~50-100 MB. **Mitigation:** disk has 3.2 TB, fine.
- **Color grade taste**: golden-hour grade is subjective. **Mitigation:** Phase 5 outputs both a graded and ungraded version; user picks. Toggleable via `--grade off|golden-hour|teal|none`.

## What this session ships

**Session 1 deliverables (TODAY):**
- This plan file
- `.backup/` with all originals
- `assets/fonts/Satoshi-Variable.ttf`
- `scripts/post_production.py` (full Phase 5 toolchain)
- `models/lng-site/cinematics/v1.5/option-e-{process-flow,differentiator,scale-detail}.mp4` (3 polished MP4s with title cards, end cards, color grade, vignette, grain)
- Memory update pointing at this spec for session pickup

**NOT shipping this session:**
- Phases 1, 2, 3, 4, 6, 7, 8, 9, 10 (queued for sessions 2 + 3)

## Session 1 — actual results (2026-05-24)

### Built
- `scripts/post_production.py` (~530 lines). Subcommands: `single` and `batch`. Default keeps v1 burned-in captions (`--rerender-captions` opt-in for v2 caption animations + `**bold**`→teal markdown).
- `.venv/` at repo root: Python 3.14 + Pillow 12.2.0. **System Python + venv path chosen** (plan's recommendation). Activate: `source .venv/bin/activate`.
- `assets/fonts/Satoshi-Variable.ttf` + `Satoshi-Bold.otf` + `Satoshi-Medium.otf` + `Satoshi-Regular.otf` (extracted from fontshare zip; path `Satoshi_Complete/Fonts/TTF/` not `Variable/` as plan said).
- `.backup/` with all originals (option-e.blend, option-e-cinematics.json, both generator scripts, full cinematics-originals/ dir).
- `models/lng-site/cinematics/v1.5/option-e-{process-flow,differentiator,scale-detail}.mp4` — 53s each (5s title + 45s graded v1 + 3s end card), libx264 CRF 18, ~155 MB each.

### Spec-vs-built deltas
- Plan's curves spec was 8-bit pairs (`0/30 64/96 ...`); ffmpeg `curves` filter requires normalized [0,1]. Added `_normalize_curve()` helper so spec format stays readable.
- Title card subtitle: in `batch` mode, defaults to per-clip JSON `label` ("Process Flow", "Differentiator First", "Scale → Detail"). Plan example hard-coded "Tier C · BOG Recovery"; that's still available via `--subtitle "..."`.
- Grade variants implemented: `golden-hour`, `teal`, `off`/`none`. (Plan listed `off|golden-hour|teal|none`.)
- "Crush deepest blacks slightly: blackpoint set to 8/255" — not implemented. The curves spec given already lifts shadows; adding a black crush after would fight the lift. Decided to ship as-is; revisit if Walker wants more contrast.

### File size note
v1.5 outputs are ~155 MB each (24 Mbps) due to CRF 18 + grain filter (grain is high-entropy → poor compression). Originals were ~20 MB at 3.2 Mbps. If smaller files are needed for sharing, bump `--crf` to 22 (re-encode via `apply_filters` block in `post_production.py`); expect 4-5× smaller, still pitch-grade clean.

### Resume instructions for Session 2 (Phases 1-4)
1. Activate venv: `cd ~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2 && source .venv/bin/activate`
2. Download HDRI (deferred from Phase 0):
   ```bash
   curl -L -o assets/hdri/kloppenheim_06_puresky_4k.exr \
     "https://dl.polyhaven.org/file/ph-assets/HDRIs/exr/4k/kloppenheim_06_puresky_4k.exr"
   ```
3. Copy generators: `cp scripts/generate_lng_site_blender.py scripts/generate_lng_site_polished.py` then add Phase 1 + 2 hooks.
4. Copy renderer: `cp scripts/generate_lng_cinematics.py scripts/render_cinematics_polished.py` then add Phase 3 hooks (bezier, DOF, handheld).
5. Phase 5 toolchain already supports `--rerender-captions` for v2 caption animations.

### CLI cheatsheet
```bash
source .venv/bin/activate

# Single clip:
python scripts/post_production.py single \
  --input  models/lng-site/cinematics/option-e-process-flow.mp4 \
  --output /tmp/test.mp4 \
  --captions models/lng-site/option-e-cinematics.json#process-flow \
  --subtitle "Process Flow"

# Batch (this is what shipped v1.5):
python scripts/post_production.py batch \
  --input-dir  models/lng-site/cinematics \
  --output-dir models/lng-site/cinematics/v1.5 \
  --captions   models/lng-site/option-e-cinematics.json \
  --title      "Apollo LNG · Option E" \
  --end-title  "Apollo Energy Group · LNG Solutions" \
  --end-subtitle "walker@apollogroup.energy"
```
