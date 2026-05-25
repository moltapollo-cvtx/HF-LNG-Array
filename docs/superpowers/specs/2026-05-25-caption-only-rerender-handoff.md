# Caption-Only Re-render Path — Handoff (2026-05-25)

**Goal:** Wire `post_production.py`'s existing `--rerender-captions` ffmpeg+Pillow path into the routine caption-tweak workflow so a caption text/timing edit goes from **~50 min Blender render** to **~30 sec ffmpeg overlay**.

**Status:** Plumbing exists. Glue is missing. Estimated build: 1–2 hours.

**Read these on resume:**
- This file (current scope + fix targets)
- Shot-list DSL spec: `docs/superpowers/specs/2026-05-25-shot-list-dsl-design.md`
- Shot-list DSL plan: `docs/superpowers/plans/2026-05-25-shot-list-dsl.md`
- YAML site config plan: `docs/superpowers/plans/2026-05-25-yaml-site-config.md`
- Polish v2 spec (for the rerender_captions origin story): `docs/superpowers/specs/2026-05-24-option-e-cinematics-polish-v2.md`

---

## Why this matters

Walker's most frequent cinematic edit is **caption text or caption timing**. Three of the four issues in the 2026-05-24 v1.5 review were caption-related (cryo manifold mistimed, vaporizer mistimed, BOG hero caption text). Today each fix requires a full Blender Eevee re-render of the affected cinematic (~15 min per cinematic, ~50 min for all three). The actual change is a text edit and a few seconds of ffmpeg overlay work.

This is the smallest of the three "ergonomics moves" from the original conversation and the one with the largest recurring win — **caption tweaks are roughly 90% of the routine cinematic edits**.

---

## What already exists (don't rebuild)

### `scripts/post_production.py`

The `rerender_captions()` function at **line 488** already does the work. It:

1. Extracts every frame of an existing MP4 into a temp directory (`ffmpeg -i in.mp4 frame_%05d.png`)
2. Walks the waypoint list from the cinematic JSON to compute the right caption text for each frame's timestamp
3. Renders a translucent caption overlay PNG via Pillow + the Satoshi font set (`assets/fonts/Satoshi-*`)
4. Composites overlay onto each frame
5. Re-encodes back to MP4 via `ffmpeg -framerate <fps> -i frame_%05d.png -c:v libx264 -crf 18 -pix_fmt yuv420p out.mp4`

Key helpers:
- `caption_for_time(waypoints, duration, t)` — line 406
- `caption_alpha(waypoints, duration, t)` — line 414 (handles fade-in/out at waypoint boundaries)
- `_render_caption_overlay(size, text, alpha, fonts)` — line 429

CLI flag entry point: `scripts/post_production.py {single|batch} --rerender-captions`. Already wired into the polish pipeline; just not commonly invoked in isolation.

### `scripts/compile_shots.py`

Already takes `cinematics/option-e.shots.yaml` → `models/lng-site/option-e-cinematics.json` in **~30 ms**. The compiled JSON is identical in structure to the renderer's expected input. Caption strings live in waypoint entries verbatim.

### Cached v1 MP4s

The "old" rendered MP4s (pre-caption-edit) live at:

```
models/lng-site/cinematics/option-e-{process-flow,differentiator,scale-detail}.mp4    # v1 raw (Eevee, no polish)
models/lng-site/cinematics/v1.6/option-e-*.mp4                                         # v1.6 polished (title + grade + grain)
```

The raw v1 MP4s are the ones to recaption from — captions are baked into them by `generate_lng_cinematics.py` during the Blender render. `--rerender-captions` strips the old captions implicitly (by overlaying the new captions on the frames; old ones get covered).

Actually re-read: the old captions are *baked into the pixels*. `--rerender-captions` overlays new captions on top — this means the OLD caption bleeds through if it doesn't fully sit under the new one. **This is the main gotcha.** See "Known constraints" below.

---

## What's missing

There is **no one-command "I changed captions, refresh the polished MP4s" path**. To do it manually today, Walker (or Claude) would:

1. Edit `cinematics/option-e.shots.yaml` (change a caption string or shift `dur:` on the shot above it)
2. `python scripts/compile_shots.py cinematics/option-e.shots.yaml` (regenerates JSON)
3. Realize the v1 MP4s have **old captions baked in**, so a simple overlay-the-new-captions path leaves the old text visible underneath
4. Either: re-render v1 with `--no-captions` first (still requires Blender, ~15 min/cinematic), or accept the bleed-through
5. Run `post_production.py batch --rerender-captions ...` to overlay new captions on the v1 MP4s
6. The polish pass (title cards + grade + grain) needs re-running on top of the new caption-baked MP4s

