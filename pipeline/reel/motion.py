"""motion stage: animate every `source: "local"` shot into out/clips/cNN.mp4 (1920x1080, 30 fps, H.264 yuv420p).

Motion types
  drift  one still; 2.5D camera move. Each output pixel is mapped back into the still through a per-pixel zoom /
         offset that depends on the depth map (Depth Anything V2 Small), so near things move more than far things.
         The depth is max-filtered first so the stretch zone falls on the background side of silhouettes (faces and
         ink outlines stay rigid). The painted-paper border is held flat (it moves with the card, never warps).
  morph  base still -> pose stills in order. In-between images come from RIFE v4.6 (rife-ncnn-vulkan), generated
         once per transition at still resolution, then played on an eased timeline under the same camera move.
         Depth is blended between the two poses' depth maps.
  step   hold each pose, snap to the next on a beat (4 beats per bar assumed) with a warm flash and a small camera
         punch-in that settles in ~6 frames. Camera move continues underneath.

Optional `sky_title` (any type): a film title composited into the scene before the fx chain, warped by the same
camera maps as the still and hidden behind near shapes by a depth matte (skytitle.py).

Run inside the GPU lock (the CLI is invoked as `gpu_lock.sh python reel.py <ep> motion`); this module never takes
the lock itself.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from . import depth as depthmod
from . import fx as fxmod
from . import skytitle as skytitlemod
from .clipkit import (RIFE_BIN, RIFE_MODEL, FrameWriter, clip_out, clip_seconds, clip_spec, kf, load_episode, log,
                      shot_span, want)

PARALLAX_GAIN = 1.25    # how strongly depth modulates zoom / pan at parallax = 1
DOLLY = 0.012           # lateral dolly (fraction of still width) added at parallax = 1 so depth reads
PUNCH = 0.014           # step: zoom bump on each snap


# ------------------------------------------------------------------------------------------------ timing

def ease(name: str, x):
    x = np.clip(x, 0.0, 1.0)
    if name == "linear":
        return x
    if name == "out":
        return 1 - (1 - x) ** 3
    return 0.5 - 0.5 * np.cos(np.pi * x)  # in_out (gentle, no overshoot)


def read_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


# ------------------------------------------------------------------------------------------------ camera

class Camera:
    """Maps output pixels to still pixels for frame i, with depth-dependent parallax."""

    def __init__(self, motion: dict, sw: int, sh: int, W: int, H: int, n_frames: int, punches=()):
        cam = motion.get("camera", {}) or {}
        self.move = cam.get("move", "static")
        self.amount = float(min(0.08, max(0.0, cam.get("amount", 0.04 if self.move != "static" else 0.0))))
        self.ease = cam.get("ease", "in_out")
        self.P = float(np.clip(motion.get("parallax", 0.0), 0, 1))
        self.sw, self.sh, self.W, self.H, self.n = sw, sh, W, H, n_frames
        self.punches = list(punches)
        cover = max(W / sw, H / sh)
        # overscan so pans / parallax never sample outside the still (BORDER_REFLECT covers any remainder; the
        # still's edge is bare paper, so a reflected sliver is invisible anyway)
        pan = self.amount * 0.5 if self.move in ("pan_left", "pan_right", "tilt_up", "tilt_down") else 0.0
        extra = pan * sw / (sh if self.move.startswith("tilt") else sw) + self.P * 0.02
        self.k0 = cover * (1 + 2 * extra)
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        self.ux = (xs + 0.5 - W / 2)  # output coords relative to centre
        self.uy = (ys + 0.5 - H / 2)

    def params(self, i):
        t = i / max(1, self.n - 1)
        e = float(ease(self.ease, t))
        a, sw = self.amount, self.sw
        z, ox, oy = 1.0, 0.0, 0.0
        if self.move == "push_in":
            z = 1.0 / (1.0 - a * e)
        elif self.move == "pull_out":
            z = 1.0 / (1.0 - a * (1 - e))
        elif self.move == "pan_left":
            ox = -a * sw * (e - 0.5)
        elif self.move == "pan_right":
            ox = a * sw * (e - 0.5)
        elif self.move == "tilt_up":
            oy = -a * sw * (e - 0.5)
        elif self.move == "tilt_down":
            oy = a * sw * (e - 0.5)
        for p in self.punches:  # step: quick ease-out zoom bump on each snap
            if i >= p:
                z *= 1.0 + PUNCH * math.exp(-(i - p) / 3.0)
        # lateral dolly that reveals depth; for a static camera it is a slow half-sway
        if self.move in ("static",):
            dolly = math.sin(math.pi * (t - 0.5)) * 0.5
        else:
            dolly = e - 0.5
        return z, ox, oy, dolly

    def maps(self, i, dmap):
        """Return (map_x, map_y, depth_used_at_output). dmap: still-res parallax depth (centred: 0 = focal plane)."""
        z, ox, oy, dolly = self.params(i)
        cx, cy = self.sw / 2, self.sh / 2
        k = self.k0
        dl = DOLLY * self.sw * dolly * self.P
        mx = cx + self.ux / (k * z) + ox
        my = cy + self.uy / (k * z) + oy
        if self.P <= 0 or dmap is None:
            return mx.astype(np.float32), my.astype(np.float32), None
        g = self.P * PARALLAX_GAIN
        lz = math.log(z)
        for _ in range(2):  # fixed-point: depth looked up where the pixel comes from
            d = cv2.remap(dmap, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            s = 1.0 + g * d
            ze = np.exp(lz * s)
            mx = cx + self.ux / (k * ze) + ox * s - dl * d
            my = cy + self.uy / (k * ze) + oy * s
        return mx.astype(np.float32), my.astype(np.float32), d

    def project(self, i, pts_norm, dval=0.0, dmap_d0=0.0):
        """Still coords (normalised 0..1) -> screen px, for a point at centred depth dval (flat approx)."""
        z, ox, oy, dolly = self.params(i)
        s = 1.0 + self.P * PARALLAX_GAIN * dval
        ze = math.exp(math.log(z) * s)
        dl = DOLLY * self.sw * dolly * self.P
        px = pts_norm[:, 0] * self.sw - self.sw / 2 - ox * s + dl * dval
        py = pts_norm[:, 1] * self.sh - self.sh / 2 - oy * s
        return np.stack([px * self.k0 * ze + self.W / 2, py * self.k0 * ze + self.H / 2], 1)


def parallax_depth(d: np.ndarray, mask: np.ndarray):
    """Centre depth on the focal plane, hold the paper border flat, push silhouettes' stretch onto the background."""
    h, w = d.shape
    r = max(3, int(w * 0.006))
    dd = cv2.dilate(d, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    dd = cv2.GaussianBlur(dd, (0, 0), r * 0.8)
    inside = mask > 0.5
    d0 = float(np.median(dd[inside])) if inside.any() else 0.5
    return ((dd - d0) * mask).astype(np.float32), d0


# ------------------------------------------------------------------------------------------------ RIFE

def rife_inbetweens(a_path: Path, b_path: Path, n: int, cache_dir: Path, force=False) -> list[Path]:
    """n images from a (first) to b (last) via RIFE v4.6, cached. Returns paths in order."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp = cache_dir / "src.txt"
    key = f"{a_path}:{a_path.stat().st_mtime}|{b_path}:{b_path.stat().st_mtime}|{n}\n"
    outs = [cache_dir / f"{k:04d}.png" for k in range(n)]
    if not force and stamp.exists() and stamp.read_text() == key and all(p.exists() for p in outs):
        return outs
    for p in cache_dir.glob("*.png"):
        p.unlink()
    shutil.copy(a_path, outs[0])
    shutil.copy(b_path, outs[-1])
    for k in range(1, n - 1):
        t = k / (n - 1)
        subprocess.run([str(RIFE_BIN), "-0", str(a_path), "-1", str(b_path), "-o", str(outs[k]),
                        "-m", str(RIFE_MODEL), "-s", f"{t:.5f}"], check=True, capture_output=True)
    stamp.write_text(key)
    return outs


# ------------------------------------------------------------------------------------------------ render

def _pose_paths(ep: Path, shot: dict) -> list[Path]:
    n = shot["n"]
    paths = [kf(ep, n)]
    for p in shot.get("poses", []) or []:
        paths.append(kf(ep, n, p["id"]))
    return paths


def render_shot(ep: Path, shot: dict, edit: dict, out: Path, W=None, H=None, fps=None, poses_override=None,
                fx_override=None, preview_frames=None, crf=16):
    """Render one shot. `preview_frames`: optional list of frame indices to return instead of writing a clip."""
    W0, H0, F0 = clip_spec()
    W, H, fps = W or W0, H or H0, fps or F0
    n = int(shot["n"])
    motion = shot.get("motion", {}) or {}
    mtype = motion.get("type", "drift")
    secs = clip_seconds(edit, n)
    span, beat = shot_span(edit, n)
    nf = int(math.ceil(secs * fps - 1e-6))
    paths = poses_override or _pose_paths(ep, shot)
    if mtype == "drift":
        paths = paths[:1]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"shot {n}: missing still(s) {', '.join(str(m) for m in missing)}")

    stills = [read_rgb(p) for p in paths]
    sh, sw = stills[0].shape[:2]
    stills = [s if s.shape[:2] == (sh, sw) else cv2.resize(s, (sw, sh), interpolation=cv2.INTER_AREA) for s in stills]
    depths = [depthmod.depth_for(p) for p in paths]
    depths = [d if d.shape == (sh, sw) else cv2.resize(d, (sw, sh)) for d in depths]
    mask = depthmod.paper_mask((stills[0] * 255).astype(np.uint8))
    pdepths = [parallax_depth(d, mask)[0] for d in depths]
    has_border = bool(mask.min() < 0.5)

    # timeline: which source image (or blend) each frame shows
    events, punches = [], []
    plan = []  # per frame: (kind, data)
    if mtype == "step" and len(stills) > 1:
        nbeats = max(1, int(round(span / beat)))
        k = len(stills)
        starts = [0] + [int(round(round(j * nbeats / k) * beat * fps)) for j in range(1, k)]
        events = punches = starts[1:]
        for i in range(nf):
            j = max(idx for idx, s in enumerate(starts) if i >= s)
            plan.append(("still", j))
    elif mtype == "morph" and len(stills) > 1:
        k = len(stills) - 1
        # hold ~15% of the visible span, morph, hold the pose; several poses share the middle 60%
        t_a, t_b = 0.15 * span, min(0.78 * span, 0.15 * span + 1.6 * k)
        seg = (t_b - t_a) / k
        inb = []
        for j in range(k):
            m = max(12, int(round(seg * fps * 0.75)))
            cache = ep / "out" / "cache" / f"morph_c{n:02d}_{j}"
            inb.append(rife_inbetweens(paths[j], paths[j + 1], m, cache))
        for i in range(nf):
            t = i / fps
            if t <= t_a:
                plan.append(("still", 0))
                continue
            j = min(k - 1, int((t - t_a) // seg))
            x = float(ease("in_out", (t - t_a - j * seg) / seg))
            if t >= t_b:
                plan.append(("still", k))
            else:
                plan.append(("morph", (j, x)))
    else:
        plan = [("still", 0)] * nf

    cam = Camera(motion, sw, sh, W, H, nf, punches=punches)
    ctx = fxmod.Ctx(W, H, fps, nf, seed=int(shot.get("seed", n)) * 1000 + n, still=stills[0], still_depth=depths[0],
                    events=events)
    d0 = parallax_depth(depths[0], mask)[1]
    ctx.project = lambda i, pts, dval=0.0: cam.project(i, pts, dval - d0)  # dval: raw depth 0..1
    chain = fxmod.build(fx_override if fx_override is not None else shot.get("fx", []), ctx)
    # optional film title in the sky, composited into the scene (moves with the sky, hidden behind near shapes)
    title = (skytitlemod.SkyTitle(shot["sky_title"], cam, fps, depths[0], pdepths[0])
             if shot.get("sky_title") else None)

    inb_cache = {}

    def source(i):
        kind, data = plan[i]
        if kind == "still":
            return stills[data], pdepths[data], depths[data]
        j, x = data
        imgs = inb[j]
        pos = x * (len(imgs) - 1)
        a = int(math.floor(pos))
        b = min(a + 1, len(imgs) - 1)
        f = pos - a
        for q in (a, b):
            if (j, q) not in inb_cache:
                inb_cache[(j, q)] = read_rgb(imgs[q])
                if len(inb_cache) > 6:
                    inb_cache.pop(next(iter(inb_cache)))
        img = inb_cache[(j, a)] * (1 - f) + inb_cache[(j, b)] * f
        pd = pdepths[j] * (1 - x) + pdepths[j + 1] * x
        rd = depths[j] * (1 - x) + depths[j + 1] * x
        return img, pd, rd

    def frame(i):
        img, pd, rd = source(i)
        mx, my, _ = cam.maps(i, pd if cam.P > 0 else None)
        rgb = cv2.remap(img, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        if title is not None:
            rgb = title.apply(np.clip(rgb, 0, 1), i, mx, my, rd)
        dw = cv2.remap(rd, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        mw = cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) if has_border else None
        return chain(np.clip(rgb, 0, 1), i, depth=dw, mask=mw)

    if preview_frames is not None:
        return [frame(i) for i in preview_frames]

    t0 = time.time()
    wr = FrameWriter(out, W, H, fps, crf=crf)
    try:
        for i in range(nf):
            wr.write((frame(i) * 255 + 0.5).astype(np.uint8))
        wr.close()
    except BaseException:
        wr.abort()
        raise
    dt = time.time() - t0
    log(f"c{n:02d}: {mtype}, {nf} frames ({secs:.2f}s) in {dt:.1f}s -> {out}")
    return dt


def run(ep_dir, only=None, force=False):
    ep, shots, edit = load_episode(ep_dir)
    done, failed = [], []
    for shot in shots.get("shots", []):
        n = int(shot["n"])
        if shot.get("source") != "local" or not want(n, only):
            continue
        out = clip_out(ep, n)
        if out.exists() and not force:
            log(f"c{n:02d}: exists, skipped")
            continue
        try:
            render_shot(ep, shot, edit, out)
            done.append(n)
        except FileNotFoundError as e:
            log(f"c{n:02d}: {e}")
            failed.append(n)
    if failed:
        raise SystemExit(f"motion: {len(failed)} shot(s) not rendered (missing stills): {failed}")
    return done
