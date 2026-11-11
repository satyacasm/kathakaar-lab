"""Anime "cut-in" mask reveals for music reels (edit.json shot key "mask").

  "mask": {"type": "zigzag", "angle": -12, "width": 0.34, "y": 0.5, "open": 4, "close": 3, "edge": "gold"}

A masked shot fills the whole reel frame with black; the shot's picture shows only inside one slanted band (or
two/three for "shards") that crosses the full width. The band snaps open from a hairline on the shot's first frame
(ease-out with a slight overshoot), holds while the picture drifts slowly, and, if the shot has "black_tail", snaps
shut just before the black. A thin bright line with a soft glow runs along the band edges; it is brightest while
the band opens. The opening frame is a hot white slash line.

Types
  zigzag  one band whose long edges are jagged, lightning-like polylines (both edges share one jagged spine, so the
          band opens out of a single lightning crack)
  slash   one clean slanted parallelogram
  shards  two or three parallel slanted bands of different widths split by thin black gaps, like manga panels;
          they open one frame apart and the picture sits slightly offset in each

Keys (all optional except "type")
  angle   tilt in degrees, -40..40; positive rises to the right                       (default 10)
  width   band thickness as a fraction of the screen height, 0.08..0.7 (shards: all bands together)   (0.34)
  y       band centre as a fraction of the screen height, 0.15..0.85                  (0.5)
  open    frames to snap open, 1..15                                                  (4)
  close   frames to snap shut before the black tail, 0..15 (0 = cut straight to black) (3)
  edge    "gold" | "white" | "none"                                                   ("gold")
  focus   [x, y] point of the picture (0-1) placed at the band centre                 ([0.5, 0.5])
  zoom    extra picture zoom inside the band, 1.0..2.0                                (1.0)
  drift   slow push-in over the shot, 0..0.15 (fraction of scale)                     (0.04)
  lines   faint diagonal speed lines in the black                                     (true)
  flash   white slash line on the opening frame                                       (true)
  seed    integer for the jagged edges / shard layout / speed lines                   (shot n)
  bands   shards only: 2 or 3                                                         (3)
"""
from __future__ import annotations

import math

import cv2
import numpy as np

MASK_TYPES = ("zigzag", "slash", "shards")
EDGE_COLOURS = {"gold": (242, 193, 78), "white": (255, 250, 240), "none": None}
MASK_KEYS = {"type", "angle", "width", "y", "open", "close", "edge", "focus", "zoom", "drift", "lines", "flash",
             "seed", "bands", "note"}
SS = 16                                         # cv2 fixed-point subpixel factor (shift=4)


def check(m, tag) -> list[str]:
    """Validation messages for one shot's mask dict."""
    out = []
    if not isinstance(m, dict):
        return [f"{tag}: 'mask' must be an object like {{\"type\": \"zigzag\"}}"]
    t = m.get("type")
    if t not in MASK_TYPES:
        return [f"{tag}: unknown mask.type {t!r} (known: {', '.join(MASK_TYPES)})"]
    for k in m:
        if k not in MASK_KEYS:
            out.append(f"{tag}: unknown mask key {k!r} (known: {', '.join(sorted(MASK_KEYS))})")

    def num(k, lo, hi, integer=False):
        if k not in m:
            return
        v = m[k]
        ok = isinstance(v, int) if integer else isinstance(v, (int, float))
        if isinstance(v, bool) or not ok or not lo <= v <= hi:
            out.append(f"{tag}: mask.{k} must be {'an integer' if integer else 'a number'} from {lo} to {hi}, "
                       f"got {v!r}")
    num("angle", -40, 40)
    num("width", 0.08, 0.7)
    num("y", 0.15, 0.85)
    num("open", 1, 15, True)
    num("close", 0, 15, True)
    num("zoom", 1.0, 2.0)
    num("drift", 0.0, 0.15)
    num("seed", 0, 2 ** 31, True)
    num("bands", 2, 3, True)
    if "bands" in m and t != "shards":
        out.append(f"{tag}: mask.bands only applies to type 'shards'")
    if m.get("edge", "gold") not in EDGE_COLOURS:
        out.append(f"{tag}: unknown mask.edge {m.get('edge')!r} (known: {', '.join(EDGE_COLOURS)})")
    for k in ("lines", "flash"):
        if k in m and not isinstance(m[k], bool):
            out.append(f"{tag}: mask.{k} must be true or false")
    if "focus" in m:
        f = m["focus"]
        if not (isinstance(f, list) and len(f) == 2 and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in f)):
            out.append(f"{tag}: mask.focus must be [x, y] with both between 0 and 1, got {f!r}")
    return out


