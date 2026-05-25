#!/usr/bin/env python3
"""Caption-only re-render workflow.

Pipes a shots.yaml through compile_shots.py and the post_production.py batch
runner with --rerender-captions, overlaying the freshly compiled captions onto
the cached no-captions source MP4s and re-running the polish pass. No Blender.

Usage
-----
    python scripts/recaption.py cinematics/option-e.shots.yaml

    # Custom polish output dir
    python scripts/recaption.py cinematics/option-e.shots.yaml \\
        --polish-output models/lng-site/cinematics/v1.8

    # Custom no-captions source dir (default: models/lng-site/cinematics/no-captions)
    python scripts/recaption.py cinematics/option-e.shots.yaml \\
        --source-dir models/lng-site/cinematics/no-captions

Workflow assumption: the no-captions source MP4s already exist. Generate them
once with:

    blender --background --python scripts/generate_lng_cinematics.py -- \\
        --cinematic all --no-captions \\
        --output-dir models/lng-site/cinematics/no-captions

Camera/motion edits still require the full Blender pipeline -- this script
only refreshes captions, grade, title cards, and grain.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
sys.path.insert(0, str(ROOT / "scripts"))


def _python() -> str:
    """Prefer the project venv interpreter (it has yaml + Pillow); fall back to sys.executable."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Recaption polished cinematics from shots.yaml without re-rendering Blender.",
    )
    p.add_argument("shots", help="Path to *.shots.yaml")
    p.add_argument(
        "--polish-output",
        default="models/lng-site/cinematics/v1.7",
        help="Where to write recaption-polished MP4s. Default: v1.7.",
    )
    p.add_argument(
        "--source-dir",
        default="models/lng-site/cinematics/no-captions",
        help="Where the no-captions source MP4s live (one-time Blender output).",
    )
    p.add_argument(
        "--prefix",
        default="option-e-",
        help="MP4 filename prefix passed to post_production.py batch.",
    )
    p.add_argument("--title", default=None,
                   help="Title-card text. Defaults to the cinematic_title from sites/<site>.yaml.")
    p.add_argument("--end-title", default="Apollo Energy Group · LNG Solutions")
    p.add_argument("--end-subtitle", default="walker@apollogroup.energy")
    p.add_argument("--kicker", default=None,
                   help="Kicker text. Defaults to the cinematic_kicker from sites/<site>.yaml.")
    p.add_argument(
        "--skip-compile",
        action="store_true",
        help="Skip compile_shots.py (use the JSON already on disk).",
    )
    return p.parse_args(argv)


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p).resolve()


def _check_sources(src_dir: Path, captions_json: Path, prefix: str) -> None:
    """Fail loud if the no-captions sources are missing or out of sync with the JSON."""
    if not src_dir.is_dir():
        raise SystemExit(
            f"[recaption] no-captions source dir missing: {src_dir}\n"
            f"  Run Fix 1 first (one-time Blender render):\n"
            f"    blender --background --python scripts/generate_lng_cinematics.py -- \\\n"
            f"      --cinematic all --no-captions --output-dir {src_dir.relative_to(ROOT)}"
        )
    mp4s = sorted(p for p in src_dir.glob(f"{prefix}*.mp4") if p.is_file())
    if not mp4s:
        raise SystemExit(
            f"[recaption] no MP4s match {prefix}*.mp4 in {src_dir}.\n"
            f"  Either run the no-captions Blender render or change --prefix."
        )
    data = json.loads(captions_json.read_text())
    cin_names = set((data.get("cinematics") or {}).keys())
    missing = []
    for mp4 in mp4s:
        name = mp4.stem[len(prefix):] if mp4.stem.startswith(prefix) else mp4.stem
        if name not in cin_names:
            missing.append((mp4.name, name))
    if missing:
        details = "\n".join(f"    {fn} (key '{key}' not in {sorted(cin_names)})" for fn, key in missing)
        raise SystemExit(
            f"[recaption] source MP4s have no matching cinematic entry in {captions_json.name}:\n{details}\n"
            f"  Likely cause: shots.yaml added/renamed a cinematic. Full Blender re-render needed."
        )


def main(argv=None) -> int:
    args = parse_args(argv)
    shots = _resolve(args.shots)
    if not shots.is_file():
        raise SystemExit(f"[recaption] shots file not found: {shots}")

    if not args.skip_compile:
        print(f"[recaption] compile {shots.relative_to(ROOT)}")
        subprocess.check_call(
            [_python(), str(ROOT / "scripts/compile_shots.py"), str(shots)],
            cwd=ROOT,
        )

    site_id = shots.stem.removesuffix(".shots")  # "option-e.shots" -> "option-e"
    captions_json = ROOT / "models" / "lng-site" / f"{site_id}-cinematics.json"
    if not captions_json.is_file():
        raise SystemExit(
            f"[recaption] compiled JSON not found: {captions_json}\n"
            f"  Re-run without --skip-compile."
        )

    # Site-aware defaults: pull title/kicker from sites/<site>.yaml when CLI didn't override.
    site_yaml = ROOT / "sites" / f"{site_id}.yaml"
    title = args.title
    kicker = args.kicker
    if site_yaml.is_file() and (title is None or kicker is None):
        try:
            from lib.site_config import load_site  # type: ignore
            site = load_site(site_yaml)
            if title is None:
                title = site.cinematic_title
            if kicker is None:
                kicker = site.cinematic_kicker
        except Exception as exc:
            print(f"[recaption] warn: failed to load {site_yaml.name} for title defaults: {exc}", file=sys.stderr)
    if title is None:
        title = "Apollo LNG"
    if kicker is None:
        kicker = "DRONE FLYTHROUGH"

    src_dir = _resolve(args.source_dir)
    out_dir = _resolve(args.polish_output)
    _check_sources(src_dir, captions_json, args.prefix)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        _python(), str(ROOT / "scripts/post_production.py"), "batch",
        "--input-dir", str(src_dir),
        "--output-dir", str(out_dir),
        "--captions", str(captions_json),
        "--prefix", args.prefix,
        "--rerender-captions",
        "--title", title,
        "--end-title", args.end_title,
        "--end-subtitle", args.end_subtitle,
        "--kicker", kicker,
    ]
    try:
        display = out_dir.relative_to(ROOT)
    except ValueError:
        display = out_dir
    print(f"[recaption] overlay + polish -> {display}")
    subprocess.check_call(cmd, cwd=ROOT)
    print(f"[recaption] done: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
