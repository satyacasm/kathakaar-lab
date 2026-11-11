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


# =============================================================================================================
# CapCut-style cut transitions, shakes and mask reveals (edit.json "transitions" types other than "hero", and the
# per-shot "mask"). Rules and examples: pipeline/REEL_PIPELINE.md, "Masks and transitions".
#
# Everything here is streamed segment by segment (decode -> numpy per frame -> encode); no segment is held in RAM.
# A cut transition at bar b spans the last `pre` frames of the outgoing shot A and the first `post` frames of the
# incoming shot B. Frames on A's side that need B use B's first frame; frames on B's side that need A use A's last
# frame. Frame counts never change.
# =============================================================================================================
import math as _math
from pathlib import Path

import cv2 as _cv2

_FFMPEG = "/opt/homebrew/bin/ffmpeg"
CUT_TYPES = ("whip", "slash", "glitch", "zoom", "flash")
EDIT_TYPES = CUT_TYPES + ("shake",)
# default (pre, post) seconds; at 30 fps: whip 3+4, slash 2+3, glitch 3+4, zoom 4+6, flash 0+2, shake 0+12 frames
EDIT_DEFAULTS = {"whip": (0.1, 0.134), "slash": (0.067, 0.1), "glitch": (0.1, 0.134), "zoom": (0.134, 0.2),
                 "flash": (0.0, 0.067), "shake": (0.0, 0.4)}
DIRS = ("left", "right", "up", "down")
FLASH_COLOURS = {"white": (255, 255, 255), "gold": (242, 193, 78), "red": (196, 22, 28)}
EDGE_COLOURS = {"gold": (242, 193, 78), "white": (255, 250, 240)}


def _u(i, P, Q):
    """Travel 0..1 across a cut for frame i (i < 0: outgoing side). 0.5 falls exactly on the cut, speed peaks there."""
    t = i + 0.5
    if t < 0:
        x = min(1.0, -t / (P + 0.5))
        return 0.5 * (1 - x) ** 2
    y = min(1.0, t / (Q + 0.5))
    return 1 - 0.5 * (1 - y) ** 2


def _whip(A, B, i, P, Q, tr):
    H, W = A.shape[:2]
    d = tr.get("dir", "left")
    s = tr.get("strength", 1.0)
    u = _u(i, P, Q)
    v = abs(_u(i + 0.5, P, Q) - _u(i - 0.5, P, Q))                 # travel per frame
    horiz = d in ("left", "right")
    L = W if horiz else H
    off = int(round(u * L))
    a, b = (A, B) if d in ("left", "up") else (A[:, ::-1] if horiz else A[::-1], B[:, ::-1] if horiz else B[::-1])
    out = np.empty_like(A)
    if horiz:
        out[:, :W - off] = a[:, off:]
        out[:, W - off:] = b[:, :off]
    else:
        out[:H - off] = a[off:]
        out[H - off:] = b[:off]
    if d == "right":
        out = out[:, ::-1]
    elif d == "down":
        out = out[::-1]
    k = int(min(L * 0.35, v * L * 0.75 * s)) | 1                    # shutter ~ 3/4 of a frame
    if k > 2:
        out = _cv2.blur(out, (k, 1) if horiz else (1, k))
    return np.ascontiguousarray(out)


_DCACHE = {}


def _dist(W, H, ang):
    key = (W, H, ang)
    if key not in _DCACHE:
        a = _math.radians(ang)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = (xx - W / 2) * _math.cos(a) - (yy - H / 2) * _math.sin(a)
        _DCACHE.clear()
        _DCACHE[key] = (d, W / 2 * abs(_math.cos(a)) + H / 2 * abs(_math.sin(a)))
    return _DCACHE[key]


def _slash(A, B, i, P, Q, tr):
    """Slanted wipe: B is revealed behind a bright edge line that crosses the centre exactly on the cut."""
    H, W = A.shape[:2]
    s = tr.get("strength", 1.0)
    ang = tr.get("angle", 22)                                   # lean of the wipe line from vertical, degrees
    d, R = _dist(W, H, ang)
    if tr.get("dir", "right") == "left":
        d = -d
    sc = W / 1920
    u = _u(i, P, Q)
    pos = -R - 30 * sc + u * (2 * R + 60 * sc)
    aa = 1.5 * sc
    m = np.clip((pos - d) / aa + 0.5, 0, 1)[..., None]           # 1 = B side
    out = A.astype(np.float32) * (1 - m) + B.astype(np.float32) * m
    col = np.array(EDGE_COLOURS[tr.get("edge", "gold")], np.float32)
    dd = np.abs(d - pos)
    core = np.clip(1 - (dd - 2.5 * sc) / (1.5 * sc), 0, 1)
    glow = np.exp(-(dd / (26 * sc)) ** 2) * 0.75 + np.exp(-(dd / (90 * sc)) ** 2) * 0.22
    lum = (core + glow * s)[..., None]
    out = out + col * lum + 255 * (core * 0.6)[..., None]
    return out.clip(0, 255).astype(np.uint8)


