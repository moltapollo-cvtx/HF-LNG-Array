# Option E Cinematics — Walker Feedback Handoff (2026-05-24)

**Session 1 of polish pass shipped v1.5 deliverable.** Walker reviewed the 3 polished MP4s and surfaced 4 specific issues. All 4 are **v1 cinematic problems** (camera waypoints + caption timing in the JSON) — the polish pass (title cards, grade, vignette, grain) just made them more visible. **None require touching `scripts/post_production.py`.**

**Read these first on resume:**
- Polish spec: `~/Apollo.Group/Tech/High-Flow LNG Array-2/docs/superpowers/specs/2026-05-24-option-e-cinematics-polish-v2.md`
- This file (feedback + fix targets)
- Memory pointer: `~/.claude/projects/-Users-wwa/memory/project_option_e_polish.md`

---

## Walker's feedback (verbatim, 2026-05-24)

> "The Glycol Bath Vaporizer Plus Stack, the cryogenic manifold should be showing when the long blue pipes are revealed, currently, it shows somewhere around the 24 ISO tanks. The BOG Capture Skid is zoomed way too far in. I need these transitions to be much more seamless and gradual. It is way too jerky, and the camera is whipping around."

Four distinct issues:
1. **Cryogenic Manifold caption mistimed** — appears later than the visual reveal of the blue pipes
2. **Glycol Bath Vaporizer + Stack caption** — likely same class of issue (caption not aligned to visual reveal)
3. **BOG Capture skid zoomed in too tight** — differentiator opens at focal 70 from ~13m away
4. **Camera whipping / jerky transitions** — waypoint velocities vary wildly (8m/4s up to 78m/5s)

---

## Issue 1 — Cryo Manifold caption mistimed

**File:** `models/lng-site/option-e-cinematics.json` → `cinematics.process-flow.waypoints`

**Current (process-flow):**
| t   | pos              | lookAt                  | focal | caption                  |
|-----|------------------|-------------------------|-------|--------------------------|
| 14  | [-30, 10, 14]    | [-30, -2, 1.5]          | 28    | 24-ISO Storage Array     |
| 19  | [40, -20, 8]     | [-15.97, -2, 1.45]      | 35    | 24× 10K LNG ISO          |
| **23** | [-15, -28, 4] | [-15.97, -17.02, 1.0]   | 40    | **Cryogenic Manifold**   |
| 27  | [-30, -33, 7]    | [-43.6, -19.52, 1.8]    | 35    | HP Smart Queens (×2)     |

**Issue:** The blue cryo pipes at `cryoManifold` `[-15.97, -17.02, 1.0]` are visually revealed during the t=14–23 ISO sweep (lookAt heights at z=1.45 catches the manifold pipes below). Caption "Cryogenic Manifold" only kicks in at t=23s, by which point the pipes have been visible for several seconds with the caption still reading "24× 10K LNG ISO".

**Fix targets (verify visually before committing):**
- Shift cryo manifold caption to start at **t=21** (last 2s of the ISO array shot now overlaps with the manifold reveal); OR
- Move cryo waypoint earlier and add a separate ISO array push-in at t=14, e.g.:
  - t=14: ISO array wide
  - t=19: ISO array close (caption "24× 10K LNG ISO")
  - **t=22: cryo manifold reveal (NEW, caption "Cryogenic Manifold")**
  - t=26: queens (was t=27)
  - reshape remaining 27→45s window accordingly

**To preview the fix without rendering full Eevee:** `models/lng-site/cinematics/preview/` was used during initial development at 0.25x resolution scale. Run:
```bash
cd ~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2
blender --background --python scripts/generate_lng_cinematics.py -- \
  --cinematic process-flow --resolution-scale 0.25 \
  --output-dir models/lng-site/cinematics/preview
```

---

## Issue 2 — Glycol Bath Vaporizer + Stack

**Same file/section.** Walker grouped this with the cryo manifold complaint. Inspect the current waypoint at t=31 vs the visual reveal:

| t   | pos             | lookAt              | focal | caption                       |
|-----|-----------------|---------------------|-------|-------------------------------|
| 27  | [-30, -33, 7]   | [-43.6, -19.52, 1.8] | 35   | HP Smart Queens (×2)          |
| **31** | [25, -22, 15]| [44.85, -6.0, 3.5]  | 32    | **Glycol-Bath Vaporizer + Stack** |
| 35  | [15, -25, 8]    | [31.85, -15, 1.4]   | 50    | BOG Capture — Option E Differentiator |

