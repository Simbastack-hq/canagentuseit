#!/usr/bin/env python3
"""Render a run into an editing kit: <run>/media/ (generated only for approved runs).

  render.py <run-dir> [--only wide|tall]

  terminal-16x9.mp4   3840x2160 30 fps H.264 High 4:2:0, CRF 16: a clean, reconstructed replay of the
                      agent's terminal (no captions, no cards; waits over 5 s squeezed, marked in the footer)
  terminal-9x16.mp4   2160x3840, same, portrait layout
  cards-16x9/ cards-9x16/   card-title.png, card-attempt-N.png, card-verdict.png
  docs-broll.mp4      the docs-walk replay, labelled B-roll on screen, H.264
  captions.srt        the agent's own words, in video time (source text for the edit, not finished subtitles)
  markers.csv         first command, first error, fix, success: video seconds, 30 fps timecode, wall clock
  timemap.csv         video seconds -> wall clock, so anything can be re-synced to real time
  timeline.json       the keyframes the videos were made from

Needs: node or bun with Playwright ($CAUI_PLAYWRIGHT = path to the playwright module), and an ffmpeg
with libx264 ($CAUI_FFMPEG, else `ffmpeg`, else imageio-ffmpeg via uv).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def ffmpeg():
    for c in (os.environ.get("CAUI_FFMPEG"), shutil.which("ffmpeg")):
        if c and "libx264" in subprocess.run([c, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout:
            return c
    r = subprocess.run(["uv", "run", "-q", "--with", "imageio-ffmpeg", "python", "-c",
                        "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    sys.exit("no ffmpeg with libx264 (set CAUI_FFMPEG)")


def js_runtime():
    return shutil.which("node") or shutil.which("bun") or sys.exit("need node or bun")


def main(run, only=None):
    run = Path(run).resolve()
    # Video is published material: build it from the redacted copy, never the raw run.
    src = run / "public" if (run / "public" / "result.json").exists() else run
    media = run / "media"
    media.mkdir(exist_ok=True)
    subprocess.run([sys.executable, HERE / "timeline.py", src, media], check=True)
    ff, js = ffmpeg(), js_runtime()
    for aspect, name in (("wide", "16x9"), ("tall", "9x16")):
        if only and only != aspect:
            continue
        with tempfile.TemporaryDirectory(prefix="caui-frames-") as tmp:
            cards = media / f"cards-{name}"
            cards.mkdir(exist_ok=True)
            subprocess.run([js, HERE / "shoot.js", media / "timeline.json", cards, aspect, "cards"], check=True)
            subprocess.run([js, HERE / "shoot.js", media / "timeline.json", tmp, aspect, "clean"], check=True)
            subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", Path(tmp) / "concat.txt",
                            "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow",
                            "-crf", "16", "-movflags", "+faststart", media / f"terminal-{name}.mp4"], check=True)
    broll = next(iter(sorted(src.glob("video/*.webm"))), None)
    if broll and not only:
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", broll, "-vf", "fps=30,format=yuv420p", "-c:v", "libx264",
                        "-profile:v", "high", "-crf", "16", "-an", "-movflags", "+faststart", media / "docs-broll.mp4"], check=True)
    for p in sorted(media.rglob("*")):
        if p.is_file():
            print(f"{p.relative_to(media)}\t{p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    main(a[0], a[2] if a[1:2] == ["--only"] else None)