# ---- easing ------------------------------------------------------------------------------------------------
def _ease_out_back(p, over=1.0):
    p = min(max(p, 0.0), 1.0)
    c1 = 1.70158 * over
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _ease_in(p):
    p = min(max(p, 0.0), 1.0)
    return p * p


# ---- geometry ----------------------------------------------------------------------------------------------
class Band:
    """One band: centre line through (W/2, yc) at `angle`, half thickness h (px, vertical), optional jagged edges."""

    def __init__(self, W, yc, angle, h, rng, jagged, xs_n=15):
        self.W, self.yc, self.h = W, yc, h
        self.slope = -math.tan(math.radians(angle))          # screen y grows downwards; +angle rises to the right
        pad = 60
        if jagged:
            # irregular stations and spike sizes (some short flat runs, some long forks): a lightning-like spine
            # shared by both edges, plus a little independent roughness per edge so they are not pure copies
            n = xs_n
            gaps = rng.uniform(0.35, 1.7, n - 1)
            xs = -pad + np.concatenate([[0], np.cumsum(gaps)]) / gaps.sum() * (W + 2 * pad)
            sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0) * rng.choice([-1.0, 1.0])
            amp = rng.choice([0.2, 0.55, 1.0, 1.6], n, p=[0.25, 0.35, 0.28, 0.12])
            spine = sign * amp * 0.13 * h
            self.xs = xs
            self.spine = spine
            self.top = sign * rng.uniform(0.0, 1.0, n) * 0.07 * h
            self.bot = -sign * rng.uniform(0.0, 1.0, n) * 0.07 * h
        else:
            self.xs = np.array([-pad, W + pad], float)
            self.spine = np.zeros(2)
            self.top = np.zeros(2)
            self.bot = np.zeros(2)

    def edges(self, k, dy=0.0):
        """(top, bottom) polylines as float arrays (n, 2) for opening factor k (0 = hairline, 1 = full)."""
        yc = self.yc + dy + self.slope * (self.xs - self.W / 2) + self.spine
        top = np.stack([self.xs, yc - self.h * k + self.top * k], 1)
        bot = np.stack([self.xs, yc + self.h * k + self.bot * k], 1)
        return top, bot

    def extent(self, k=1.12):
        top, bot = self.edges(k)
        return top[:, 1].min(), bot[:, 1].max()


def _poly(top, bot):
    return np.concatenate([top, bot[::-1]], 0)


def _fx(pts):
    return np.round(pts * SS).astype(np.int32).reshape(-1, 1, 2)


