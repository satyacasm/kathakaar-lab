"""finish stage: hero raw clips (out/hero_raw/cNN.mp4, ~480p 24 fps) -> out/clips/cNN.mp4 (1920x1080, 30 fps, yuv420p).

1. decode the raw clip to frames (temp dir under out/cache/, deleted afterwards)
2. RIFE v4.6 (rife-ncnn-vulkan) re-times it to 30 fps; if the shot's bar span + 0.5 s handle is longer than the raw
   clip, the same pass stretches it to fit with interpolated frames (never duplicated frames)
3. Real-ESRGAN realesr-animevideov3 (realesrgan-ncnn-vulkan) upscales x3, then a Lanczos scale-to-cover + centre crop
   gives exactly 1920x1080
4. ffmpeg encodes H.264 yuv420p, no audio

The external tools need image files, so this stage writes temporary frame folders (the clip is short: ~100 frames).
Run inside the GPU lock; this module does not take it.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from .clipkit import (ESRGAN_BIN, ESRGAN_DIR, FFMPEG, RIFE_BIN, RIFE_MODEL, FrameWriter, clip_out, clip_seconds,
                      clip_spec, load_episode, log, probe, want)

ESRGAN_MODEL = "realesr-animevideov3"
ESRGAN_SCALE = 3
TEXTURE_MIX = 0.35  # share of plain Lanczos upscale mixed back in


def _cover(img, W, H, interp):
    """Scale to cover W x H, centre crop."""
    h, w = img.shape[:2]
    s = max(W / w, H / h)
    nw, nh = max(W, round(w * s)), max(H, round(h * s))
    r = cv2.resize(img, (nw, nh), interpolation=interp)
    x, y = (nw - W) // 2, (nh - H) // 2
    return r[y:y + H, x:x + W]


def _run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{Path(str(cmd[0])).name} failed ({r.returncode}): {r.stderr[-800:]}")
    return r


def finish_clip(raw: Path, out: Path, target_secs: float | None, work: Path, keep=False) -> dict:
    W, H, fps = clip_spec()
    info = probe(raw)
    raw_secs = info["frames"] / info["fps"] if info["frames"] else info["duration"]
    secs = max(raw_secs, target_secs or 0.0)
    n_out = int(math.ceil(secs * fps - 1e-6))
    t0 = time.time()
    if work.exists():
        shutil.rmtree(work)
    fin, fmid, fup = work / "in", work / "rife", work / "up"
    for d in (fin, fmid, fup):
        d.mkdir(parents=True)
    _run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", raw, "-vsync", "0", fin / "%06d.png"])
    n_in = len(list(fin.glob("*.png")))
    # rife-ncnn-vulkan directory mode: output frame i sits at input position i * n_in / n_out
    _run([RIFE_BIN, "-i", fin, "-o", fmid, "-m", RIFE_MODEL, "-n", n_out, "-f", "%08d.png"])
    n_mid = len(list(fmid.glob("*.png")))
    t1 = time.time()
    _run([ESRGAN_BIN, "-i", fmid, "-o", fup, "-n", ESRGAN_MODEL, "-s", ESRGAN_SCALE, "-m", ESRGAN_DIR / "models",
          "-f", "png"])
    t2 = time.time()
    # Real-ESRGAN's anime model sharpens lines but irons out the watercolour paper grain; mixing back a share of a
    # plain Lanczos upscale of the same frame keeps the texture (checked by eye on c02 of the demo episode)
    wr = FrameWriter(out, W, H, fps)
    try:
        for k in range(1, n_mid + 1):
            up = cv2.imread(str(fup / f"{k:08d}.png"), cv2.IMREAD_COLOR)
            lo = cv2.imread(str(fmid / f"{k:08d}.png"), cv2.IMREAD_COLOR)
            a = _cover(up, W, H, cv2.INTER_AREA).astype(np.float32)
            b = _cover(lo, W, H, cv2.INTER_LANCZOS4).astype(np.float32)
            f = np.clip(a * (1 - TEXTURE_MIX) + b * TEXTURE_MIX + 0.5, 0, 255).astype(np.uint8)
            wr.write(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        wr.close()
    except BaseException:
        wr.abort()
        raise
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    res = {"raw_frames": n_in, "raw_fps": info["fps"], "raw_secs": round(raw_secs, 3), "target_secs": target_secs,
           "out_frames": n_mid, "slowdown": round(secs / raw_secs, 3), "rife_s": round(t1 - t0, 1),
           "upscale_s": round(t2 - t1, 1), "total_s": round(time.time() - t0, 1)}
    log(f"{out.name}: {res}")
    return res


def run(ep_dir, only=None, force=False):
    ep, shots, edit = load_episode(ep_dir)
    done = []
    for raw in sorted((ep / "out" / "hero_raw").glob("c[0-9][0-9].mp4")):
        n = int(raw.stem[1:])
        if not want(n, only):
            continue
        out = clip_out(ep, n)
        if out.exists() and not force and out.stat().st_mtime >= raw.stat().st_mtime:
            log(f"{out.name}: exists, skipped")
            continue
        try:
            target = clip_seconds(edit, n)
        except KeyError:
            target = None
            log(f"c{n:02d}: not in edit.json; keeping raw length")
        finish_clip(raw, out, target, ep / "out" / "cache" / f"finish_c{n:02d}")
        done.append(n)
    return done