So the actual problem set:

| Problem | Today | After this work |
|---------|-------|-----------------|
| Old captions bleed through | Bleed | Stripped at source |
| Multiple manual steps | 3-5 commands | 1 command |
| No caption-only edit detection | Always full re-render | Auto-detect → caption path |
| Polish pass coupling | Manual re-run | Auto-chained |

---

## Fix targets

Three independent pieces; do in this order.

### Fix 1 — Re-render v1 without baked-in captions (one-time)

Modify `scripts/generate_lng_cinematics.py` so its existing `--no-captions` flag (already present, see `parse_args` ~line 48) is the **default for routine renders going forward**. Re-render Option E's three cinematics once with `--no-captions` and stash them at `models/lng-site/cinematics/no-captions/option-e-*.mp4`. These become the canonical pre-caption-overlay source.

```bash
cd ~/Apollo.Group/Tech/High-Flow\ LNG\ Array-2
blender --background --python scripts/generate_lng_cinematics.py -- \
  --cinematic all --no-captions \
  --output-dir models/lng-site/cinematics/no-captions
```

One-time cost: ~50 min Blender wall time. After that, caption edits never trigger Blender again.

### Fix 2 — Build `scripts/recaption.py`

Single-command wrapper that takes a shots.yaml, compiles to JSON, overlays captions on the no-captions source MP4s, and re-runs the polish pass. Skeleton:

```python
#!/usr/bin/env python3
"""Caption-only re-render workflow.

Usage:
  python scripts/recaption.py cinematics/option-e.shots.yaml
      → re-renders v1.6 polished MP4s with new captions from shots.yaml
      → ~30-60 sec wall time (no Blender)
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Recaption polished cinematics from shots.yaml without re-rendering Blender.")
    p.add_argument("shots", help="Path to *.shots.yaml")
    p.add_argument("--polish-output", default="models/lng-site/cinematics/v1.7",
                   help="Where to write recaption-polished MP4s. Default: v1.7 (next polish version).")
    p.add_argument("--source-dir", default="models/lng-site/cinematics/no-captions",
                   help="Where to find the no-captions source MP4s (one-time Eevee render output).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    shots = Path(args.shots)

    # Step 1: compile shots.yaml → cinematic JSON
    print(f"[recaption] compiling {shots}")
    subprocess.check_call([sys.executable, str(ROOT / "scripts/compile_shots.py"), str(shots)], cwd=ROOT)

    # Step 2: pick up the freshly compiled JSON
    site_id = shots.stem.replace(".shots", "")  # "option-e.shots" → "option-e"
    captions_json = ROOT / "models" / "lng-site" / f"{site_id}-cinematics.json"

    # Step 3: overlay new captions onto the no-captions MP4s, then re-polish
    src_dir = ROOT / args.source_dir
    out_dir = ROOT / args.polish_output
    out_dir.mkdir(parents=True, exist_ok=True)

    # post_production.py supports overlay + polish in a single batch run via --rerender-captions
    cmd = [
        sys.executable, str(ROOT / "scripts/post_production.py"), "batch",
        "--input-dir", str(src_dir),
        "--output-dir", str(out_dir),
        "--captions", str(captions_json),
        "--rerender-captions",     # << the key flag
        "--title", "Apollo LNG · Option E",
        "--end-title", "Apollo Energy Group · LNG Solutions",
        "--end-subtitle", "walker@apollogroup.energy",
    ]
    print(f"[recaption] overlay + polish → {out_dir}")
    subprocess.check_call(cmd, cwd=ROOT)
    print(f"[recaption] done: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Edge cases to handle:
- If `models/lng-site/cinematics/no-captions/option-X-*.mp4` doesn't exist, **error fast** with a message that says "run Fix 1 first" rather than silently re-rendering Blender.
- Verify the compiled JSON's `cinematics` keys match the MP4 names in `source-dir`. A mismatch (e.g. shots.yaml has a new cinematic) means full Blender re-render is needed — error with that diagnosis.

### Fix 3 — Make `compile_shots.py` smart about caption-only changes (optional, defer)

A nice-to-have for later: a `--detect-caption-only` flag on `compile_shots.py` that diffs the freshly compiled JSON against the existing one. If only `caption` fields differ (no `pos`, `lookAt`, `focal`, `ease`, `t` changes), automatically invoke `recaption.py`. If anything else changed, instruct the user to run the full Blender pipeline.

Skip this if Walker's iteration loop is comfortable enough with the explicit `recaption.py` invocation.

---

## Resulting workflow

After Fix 1 + Fix 2:

```bash
$EDITOR cinematics/option-e.shots.yaml     # change a caption string
python scripts/recaption.py cinematics/option-e.shots.yaml
# ~30-60 sec later: models/lng-site/cinematics/v1.7/option-e-*.mp4 ready for Walker
```

Compared to today: **~50 min → ~30 sec for caption-only edits.** ~100x faster routine iteration.

Camera/motion edits still require full Blender re-render — those flow through the existing `generate_lng_cinematics.py` path. Walker decides per-edit which lane to use, or Fix 3 auto-routes.

---

## Verification

Once Fix 1 + Fix 2 land, sanity check:

1. **Baseline timing:** `time python scripts/recaption.py cinematics/option-e.shots.yaml` should report under 2 min total (compile + recaption + polish for 3 cinematics × 45s each). Anything over 5 min means Blender is being invoked somewhere it shouldn't.
2. **Visual:** Open `models/lng-site/cinematics/v1.7/option-e-process-flow.mp4` at the timestamp of an edited caption. The new caption should appear cleanly with no old caption bleed-through.
3. **Roundtrip:** Edit a caption, run recaption, observe new caption. Change it back, recaption again, observe original caption restored. Idempotent.
4. **Negative test:** Modify a `pos:` in shots.yaml (i.e. a camera change, not caption-only). Run recaption. Expected behavior: recaption still produces output, but the camera motion is unchanged from the no-captions source (because Blender isn't called). The polished MP4 will show the OLD camera with NEW captions — possibly correct, possibly not, depending on whether the camera change was intentional. Document this trap: **recaption is caption-only by definition.**

---

## Known constraints

- **No-captions source MP4s are the canonical inputs.** Once they exist, never re-render them unless camera/motion changes. Stash them at `models/lng-site/cinematics/no-captions/` and treat as source-of-truth artifacts.
- **Polish pass is non-deterministic on grain.** The film-grain layer is generated with a seeded PRNG (per the polish-v2 spec). Same input → identical output. No surprises.
- **Title card + end card baked into v1.7 output**. If those need updating (e.g., new subtitle), pass `--title`/`--end-title` flags through `recaption.py`.
- **Apollo project has no git.** Backup `cinematics/option-e.shots.yaml` to `.backup/caption-only-rerender/<date>/` before any non-trivial caption restructuring. The shots YAML is now the source-of-truth — protect it.
- **DSL parity gate doesn't apply.** Recaption preserves the camera path that was baked into the no-captions MP4 (which was generated by the DSL-compiled JSON in the first place). So the recaption workflow is implicitly within whatever parity tolerance the original Blender render was at.

---

## Files this work creates/modifies

**Create:**
- `scripts/recaption.py` (the new CLI from Fix 2)
- `models/lng-site/cinematics/no-captions/option-e-{process-flow,differentiator,scale-detail}.mp4` (one-time Eevee output from Fix 1)
- `models/lng-site/cinematics/v1.7/option-e-*.mp4` (recaption output dir)

**Modify (minimal):**
- Possibly `scripts/post_production.py` only if a new flag is needed for the polish pass to read the no-captions sources — but the existing `--rerender-captions` should already cover this. Verify by reading the function body before adding flags.

**Untouched:**
- `scripts/generate_lng_cinematics.py` (camera/motion changes still flow here; default behavior unchanged)
- `scripts/compile_shots.py` (Fix 3 might extend, otherwise unchanged)
- `scripts/lib/shot_compiler.py`, `scripts/lib/site_config.py`, `scripts/lib/equipment_builders.py` (no changes)
- `cinematics/option-e.shots.yaml` and `sites/option-e.yaml` (Walker's artifacts, unchanged structurally)

---

## Acceptance criteria

1. `python scripts/recaption.py cinematics/option-e.shots.yaml` exits 0 in under 2 minutes wall time, with no Blender invocation.
2. Editing a caption text in `cinematics/option-e.shots.yaml` and re-running recaption produces a v1.7 MP4 with the new caption visible at the expected timestamp.
3. The no-captions source MP4s at `models/lng-site/cinematics/no-captions/` exist and are reused across recaption invocations (file mtime doesn't change).
4. No baked-in caption bleed-through in the v1.7 output (visual check at any edited caption timestamp).
5. The polish pass title card, end card, golden-hour grade, and film grain all appear correctly in v1.7 (no regression vs v1.6 styling).

---

## Followups (out of scope for this handoff)

- **Fix 3** above (caption-only auto-detection).
- Caption animation timing variations beyond simple fade-in/out (e.g. character-by-character reveal). The current `caption_alpha()` is fade-only; a richer animation surface is a separate spec.
- Per-clip caption font / color overrides via the shots.yaml. Today captions inherit a single style from `post_production.py`.
- Multi-language caption tracks (English + Spanish overlay). Not requested; defer.
