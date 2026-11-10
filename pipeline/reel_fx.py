"""Hero transitions for Kathakaar music reels (the CapCut-style "hit" on a song's hook).

A hero hit spans one cut that lands on a downbeat:
  - wind-up  (end of the outgoing shot): push-in zoom, brightness lift, growing RGB split
  - impact   (start of the incoming shot): 1-2 frame white flash, zoom punch settling back
             (ease-out), decaying camera shake, RGB split snapping back to clean

Works on already-rendered shot segments (same size/fps/codec as the reel), re-encoding only the
affected segments with the same frame count, so the beat grid is untouched.

Use from an episode's edit.json:
  "transitions": [{"type": "hero", "bar": 16, "pre": 0.5, "post": 0.55, "strength": 1.0}]
and in make_reel.py:  reel_fx.apply_transitions(E, segs, fps, (W, H))
"""
import subprocess

import numpy as np
from PIL import Image, ImageFilter


def _read_frames(path, size):
    w, h = size
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).copy()


def _write_frames(frames, path, fps):
    h, w = frames.shape[1:3]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                          "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    p.stdin.write(frames.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"encode failed: {path}")


def _zoom(fr, z, dx=0.0, dy=0.0):
    if z <= 1.0001 and not dx and not dy:
        return fr
    h, w = fr.shape[:2]
    cw, ch = w / z, h / z
    cx, cy = w / 2 + dx, h / 2 + dy
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return np.asarray(Image.fromarray(fr).resize((w, h), Image.BILINEAR, box=box))


def _rgb_split(fr, px):
    px = int(round(px))
    if px <= 0:
        return fr
    out = fr.copy()
    out[:, px:, 0] = fr[:, :-px, 0]      # red right
    out[:, :-px, 2] = fr[:, px:, 2]      # blue left
    return out


def _lift(fr, amount, to=255.0):
    """blend toward white (to=255) by amount 0..1"""
    if amount <= 0:
        return fr
    return (fr.astype(np.float32) * (1 - amount) + to * amount).clip(0, 255).astype(np.uint8)


def ease_in(x):
    return x * x * x


def ease_out(x):
    return 1 - (1 - x) ** 3


def hero_windup(frames, n, s=1.0):
    """Last n frames of the outgoing shot."""
    out = frames.copy()
    start = len(frames) - n
    for i in range(n):
        p = ease_in((i + 1) / n)
        fr = _zoom(frames[start + i], 1 + 0.22 * s * p)
        fr = _rgb_split(fr, 9 * s * p)
        out[start + i] = _lift(fr, 0.35 * s * p)
    return out


def hero_impact(frames, n, s=1.0, seed=7):
    """First n frames of the incoming shot."""
    rng = np.random.default_rng(seed)
    out = frames.copy()
    for i in range(min(n, len(frames))):
        p = i / max(1, n - 1)                       # 0 at the cut, 1 at the end of the effect
        decay = (1 - ease_out(p))
        z = 1 + 0.18 * s * decay                    # punch: starts zoomed, settles to 1.0
        shake = 22 * s * decay ** 1.5
        dx, dy = rng.uniform(-shake, shake), rng.uniform(-shake * 0.6, shake * 0.6)
        fr = _zoom(frames[i], z, dx, dy)
        fr = _rgb_split(fr, 12 * s * decay)
        flash = 1.0 if i == 0 else (0.55 if i == 1 else max(0.0, 0.35 * (1 - (i - 1) / 5)))
        out[i] = _lift(fr, flash * s)
    return out


def _bloom(fr, amount):
    small = Image.fromarray(fr).resize((fr.shape[1] // 4, fr.shape[0] // 4), Image.BILINEAR)
    s = np.asarray(small).astype(np.float32)
    s = np.clip((s - 150) * 2.2, 0, 255)                         # keep only the highlights
    s = np.asarray(Image.fromarray(s.astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))
                   .resize((fr.shape[1], fr.shape[0]), Image.BILINEAR)).astype(np.float32)
    return fr.astype(np.float32) + s * amount


def hero_grade(fr, letterbox, rng, vignette):
    """'Main character' look: contrast, teal shadows / warm highlights, +saturation, bloom, vignette, grain,
    and 2.39:1 letterbox bars (letterbox = 0..1, how far the bars are in)."""
    x = _bloom(fr, 0.22) / 255.0
    lum = (0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2])[..., None]
    x = (x - 0.5) * 1.14 + 0.5                                   # contrast
    sh, hi = (1 - lum) ** 2, lum ** 2
    x = x + sh * np.array([-0.035, 0.012, 0.05]) + hi * np.array([0.06, 0.02, -0.055])   # split tone
    x = lum + (x - lum) * 1.12                                   # saturation
    x = x * vignette
    x = x * 255 + rng.normal(0, 4.0, x.shape[:2])[..., None]     # grain
    out = x.clip(0, 255).astype(np.uint8)
    bar = int(round(letterbox * (fr.shape[0] - fr.shape[1] / 2.39) / 2))
    if bar > 0:
        out[:bar] = 0
        out[-bar:] = 0
    return out


def apply_grade(E, segs, fps, size):
    """E['grade'] = {"type": "hero", "from_bar": 16, "letterbox_out_bar": 20}: grade every shot from from_bar on;
    letterbox bars slam in at from_bar (4 frames) and slide out over 0.6 s from letterbox_out_bar."""
    g = E.get("grade")
    if not g:
        return
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vignette = (1 - 0.30 * np.clip(r - 0.35, 0, None) ** 1.6)[..., None]
    rng = np.random.default_rng(3)
    bars = E["bars"]
    t_in, t_out = bars[g["from_bar"]], bars[g["letterbox_out_bar"]] if g.get("letterbox_out_bar") else None
    for k, s in enumerate(E["shots"]):
        if s["from_bar"] < g["from_bar"]:
            continue
        frames = _read_frames(segs[k], size)
        f0 = round(bars[s["from_bar"]] * fps)
        for i in range(len(frames)):
            t = (f0 + i) / fps
            lb = min(1.0, (t - t_in) * fps / 4)
            if t_out is not None and t >= t_out:
                lb *= 1 - ease_out(min(1.0, (t - t_out) / 0.6))
            frames[i] = hero_grade(frames[i], lb, rng, vignette)
        _write_frames(frames, segs[k], fps)
        print(f"graded shot {s['n']} ({len(frames)} frames)")


def apply_transitions(E, segs, fps, size):
    """Re-render the segments touched by E['transitions'] in place. segs[k] belongs to E['shots'][k]."""
    for tr in E.get("transitions", []):
        if tr.get("type") != "hero":
            continue
        b = tr["bar"]
        k_out = next(k for k, s in enumerate(E["shots"]) if s["to_bar"] == b)
        k_in = next(k for k, s in enumerate(E["shots"]) if s["from_bar"] == b)
        st = tr.get("strength", 1.0)
        fo = _read_frames(segs[k_out], size)
        _write_frames(hero_windup(fo, round(tr.get("pre", 0.5) * fps), st), segs[k_out], fps)
        fi = _read_frames(segs[k_in], size)
        _write_frames(hero_impact(fi, round(tr.get("post", 0.55) * fps), st), segs[k_in], fps)
        print(f"hero transition at bar {b}: shot {E['shots'][k_out]['n']} -> shot {E['shots'][k_in]['n']}"
              f" ({len(fo)} + {len(fi)} frames, unchanged)")