Hypothesis: at t=27–31 the camera is still on the queens (cryoManifold→queens lookAt is at [-43.6, ...]), but as it sweeps east the vaporizer becomes visible before t=31 hits. Validate by sampling frames at t=28, 29, 30 and checking when the vaporizer skid first dominates the frame. Likely fix is the same pattern as issue 1 — shift the vaporizer caption ~1.5–2s earlier.

---

## Issue 3 — BOG Capture too tight

**Three offending waypoints:**

**process-flow:**
| t  | pos          | lookAt           | focal | distance to lookAt |
|----|--------------|------------------|-------|--------------------|
| 35 | [15, -25, 8] | [31.85, -15, 1.4] | **50** | ~21 m              |
| 39 | [50, -28, 12]| [31.85, -15, 1.4] | **50** | ~24 m              |

**differentiator (Walker's main complaint — opens on BOG):**
| t  | pos          | lookAt           | focal | distance |
|----|--------------|------------------|-------|----------|
| **0**  | [20, -20, 5] | [31.85, -15, 1.4] | **70** | **~13 m** |
| **4**  | [40, -22, 5] | [31.85, -15, 1.4] | **70** | ~11 m    |

At focal 70mm with ~12m subject distance, the BOG skid fills the frame and the surrounding context disappears. This reads as "zoomed way too far in" exactly as Walker described.

**Fix targets:**
- **Differentiator opening:** drop focal to **35–45**, pull camera back to `pos: [55, -45, 12]` or similar (~30m distance). Keep the BOG skid recognizable but show enough surrounding context (ISO array tail in background, vaporizer to the right) so the viewer reads "this is the differentiator and here's where it sits."
- **process-flow t=35:** drop focal from 50 to ~40, pull pos to `[5, -32, 10]` (~30m). The 50mm + close distance was meant to "hero" the skid but it just feels claustrophobic.

---

## Issue 4 — Camera whipping / jerky transitions

**Root cause:** waypoint velocities vary from 2m/s to 19m/s across adjacent segments. The render uses linear interp + per-waypoint easing, but no global motion smoothing.

**process-flow velocity audit:**
| segment | Δpos | Δt | speed | notes |
|---------|------|----|-------|-------|
| 0→5     | 190 m | 5 s | 38 m/s | establishing sweep — OK, dramatic |
| 5→10    | 50 m  | 5 s | 10 m/s | OK |
| 10→14   | 45 m  | 4 s | 11 m/s | OK |
| 14→19   | **78 m**  | **5 s** | **16 m/s** | **JERKY — across the entire site** |
| 19→23   | 60 m  | 4 s | 15 m/s | jerky |
| 23→27   | 16 m  | 4 s | 4 m/s | slow |
| 27→31   | **60 m**  | **4 s** | **15 m/s** | **JERKY — abrupt acceleration after slow segment** |
| 31→35   | 12 m  | 4 s | 3 m/s | slow |
| 35→39   | 35 m  | 4 s | 9 m/s | OK |
| 39→42   | 35 m  | 3 s | 12 m/s | a bit fast |
| 42→45   | 8 m   | 3 s | 3 m/s | slow |

The pattern slow-fast-slow-fast (e.g. t=23→27 at 4 m/s then t=27→31 at 15 m/s) creates the "whipping" feel. Same problem in differentiator + scale-detail.

**Two fix options:**

### Option A — Quick fix (this PR, before Session 2 lighting work)
Stay in v1 pipeline. Two changes to the JSON:
1. **Add intermediate waypoints** so no segment exceeds ~8 m/s. E.g. between t=14 [-30, 10, 14] and t=19 [40, -20, 8], insert a t=16.5 waypoint at the midpoint to smooth the arc.
2. **Match adjacent segment speeds**: if segment N runs at 4 m/s, segment N+1 shouldn't jump to 15 m/s. Either slow the fast segment (extend t) or speed up the slow one.

**Time:** 1–2h to retime all 3 cinematics. **Render time:** ~30 min (Eevee, 1080p) + 7 min polish-pass batch.

**End-state quality:** noticeably smoother but still uses linear interp + ease per-waypoint. Walker said "much more seamless and gradual" — Option A gets ~70% of the way there.

### Option B — Real fix (Session 2 / Phase 3 of polish plan)
Implement Phase 3 of `2026-05-24-option-e-cinematics-polish-v2.md` (lines 236–262): bezier handles per waypoint, DOF focus pulls, optional handheld noise. This requires building `scripts/render_cinematics_polished.py` (the v2 renderer with bezier F-curve handle support).

**Time:** 1–2h to retime + add bezier handles + DOF targets, all per the existing spec. **Render time:** same as Option A.

**End-state quality:** professional smoothness. The bezier handles let segment N decelerate into segment N+1 instead of jumping speed.

**Recommendation:** **Option A first** to ship a better v1.5 sooner, then **Option B** as part of Session 2 when geometry/HDRI is being added. Option B alone won't fix issue 3 (BOG zoom) — that's a focal/distance choice independent of camera smoothness.

---

## Re-render workflow (after any JSON edit)

```bash
APOLLO=~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2
cd "$APOLLO"

# 1. Re-render v1 cinematics from edited JSON (Eevee, full res, ~15-30 min for all 3)
blender --background --python scripts/generate_lng_cinematics.py -- --cinematic all

# 2. Re-run polish pass on the new v1 → produce v1.5 (~7 min)
source .venv/bin/activate
python scripts/post_production.py batch \
  --input-dir models/lng-site/cinematics \
  --output-dir models/lng-site/cinematics/v1.5 \
  --captions models/lng-site/option-e-cinematics.json \
  --title "Apollo LNG · Option E" \
  --end-title "Apollo Energy Group · LNG Solutions" \
  --end-subtitle "walker@apollogroup.energy"

# 3. Preview iteration (faster — 0.25x res):
blender --background --python scripts/generate_lng_cinematics.py -- \
  --cinematic process-flow --resolution-scale 0.25 \
  --output-dir models/lng-site/cinematics/preview
```

---

## What polish-pass did right (don't change)

These were validated visually and are working:
- Title card design (navy gradient, teal radial glow, Satoshi typography, lower-left kicker)
- End card (Apollo Energy Group · LNG Solutions + email, teal glow rising from bottom)
- Per-clip subtitle auto-resolution from JSON `label` ("Process Flow", "Differentiator First", "Scale → Detail")
- Golden-hour color grade — subtle Navy shadow lift + warm midtones, doesn't fight the existing v1 captions
- Vignette + grain — present but unobtrusive
- File sizes are heavy (~155 MB each at CRF 18). If sharing with investors via email, bump `--crf 22` in `apply_filters()` for ~4× smaller files. Plan didn't constrain size; left at CRF 18 for archival quality.

---

## State for session 2 resume

- **Backups intact** at `.backup/` — originals of blend, JSON, both scripts, full cinematics dir
- **Polish toolchain stable** — `scripts/post_production.py` works, venv at `.venv/`
- **Fonts present** at `assets/fonts/Satoshi-{Variable.ttf,Bold.otf,Medium.otf,Regular.otf}`
- **Spec still accurate** through Phase 5.5; Phases 1–4, 6–10 unchanged
- **No git** (per Phase 0 plan note: "Apollo project: NOT a git repo → backup-first strategy required")

After issues 1–4 are fixed and re-rendered:
1. Show Walker the new v1.5
2. If approved → start Session 2 (Phase 1 geometry detail + Phase 2 HDRI lighting + Phase 3 bezier camera per polish spec)
3. If not approved → iterate on JSON

---

## Files written this session

- `scripts/post_production.py` (~530 lines, working)
- `.venv/` (Python 3.14 + Pillow 12.2.0)
- `assets/fonts/Satoshi-*` (4 files)
- `.backup/` (originals)
- `models/lng-site/cinematics/v1.5/option-e-{process-flow,differentiator,scale-detail}.mp4`
- `docs/superpowers/specs/2026-05-24-option-e-cinematics-polish-v2.md` (updated with Session 1 results)
- This file
- `~/.claude/projects/-Users-wwa/memory/project_option_e_polish.md` (memory pointer)
- `~/.claude/projects/-Users-wwa/memory/MEMORY.md` (added pointer entry)