def _glitch(A, B, i, P, Q, tr, seed):
    H, W = A.shape[:2]
    s = tr.get("strength", 1.0)
    sc = W / 1920
    e = ((i + P + 1) / (P + 1)) ** 2 if i < 0 else (1 - i / max(1, Q)) ** 1.5
    own, other = (A, B) if i < 0 else (B, A)
    rng = np.random.default_rng(seed * 1000 + i + 500)
    out = own.copy()
    # displaced horizontal slices; on the two frames next to the cut a few slices come from the other shot
    for _ in range(int(3 + 5 * e)):
        h = int(rng.uniform(8, 110) * sc * (0.5 + e))
        y = int(rng.uniform(0, H - h))
        dx = int(rng.choice([-1, 1]) * rng.uniform(30, 170) * sc * e * s)
        src = other if (i in (-1, 0) and rng.random() < 0.4) else own
        out[y:y + h] = np.roll(src[y:y + h], dx, axis=1)
    px = int(round(16 * sc * e * s))
    if px > 0:
        r = np.roll(out[..., 0], px, axis=1)
        b = np.roll(out[..., 2], -px, axis=1)
        out = np.stack([r, out[..., 1], b], -1)
    if i in (-1, 0):                                              # a thin bright scan bar on the hit
        y = int(rng.uniform(0.2, 0.8) * H)
        out[y:y + max(2, int(3 * sc))] = np.maximum(out[y:y + max(2, int(3 * sc))], 230)
    return out


def _zoom_about(fr, z, cx, cy, dx=0.0, dy=0.0, border=_cv2.BORDER_REFLECT):
    H, W = fr.shape[:2]
    M = np.array([[z, 0, (1 - z) * cx + dx], [0, z, (1 - z) * cy + dy]], np.float32)
    return _cv2.warpAffine(fr, M, (W, H), flags=_cv2.INTER_LINEAR, borderMode=border)


def _radial(fr, z, r, cx, cy, K=7):
    if r < 0.004:
        return _zoom_about(fr, z, cx, cy)
    acc = np.zeros(fr.shape, np.float32)
    for j in range(K):
        acc += _zoom_about(fr, z * (1 + r * j / (K - 1)), cx, cy)
    return (acc / K).astype(np.uint8)


def _zoom_cut(A, B, i, P, Q, tr):
    H, W = A.shape[:2]
    s = tr.get("strength", 1.0)
    cx, cy = W * tr.get("cx", 0.5), H * tr.get("cy", 0.5)
    if i < 0:
        e = ((i + P + 1) / P) ** 2.2                       # accelerating push into A
        fr = _radial(A, 1 + 0.38 * s * e, 0.12 * s * e, cx, cy)
    else:
        e = (1 - i / Q) ** 2.4                             # B lands zoomed in and settles out
        fr = _radial(B, 1 + 0.30 * s * e, 0.10 * s * e, cx, cy)
    return _lift(fr, 0.16 * s * e)


def _flash(A, B, i, P, Q, tr):
    s = tr.get("strength", 1.0)
    c = tr.get("color", "white")
    col = np.array(FLASH_COLOURS[c] if isinstance(c, str) else c, np.float32)
    if i < 0:
        own, a = A, 0.3 * s * (i + P + 1) / (P + 1)
    else:
        own, a = B, min(1.0, 0.88 * s * 0.42 ** i)
    if a <= 0.001:
        return own
    x = own.astype(np.float32)
    if c != "white":                                       # coloured flash keeps a trace of the picture's light
        x = x * (1 - a) + col * a + x * a * 0.25
    else:
        x = x * (1 - a) + col * a
    return x.clip(0, 255).astype(np.uint8)