class MaskRenderer:
    """Renders the masked frames of one shot. Call frame(pic, i) for i = 0 .. nframes-1 in any order."""

    def __init__(self, m, canvas, nframes, fps, black_from, n_shot):
        self.m = m
        self.W, self.H = canvas
        self.N = nframes
        self.black_from = black_from                  # first frame index of the black tail (or nframes)
        self.typ = m["type"]
        self.open = int(m.get("open", 4))
        self.close = int(m.get("close", 3)) if black_from < nframes else 0
        self.edge = EDGE_COLOURS[m.get("edge", "gold")]
        self.focus = m.get("focus", [0.5, 0.5])
        self.zoom = float(m.get("zoom", 1.0))
        self.drift = float(m.get("drift", 0.04))
        self.lines = m.get("lines", True)
        self.flash = m.get("flash", True)
        seed = int(m.get("seed", n_shot * 7919 + 13))
        rng = np.random.default_rng(seed)
        angle = float(m.get("angle", 10))
        width = float(m.get("width", 0.34)) * self.H
        yc = float(m.get("y", 0.5)) * self.H
        self.angle = angle
        self.bands, self.delays, self.offsets = [], [], []
        if self.typ == "shards":
            nb = int(m.get("bands", 3))
            frac = np.array([0.5, 0.3, 0.2][:nb] if nb == 3 else [0.62, 0.38])
            order = rng.permutation(nb)                                      # wide band not always on top
            frac = frac[order]
            gap = 0.016 * self.H
            usable = width - gap * (nb - 1)
            hs = frac / frac.sum() * usable / 2
            y = yc - width / 2
            for j in range(nb):
                tilt = angle + rng.uniform(-2.5, 2.5)
                self.bands.append(Band(self.W, y + hs[j], tilt, hs[j], rng, jagged=False))
                y += 2 * hs[j] + gap
                self.delays.append(j)                                        # one frame apart
                self.offsets.append(rng.uniform(-1, 1) * 0.012 * self.W)
        else:
            self.bands.append(Band(self.W, yc, angle, width / 2, rng, jagged=self.typ == "zigzag"))
            self.delays.append(0)
            self.offsets.append(0.0)
        lo = min(b.extent()[0] for b in self.bands)
        hi = max(b.extent()[1] for b in self.bands)
        self.box = (max(0.0, lo), min(float(self.H), hi))                    # picture must cover this strip
        # speed lines: parallel to the band, in the black, sliding along it
        self.speed = []
        if self.lines:
            for _ in range(14):
                side = rng.choice([-1, 1])
                d = side * rng.uniform(0.6, 1.6) * (hi - lo) / 2 + rng.uniform(-40, 40)
                self.speed.append((yc + d, rng.uniform(0.25, 0.7) * self.W, rng.uniform(0, self.W * 2),
                                   rng.uniform(0.04, 0.10), rng.uniform(40, 90) * rng.choice([-1, 1])))
        self.slope = -math.tan(math.radians(angle))
        self._glow_small = (self.W // 4, self.H // 4)

    # timing: opening factor of band j at frame i
    def k(self, i, j=0):
        if i >= self.black_from:
            return None
        i2 = i - self.delays[j]
        if i2 < 0:
            return None
        if i2 == 0:
            kk = 0.012                                                     # opening frame: the hairline slash
        elif i2 < self.open:
            p = i2 / self.open                                             # fast ease-out with a slight overshoot
            kk = 1 - (1 - p) ** 2.4 + 0.10 * math.sin(math.pi * p) * p ** 1.5
        else:
            kk = 1.0
        if self.close:
            cs = self.black_from - self.close
            if i >= cs:                                                    # snaps shut to a hairline, then black
                kk = min(kk, max(0.012, 1 - _ease_in((i - cs + 1) / self.close) * 0.99))
        return kk

    def _picture(self, pic, i):
        """Cover-scale the picture onto the band strip (focus at the band centre), with settle + drift zoom."""
        ph, pw = pic.shape[:2]
        y0, y1 = self.box
        bw, bh = self.W, y1 - y0
        s = max(bw / pw, bh / ph) * self.zoom
        settle = 0.07 * (1 - min(1.0, i / max(1, self.open + 2))) ** 2       # lands slightly zoomed, settles
        s *= 1 + settle + self.drift * i / max(1, self.N)
        fx, fy = self.focus[0] * pw, self.focus[1] * ph
        cx, cy = self.W / 2, (y0 + y1) / 2
        tx, ty = cx - fx * s, cy - fy * s
        # keep the picture covering the strip
        tx = min(0.0, max(self.W - pw * s, tx))
        ty = min(y0, max(y1 - ph * s, ty))
        M = np.array([[s, 0, tx], [0, s, ty]], np.float32)
        return M

    def frame(self, pic, i):
        W, H = self.W, self.H
        out = np.zeros((H, W, 3), np.float32)
        ks = [self.k(i, j) for j in range(len(self.bands))]
        if all(k is None for k in ks):
            return out.astype(np.uint8)
        # speed lines (drawn first, masked out of the band later)
        if self.speed:
            lay = np.zeros((H, W), np.uint8)
            for (y, ln, x0, a, v) in self.speed:
                x = (x0 + v * i) % (W * 2) - W / 2
                p0 = np.array([x, y + self.slope * (x - W / 2)])
                p1 = np.array([x + ln, y + self.slope * (x + ln - W / 2)])
                cv2.line(lay, tuple(_fx(p0)[0, 0]), tuple(_fx(p1)[0, 0]), int(255 * a), 2, cv2.LINE_AA, 4)
            out += lay[..., None].astype(np.float32) * (np.array([0.85, 0.85, 0.9], np.float32))
        alpha = np.zeros((H, W), np.uint8)
        edge = np.zeros((H, W), np.uint8)
        glow_s = np.zeros(self._glow_small[::-1], np.uint8)
        q = 4
        M = self._picture(pic, i)
        layers = []
        for j, (b, kk) in enumerate(zip(self.bands, ks)):
            if kk is None:
                continue
            top, bot = b.edges(kk)
            a = np.zeros((H, W), np.uint8)
            cv2.fillPoly(a, [_fx(_poly(top, bot))], 255, cv2.LINE_AA, 4)
            layers.append((a, self.offsets[j]))
            for e in (top, bot):
                cv2.polylines(edge, [_fx(e)], False, 255, 3, cv2.LINE_AA, 4)
                cv2.polylines(glow_s, [_fx(e / q)], False, 255, 3, cv2.LINE_AA, 4)
        # picture (shards: same picture nudged per band)
        if len(layers) == 1 and layers[0][1] == 0:
            alpha = layers[0][0]
            pic_w = cv2.warpAffine(pic, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            af = alpha[..., None].astype(np.float32) / 255
            out = out * (1 - af) + pic_w.astype(np.float32) * af
        else:
            for a, off in layers:
                M2 = M.copy()
                M2[0, 2] += off
                pic_w = cv2.warpAffine(pic, M2, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                af = a[..., None].astype(np.float32) / 255
                out = out * (1 - af) + pic_w.astype(np.float32) * af
        # edge line + glow; brighter while opening/closing, a white-hot slash on the opening frame
        kmin = min(k for k in ks if k is not None)
        opening = i < self.open + max(self.delays) + 1
        closing = self.close and i >= self.black_from - self.close
        hot = (i == 0 and self.flash) or (closing and kmin < 0.05)
        if self.edge is not None or hot:
            col = np.array((255, 255, 250) if hot or self.edge is None else self.edge, np.float32)
            if hot:
                gi, core = 2.6, 1.0
            elif opening:
                gi, core = 1.6 - 1.0 * (i / (self.open + 1)), 1.0
            elif closing:
                gi, core = 1.2, 1.0
            else:
                gi, core = 0.55, 0.9
            if self.edge is None and not hot:
                gi = core = 0.0
            if gi > 0:
                g = cv2.GaussianBlur(glow_s, (0, 0), 3.2)
                g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
                e = edge.astype(np.float32) / 255
                lum = np.clip(e * core + g * gi * 0.9, 0, 1.4)[..., None]
                out = out + col * lum
                if hot:                                                   # white core on top of the colour
                    out = out + 255 * (e * 0.8)[..., None]
        return np.clip(out, 0, 255).astype(np.uint8)