def _shake(fr, i, Q, tr, seed, state):
    H, W = fr.shape[:2]
    s = tr.get("strength", 1.0)
    sc = W / 1920
    rng = np.random.default_rng(seed * 1000 + i)
    decay = (1 - i / Q) ** 2
    amp = 24 * sc * s * decay
    dx, dy = rng.uniform(-amp, amp), rng.uniform(-amp * 0.7, amp * 0.7)
    punch = 0.05 * s * (1 - ease_out(min(1.0, i / max(1.0, Q * 0.45))))
    z = 1 + punch + 2.2 * amp / min(W, H) + 0.002
    out = _zoom_about(fr, z, W / 2, H / 2, dx, dy)
    px, py = state.get("prev", (0.0, 0.0))
    state["prev"] = (dx, dy)
    mv = abs(dx - px)
    if i < 3 and mv > 6 * sc:                              # a touch of motion blur on the first jolts
        k = int(mv * 0.5) | 1
        out = _cv2.blur(out, (k, 1))
    return out


# ---- planning --------------------------------------------------------------------------------------------
def _shot_frames(E, fps):
    bars = E["bars"]
    f0 = [round(bars[s["from_bar"]] * fps) for s in E["shots"]]
    n = [round(bars[s["to_bar"]] * fps) - a for s, a in zip(E["shots"], f0)]
    return f0, n


def plan_edits(E, fps):
    """List of (effect dict, notes). Effects: {"type", "tr", "k_out", "k_in", "g", "P", "Q", "seed"} with g = global
    frame index of the cut (or the shake start). Returns (effects, messages about ignored/trimmed parts)."""
    shots = E["shots"]
    f0, nf = _shot_frames(E, fps)
    effects, msgs = [], []
    for idx, tr in enumerate(E.get("transitions", [])):
        typ = tr.get("type")
        if typ not in EDIT_TYPES:
            continue
        pre_d, post_d = EDIT_DEFAULTS[typ]
        P, Q = round(tr.get("pre", pre_d) * fps), round(tr.get("post", post_d) * fps)
        seed = int(tr.get("seed", 101 + idx * 37))
        if typ == "shake":
            t = tr["t"] if "t" in tr else E["bars"][tr["bar"]]
            g = round(t * fps) - P
            effects.append(dict(type=typ, tr=tr, g=g, P=0, Q=P + Q, seed=seed))
            continue
        b = tr["bar"]
        k_out = next(k for k, s in enumerate(shots) if s["to_bar"] == b)
        k_in = next(k for k, s in enumerate(shots) if s["from_bar"] == b)
        if shots[k_in].get("mask") or (shots[k_out].get("mask") and typ != "flash"):
            msgs.append(f"{typ} at bar {b}: ignored (a masked shot has its own open/close animation)")
            continue
        if shots[k_out].get("mask") or float(shots[k_out].get("black_tail", 0) or 0) > 0:
            if P:
                msgs.append(f"{typ} at bar {b}: outgoing shot ends in black, only the incoming half plays")
            P = 0
        P, Q = min(P, nf[k_out]), min(Q, nf[k_in])
        if typ != "flash":
            Q = max(Q, 1)
        effects.append(dict(type=typ, tr=tr, g=f0[k_in], P=P, Q=Q, seed=seed, k_out=k_out, k_in=k_in))
    return effects, msgs


def _raw_frame(path, size, index):
    w, h = size
    vf = ["-vf", f"select=eq(n\\,{index})"] if index else []
    raw = subprocess.run([_FFMPEG, "-v", "error", "-i", str(path), *vf, "-vsync", "0", "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    if len(raw) < w * h * 3:
        raise RuntimeError(f"could not read frame {index} of {path}")
    return np.frombuffer(raw[:w * h * 3], np.uint8).reshape(h, w, 3).copy()


def _apply_frame(fr, g, k, effects, ends, state):
    """Apply every effect that covers global frame g (in list order)."""
    for e in effects:
        if e["type"] == "shake":
            i = g - e["g"]
            if 0 <= i < e["Q"]:
                fr = _shake(fr, i, e["Q"], e["tr"], e["seed"], state.setdefault(id(e), {}))
            continue
        i = g - e["g"]
        if not (-e["P"] <= i < e["Q"]):
            continue
        if i < 0 and k != e["k_out"] or i >= 0 and k != e["k_in"]:
            continue
        A = fr if i < 0 else ends[("last", e["k_out"])]
        B = fr if i >= 0 else ends[("first", e["k_in"])]
        t = e["type"]
        if t == "whip":
            fr = _whip(A, B, i, e["P"], e["Q"], e["tr"])
        elif t == "slash":
            fr = _slash(A, B, i, e["P"], e["Q"], e["tr"])
        elif t == "glitch":
            fr = _glitch(A, B, i, e["P"], e["Q"], e["tr"], e["seed"])
        elif t == "zoom":
            fr = _zoom_cut(A, B, i, e["P"], e["Q"], e["tr"])
        elif t == "flash":
            fr = _flash(A, B, i, e["P"], e["Q"], e["tr"])
    return fr


def _black_from(E, s, fps, n):
    bt = float(s.get("black_tail", 0) or 0)
    if bt <= 0:
        return n
    dur = E["bars"][s["to_bar"]] - E["bars"][s["from_bar"]]
    return min(n, int(_math.ceil((dur - bt) * fps - 1e-6)))


def apply_edits(E, segs, fps, size, canvas, bg=None):
    """Cut transitions, shakes and mask reveals, then (inset layout, `bg` given) put every shot on the reel canvas.

    segs[k] (picture size `size`) is replaced in place. With `bg` every output segment is `canvas` sized: plain shots
    get the picture scaled to 1080x608 at y=656 on the textured background (the same ffmpeg filter the final pass
    used to apply), masked shots are drawn full-screen by reel.masks. Without `bg` (full layout) size == canvas.
    """
    from reel import captions as _C
    from reel import masks as _M
    w, h = size
    CW, CH = canvas
    effects, msgs = plan_edits(E, fps)
    for m in msgs:
        print("note:", m)
    if not effects and bg is None and not any(s.get("mask") for s in E["shots"]):
        return
    f0, nf = _shot_frames(E, fps)
    ends = {}                                   # boundary frames, read before any segment is rewritten
    for e in effects:
        if e["type"] != "shake":
            for key, kk, idx in (("last", e["k_out"], nf[e["k_out"]] - 1), ("first", e["k_in"], 0)):
                if (key, kk) not in ends:
                    ends[(key, kk)] = _raw_frame(segs[kk], size, idx)
    inset_fc = (f"[0:v]scale={_C.INSET_PIC_W}:{_C.INSET_PIC_H}:flags=lanczos[fg];"
                f"[1:v][fg]overlay=0:{_C.INSET_PIC_Y},format=yuv420p[v]")
    enc = ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(fps)]
    for k, s in enumerate(E["shots"]):
        n = nf[k]
        g0 = f0[k]
        touched = [e for e in effects if (e["type"] == "shake" and e["g"] < g0 + n and e["g"] + e["Q"] > g0)
                   or (e["type"] != "shake" and ((e["k_out"] == k and e["P"]) or (e["k_in"] == k and e["Q"])))]
        mask = s.get("mask")
        seg = Path(segs[k])
        tmp = seg.with_name(seg.stem + "_e.mp4")
        if not touched and not mask:
            if bg is None:
                continue
            _run_ok([_FFMPEG, "-v", "error", "-y", "-i", str(seg), "-loop", "1", "-framerate", str(fps), "-i", str(bg),
                     "-filter_complex", inset_fc, "-map", "[v]", "-frames:v", str(n), *enc, str(tmp)])
            tmp.replace(seg)
            continue
        if mask:
            rend = _M.MaskRenderer(mask, (CW, CH), n, fps, _black_from(E, s, fps, n), s["n"])
            out_cmd = [_FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{CW}x{CH}",
                       "-r", str(fps), "-i", "-", "-frames:v", str(n), *enc, str(tmp)]
        elif bg is not None:
            out_cmd = [_FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                       "-r", str(fps), "-i", "-", "-loop", "1", "-framerate", str(fps), "-i", str(bg),
                       "-filter_complex", inset_fc, "-map", "[v]", "-frames:v", str(n), *enc, str(tmp)]
        else:
            out_cmd = [_FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                       "-r", str(fps), "-i", "-", "-frames:v", str(n), *enc, str(tmp)]
        rd = subprocess.Popen([_FFMPEG, "-v", "error", "-i", str(seg), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE)
        wr = subprocess.Popen(out_cmd, stdin=subprocess.PIPE)
        state, got = {}, 0
        for i in range(n):
            buf = rd.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            fr = _apply_frame(fr, g0 + i, k, touched, ends, state)
            if mask:
                fr = rend.frame(fr, i)
            wr.stdin.write(np.ascontiguousarray(fr).tobytes())
            got += 1
        rd.stdout.close()
        rd.wait()
        wr.stdin.close()
        if wr.wait() != 0 or got != n:
            raise RuntimeError(f"edit pass failed on shot {s['n']} ({got} of {n} frames)")
        tmp.replace(seg)
        what = [e["type"] for e in touched] + ([f"mask:{mask['type']}"] if mask else [])
        print(f"edits on shot {s['n']:2d}: {', '.join(what)} ({n} frames, unchanged)")


def _run_ok(cmd):
    subprocess.run(cmd, check=True)
