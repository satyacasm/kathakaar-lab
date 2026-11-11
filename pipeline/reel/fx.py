"""Effects for local motion clips, as frame-in / frame-out functions.

Usage (motion.py does this):
    ctx = fx.Ctx(w, h, fps, n_frames, seed=shot_seed, still=rgb_float, ...)
    chain = fx.build(["embers", "glow"], ctx)        # grain + vignette are always appended
    out = chain(frame, i, depth=warped_depth)          # frame: float32 HxWx3 RGB in 0..1

Every effect is deterministic: its random state comes only from (ctx.seed, effect name), and particle positions
are closed-form functions of the frame index, so any frame renders the same on every run and in any order.

Names (contract): embers, sparks, smoke, mist, glow, rays, rain, stars, flash.  Always on: grain, vignette.
Design rule: effects take their colours from the painting (its highlights / paper tone) and respect the
per-frame depth map, so particles pass behind near objects and mist lies in the distance.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import cv2
import numpy as np

NAMES = ("embers", "sparks", "smoke", "mist", "glow", "rays", "rain", "stars", "flash")
ORDER = ("mist", "smoke", "rain", "rays", "glow", "stars", "embers", "sparks", "flash")


@dataclass
class Ctx:
    w: int
    h: int
    fps: int
    n_frames: int
    seed: int = 0
    still: np.ndarray | None = None          # source still, float RGB 0..1 (any size), for palette / star finding
    still_depth: np.ndarray | None = None    # depth of the still (1 = near)
    project: object = None                   # project(i, pts_xy_norm_in_still, depth) -> screen px (N,2)
    events: list = field(default_factory=list)  # frame indices for flash (pose snaps, cuts)
    strength: float = 1.0

    def rng(self, name: str) -> np.random.Generator:
        return np.random.default_rng([int(self.seed) & 0xFFFFFFFF, zlib.crc32(name.encode())])


# ----------------------------------------------------------------------------------------------- helpers

def _luma(img):
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


def _screen(base, add):
    return 1.0 - (1.0 - base) * (1.0 - np.clip(add, 0, 1))


def _smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _palette(ctx: Ctx):
    """(highlight colour, paper/light colour, shadow colour) taken from the still."""
    if ctx.still is None:
        return np.array([1, .8, .55], np.float32), np.array([.93, .9, .84], np.float32), np.array([.2, .17, .15], np.float32)
    s = cv2.resize(ctx.still, (160, 90), interpolation=cv2.INTER_AREA).reshape(-1, 3)
    l = _luma(s)
    hi = s[l >= np.percentile(l, 96)].mean(0)
    mid = s[(l > np.percentile(l, 70)) & (l < np.percentile(l, 90))].mean(0)
    lo = s[l <= np.percentile(l, 8)].mean(0)
    return hi.astype(np.float32), mid.astype(np.float32), lo.astype(np.float32)


def _sample(depth, xs, ys):
    if depth is None:
        return np.zeros(len(xs), np.float32)
    h, w = depth.shape
    xi = np.clip(xs.astype(int), 0, w - 1)
    yi = np.clip(ys.astype(int), 0, h - 1)
    return depth[yi, xi]


class _Noise:
    """Smooth tileable-ish value noise, sampled with drifting offsets. Built at low res, upsampled per frame."""

    def __init__(self, rng, gw, gh, octaves=((12, 1.0), (24, 0.5), (48, 0.25))):
        self.gw, self.gh = gw, gh
        self.layers = []
        tw, th = gw * 2, gh * 2
        for cells, amp in octaves:
            cy = max(2, cells * gh // gw)
            g = rng.random((cy, cells)).astype(np.float32)
            # periodic texture: resize a 3x3 tiling and keep the centre tile, so wrapping has no seam
            big = cv2.resize(np.tile(g, (3, 3)), (tw * 3, th * 3), interpolation=cv2.INTER_CUBIC)
            self.layers.append((np.ascontiguousarray(big[th:2 * th, tw:2 * tw]), amp))
        self.norm = sum(a for _, a in octaves)

    def field(self, offsets):
        acc = np.zeros((self.gh, self.gw), np.float32)
        for (tex, amp), (ox, oy) in zip(self.layers, offsets):
            M = np.float32([[1, 0, -ox], [0, 1, -oy]])
            acc += amp * cv2.warpAffine(tex, M, (self.gw, self.gh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        return acc / self.norm


# ----------------------------------------------------------------------------------------------- effects

class Embers:
    """Slow rising sparks of fire with soft glow; warm colours; occluded by nearer objects."""
    count, speed, size, life, glow = 90, (40, 100), (1.6, 3.6), (2.5, 5.0), 1.0
    colour = np.array([1.0, 0.52, 0.16], np.float32)

    def __init__(self, ctx: Ctx, name="embers"):
        r = ctx.rng(name)
        n = int(self.count * ctx.strength)
        self.ctx = ctx
        s = ctx.h / 1080
        self.x0 = r.uniform(-0.05, 1.05, n) * ctx.w
        self.y0 = r.uniform(0.45, 1.25, n) * ctx.h
        self.vy = r.uniform(*self.speed, n) * s
        self.vx = r.normal(0.15, 0.25, n) * self.vy
        self.wob_a = r.uniform(4, 18, n) * s
        self.wob_f = r.uniform(0.2, 0.7, n)
        self.ph = r.uniform(0, 2 * np.pi, n)
        self.r = r.uniform(*self.size, n) * s
        self.life = r.uniform(*self.life, n)
        self.t0 = r.uniform(0, 1, n) * self.life
        self.z = r.uniform(0.25, 0.85, n)        # depth layer of the particle (1 = near)
        self.fl = r.uniform(4, 10, n)            # flicker rate
        self.heat = r.uniform(0, 1, n)

    def positions(self, t):
        age = (t + self.t0) % self.life
        cyc = np.floor((t + self.t0) / self.life)
        jitter = (np.sin(cyc * 12.9898 + self.ph) * 43758.5453) % 1.0  # new path each respawn, deterministic
        x = self.x0 + (jitter - 0.5) * 0.3 * self.ctx.w + self.vx * age + self.wob_a * np.sin(self.wob_f * 2 * np.pi * age + self.ph)
        y = self.y0 - self.vy * age
        a = np.sin(np.pi * np.clip(age / self.life, 0, 1)) ** 0.7
        return x, y, age, a

    def __call__(self, img, i, depth):
        ctx = self.ctx
        t = i / ctx.fps
        x, y, age, a = self.positions(t)
        a = a * (0.7 + 0.3 * np.sin(self.fl * t + self.ph * 3))
        if depth is not None:  # fade if something nearer covers the particle
            d = _sample(depth, x, y)
            a = a * _smooth((self.z + 0.08 - d) / 0.12)
        # cores: painted-on opaque-ish dots of hot colour (visible on pale skies too); halo: additive light
        alpha = np.zeros((ctx.h, ctx.w), np.float32)
        col = np.zeros((ctx.h, ctx.w, 3), np.float32)
        for k in np.nonzero(a > 0.02)[0]:
            c = self.colour * (0.85 + 0.3 * self.heat[k]) + np.float32([0, 0.3, 0.12]) * self.heat[k]
            ctr = (int(x[k] * 16), int(y[k] * 16))
            rad = max(8, int(self.r[k] * 16))
            cv2.circle(alpha, ctr, rad, float(a[k]), -1, cv2.LINE_AA, shift=4)
            cv2.circle(col, ctr, rad + 16, np.clip(c, 0, 1).tolist(), -1, cv2.LINE_AA, shift=4)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 0.9 * ctx.h / 1080)
        q = 8
        halo = cv2.GaussianBlur(cv2.resize(col * alpha[..., None], (ctx.w // q, ctx.h // q), interpolation=cv2.INTER_AREA),
                                (0, 0), 2.2)
        halo = cv2.resize(halo, (ctx.w, ctx.h), interpolation=cv2.INTER_LINEAR) * (9.0 * self.glow)
        aa = np.clip(alpha * 1.1, 0, 1)[..., None]
        out = img * (1 - aa) + col * aa
        return _screen(out, halo)


class Sparks(Embers):
    """Faster, brighter, fewer, short-lived; drawn as short streaks."""
    count, speed, size, life, glow = 80, (160, 320), (1.0, 2.0), (0.5, 1.2), 1.0
    colour = np.array([1.0, 0.75, 0.35], np.float32)

    def __call__(self, img, i, depth):
        ctx = self.ctx
        t = i / ctx.fps
        x, y, age, a = self.positions(t)
        x2, y2, _, _ = self.positions(t - 1.5 / ctx.fps)
        a = a * (0.5 + 0.5 * np.sin(self.fl * 2 * t + self.ph))
        if depth is not None:
            a = a * _smooth((self.z + 0.08 - _sample(depth, x, y)) / 0.12)
        layer = np.zeros((ctx.h, ctx.w, 3), np.float32)
        for k in np.nonzero(a > 0.03)[0]:
            cv2.line(layer, (int(x2[k] * 16), int(y2[k] * 16)), (int(x[k] * 16), int(y[k] * 16)),
                     np.clip(self.colour * a[k] * 1.6, 0, 1).tolist(), max(1, int(self.r[k] * 1.5)), cv2.LINE_AA, shift=4)
        halo = cv2.GaussianBlur(cv2.resize(layer, (ctx.w // 6, ctx.h // 6), interpolation=cv2.INTER_AREA), (0, 0), 2.5)
        add = cv2.GaussianBlur(layer, (0, 0), 0.7) + cv2.resize(halo, (ctx.w, ctx.h)) * 4.0 * self.glow
        return _screen(img, add)


class Atmosphere:
    """Base for smoke and mist: drifting noise density, coloured from the painting, weighted by depth/height."""

    def __init__(self, ctx: Ctx, name):
        self.ctx = ctx
        r = ctx.rng(name)
        self.gw, self.gh = 320, 180
        self.noise = _Noise(r, self.gw, self.gh)
        self.noise2 = _Noise(r, self.gw, self.gh, octaves=((8, 1.0), (16, 0.5)))
        yy = np.linspace(0, 1, self.gh, dtype=np.float32)[:, None]
        self.yy = np.repeat(yy, self.gw, 1)
        hi, mid, lo = _palette(ctx)
        self.hi, self.mid, self.lo = hi, mid, lo


class Mist(Atmosphere):
    """Pale low-lying mist in the distance; two noise layers drifting opposite ways so it slowly evolves."""

    def __init__(self, ctx, name="mist"):
        super().__init__(ctx, name)
        self.colour = np.clip(0.55 * self.mid + 0.45 * np.float32([0.95, 0.93, 0.9]), 0, 1)

    def __call__(self, img, i, depth):
        t = i / self.ctx.fps
        f1 = self.noise.field([(t * 6, t * 0.5), (t * 9, -t * 0.8), (-t * 14, t)])
        f2 = self.noise2.field([(-t * 4, 0), (t * 7, t * 0.4)])
        dens = _smooth((0.6 * f1 + 0.4 * f2 - 0.32) / 0.38)
        band = _smooth((self.yy - 0.25) / 0.55)       # thicker toward the bottom of the frame
        dens = dens * (0.35 + 0.65 * band)
        dens = cv2.resize(dens, (self.ctx.w, self.ctx.h), interpolation=cv2.INTER_CUBIC)
        if depth is not None:
            dens = dens * (0.25 + 0.75 * _smooth((0.75 - depth) / 0.5))  # mist sits behind near subjects
        a = (0.55 * self.ctx.strength * dens)[..., None]
        return img * (1 - a) + self.colour * a


class Smoke(Atmosphere):
    """Darker rising smoke wisps from the lower frame, domain-warped so the wisps curl."""

    def __init__(self, ctx, name="smoke"):
        super().__init__(ctx, name)
        self.colour = np.clip(self.lo * 0.6 + np.float32([0.32, 0.3, 0.29]) * 0.4, 0, 1)
        gx, gy = np.meshgrid(np.arange(self.gw, dtype=np.float32), np.arange(self.gh, dtype=np.float32))
        self.gx, self.gy = gx, gy

    def __call__(self, img, i, depth):
        t = i / self.ctx.fps
        warp = self.noise2.field([(t * 3, t * 5), (-t * 5, t * 3)]) - 0.5
        f = self.noise.field([(t * 2, t * 14), (-t * 3, t * 22), (t * 5, t * 30)])  # rises (offset y grows)
        mx = (self.gx + warp * 40).astype(np.float32)
        my = (self.gy + warp * 25).astype(np.float32)
        f = cv2.remap(f, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        dens = _smooth((f - 0.36) / 0.32) * (0.15 + 0.85 * _smooth((self.yy - 0.2) / 0.7))
        dens = cv2.resize(dens, (self.ctx.w, self.ctx.h), interpolation=cv2.INTER_CUBIC)
        if depth is not None:
            dens = dens * (0.4 + 0.6 * _smooth((0.85 - depth) / 0.4))
        a = (0.68 * self.ctx.strength * dens)[..., None]
        return img * (1 - a) + self.colour * a


class Glow:
    """Bloom on the painting's own highlights, breathing slowly."""

    def __init__(self, ctx, name="glow"):
        self.ctx = ctx
        self.ph = ctx.rng(name).uniform(0, 6.28)

    def __call__(self, img, i, depth):
        ctx = self.ctx
        t = i / ctx.fps
        small = cv2.resize(img, (ctx.w // 4, ctx.h // 4), interpolation=cv2.INTER_AREA)
        l = _luma(small)
        m = _smooth((l - np.percentile(l, 80)) / 0.25)[..., None]
        src = small * m
        b = cv2.GaussianBlur(src, (0, 0), ctx.h / 4 / 40) * 0.6 + cv2.GaussianBlur(src, (0, 0), ctx.h / 4 / 12) * 0.6
        k = 0.5 * ctx.strength * (1 + 0.12 * np.sin(2 * np.pi * t / 3.2 + self.ph))
        return _screen(img, cv2.resize(b, (ctx.w, ctx.h), interpolation=cv2.INTER_LINEAR) * k)


class Rays:
    """Crepuscular light rays from the brightest region (found once on the still), slow shimmer."""

    def __init__(self, ctx, name="rays"):
        self.ctx = ctx
        r = ctx.rng(name)
        self.ph = r.uniform(0, 100)
        self.src = None
        self.q = 4
        hw, hh = ctx.w // self.q, ctx.h // self.q
        self.yy, self.xx = np.mgrid[0:hh, 0:hw].astype(np.float32)
        hi, mid, _ = _palette(ctx)
        self.colour = np.clip(0.6 * hi + 0.4 * np.float32([1, 0.9, 0.7]), 0, 1)
        self.n1 = r.random(256).astype(np.float32)

    def _find_src(self, small):
        l = cv2.GaussianBlur(_luma(small), (0, 0), 8)
        l[int(l.shape[0] * 0.75):] *= 0.5  # prefer the sky
        y, x = np.unravel_index(np.argmax(l), l.shape)
        return float(x), float(y)

    def __call__(self, img, i, depth):
        ctx = self.ctx
        t = i / ctx.fps
        hw, hh = ctx.w // self.q, ctx.h // self.q
        small = cv2.resize(img, (hw, hh), interpolation=cv2.INTER_AREA)
        if self.src is None:
            self.src = self._find_src(small)
        cx, cy = self.src
        l = _luma(small)
        m = _smooth((l - np.percentile(l, 85)) / 0.2)
        acc = np.zeros_like(m)
        for k in range(24):  # zoom blur toward the source = rays
            s = 1.0 + k * 0.045
            M = np.float32([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]])
            acc += cv2.warpAffine(m, M, (hw, hh), flags=cv2.INTER_LINEAR) * (0.93 ** k)
        acc /= 8.0
        ang = np.arctan2(self.yy - cy, self.xx - cx)
        idx = ((ang / (2 * np.pi) + 0.5) * 255 + t * 1.5 + self.ph)
        lo = np.floor(idx).astype(int) % 256
        fr = idx - np.floor(idx)
        stripes = self.n1[lo] * (1 - fr) + self.n1[(lo + 1) % 256] * fr
        stripes = 0.45 + 0.55 * _smooth(stripes)
        rays = cv2.GaussianBlur(acc * stripes, (0, 0), 1.5)
        rays = cv2.resize(rays, (ctx.w, ctx.h), interpolation=cv2.INTER_CUBIC)
        k = 0.75 * ctx.strength * (1 + 0.1 * np.sin(t * 1.3 + self.ph))
        return _screen(img, rays[..., None] * self.colour * k)


class Rain:
    """Thin slanted streaks in two depth layers, cool tint, slight darkening."""

    def __init__(self, ctx, name="rain"):
        self.ctx = ctx
        r = ctx.rng(name)
        n = int(650 * ctx.strength)
        s = ctx.h / 1080
        self.x0 = r.uniform(-0.1, 1.2, n) * ctx.w
        self.y0 = r.uniform(0, 1, n) * ctx.h
        self.v = r.uniform(900, 1500, n) * s
        self.len = r.uniform(18, 46, n) * s
        self.a = r.uniform(0.18, 0.42, n)
        self.z = r.uniform(0.2, 0.95, n)
        self.slant = 0.18

    def __call__(self, img, i, depth):
        ctx = self.ctx
        t = i / ctx.fps
        y = (self.y0 + self.v * t) % (ctx.h + 60) - 30
        x = self.x0 - self.slant * y
        a = self.a.copy()
        if depth is not None:
            a *= _smooth((self.z + 0.1 - _sample(depth, x, y)) / 0.15)
        layer = np.zeros((ctx.h, ctx.w), np.float32)
        for k in np.nonzero(a > 0.01)[0]:
            dy = self.len[k]
            cv2.line(layer, (int(x[k] * 16), int(y[k] * 16)), (int((x[k] - self.slant * dy) * 16), int((y[k] - dy) * 16)),
                     float(a[k]), 1, cv2.LINE_AA, shift=4)
        layer = cv2.GaussianBlur(layer, (0, 0), 0.6)[..., None]
        out = img * 0.94 + np.float32([0.0, 0.01, 0.025])
        return _screen(out, layer * np.float32([0.82, 0.88, 0.95]))


class Stars:
    """Twinkle: stars placed in the dark, distant sky of the still, moved with the camera via ctx.project."""

    def __init__(self, ctx, name="stars"):
        self.ctx = ctx
        r = ctx.rng(name)
        st = ctx.still
        if st is None:
            self.pts = np.zeros((0, 2), np.float32)
            return
        sh, sw = st.shape[:2]
        l = _luma(st)
        d = ctx.still_depth if ctx.still_depth is not None else np.zeros_like(l)
        sky = (l < 0.45) & (d < 0.3)
        sky[int(sh * 0.7):] = False
        sky = cv2.erode(sky.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
        # existing painted stars: small bright local maxima inside the sky
        blur = cv2.GaussianBlur(l, (0, 0), 4)
        peak = (l - blur > 0.12) & (l == cv2.dilate(l, np.ones((5, 5), np.uint8)))
        ys, xs = np.nonzero(peak & cv2.dilate(sky.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool))
        old = np.stack([xs, ys], 1)[:60] if len(xs) else np.zeros((0, 2))
        ys, xs = np.nonzero(sky)
        new = np.zeros((0, 2))
        if len(xs):
            k = r.choice(len(xs), size=min(len(xs), int(70 * ctx.strength)), replace=False)
            new = np.stack([xs[k], ys[k]], 1)
        pts = np.concatenate([old, new]).astype(np.float32)
        self.pts = pts / np.float32([sw, sh])
        n = len(self.pts)
        self.size = np.concatenate([np.full(len(old), 1.6), r.uniform(0.6, 1.5, len(new))]).astype(np.float32)
        self.base = np.concatenate([np.full(len(old), 0.5), r.uniform(0.35, 0.8, len(new))]).astype(np.float32)
        self.rate = r.uniform(0.6, 2.2, n)
        self.ph = r.uniform(0, 6.28, n)
        self.cross = r.random(n) < 0.12

    def __call__(self, img, i, depth):
        ctx = self.ctx
        if not len(self.pts) or ctx.project is None:
            return img
        t = i / ctx.fps
        xy = ctx.project(i, self.pts, 0.0)
        s = ctx.h / 1080
        tw = self.base * (0.55 + 0.45 * np.sin(self.rate * 2 * np.pi * t + self.ph)) ** 2
        layer = np.zeros((ctx.h, ctx.w), np.float32)
        for k in range(len(xy)):
            x, y = xy[k]
            if not (0 <= x < ctx.w and 0 <= y < ctx.h):
                continue
            r = max(1, int(self.size[k] * s * 16))
            cv2.circle(layer, (int(x * 16), int(y * 16)), r, float(tw[k]), -1, cv2.LINE_AA, shift=4)
            if self.cross[k]:
                L = int(9 * s * 16 * tw[k])
                cv2.line(layer, (int(x * 16) - L, int(y * 16)), (int(x * 16) + L, int(y * 16)), float(tw[k] * 0.5), 1, cv2.LINE_AA, shift=4)
                cv2.line(layer, (int(x * 16), int(y * 16) - L), (int(x * 16), int(y * 16) + L), float(tw[k] * 0.5), 1, cv2.LINE_AA, shift=4)
        glow = cv2.GaussianBlur(layer, (0, 0), 3 * s) * 2.5
        add = (cv2.GaussianBlur(layer, (0, 0), 0.6) + glow)[..., None] * np.float32([0.95, 0.96, 1.0])
        return _screen(img, add)


class Flash:
    """Warm bloom-flash on each event frame (pose snap). Lifts highlights more than shadows, decays in ~6 frames."""

    def __init__(self, ctx, name="flash"):
        self.ctx = ctx
        self.ev = sorted(ctx.events) if ctx.events else [0]
        hi, _, _ = _palette(ctx)
        self.colour = np.clip(0.5 * hi + 0.5 * np.float32([1, 0.95, 0.85]), 0, 1)

    def level(self, i):
        v = 0.0
        for e in self.ev:
            if i >= e:
                v = max(v, np.exp(-(i - e) / 2.4))
            elif i == e - 1:
                v = max(v, 0.35)  # one-frame lead-in reads as light, not as a cut glitch
        return v

    def __call__(self, img, i, depth):
        v = self.level(i) * self.ctx.strength
        if v < 0.005:
            return img
        # exposure punch + warm light: keeps the painting's saturation instead of greying it like a white overlay
        l = _luma(img)[..., None]
        out = img * (1.0 + 0.9 * v * (0.4 + l)) + self.colour * (0.12 * v)
        return _softclip(out)


def _softclip(x, knee=0.85):
    """Values above `knee` roll off smoothly toward 1 (no hard clipped flat patches)."""
    over = np.maximum(x - knee, 0)
    return np.where(x > knee, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee))), x)


class Finish:
    """Always on: fine paper-like grain (cycled from 8 pre-made tiles) and a soft vignette."""

    def __init__(self, ctx, grain=0.016, vignette=0.09):
        self.ctx = ctx
        r = ctx.rng("grain")
        self.tiles = []
        for _ in range(8):
            g = r.normal(0, 1, (ctx.h, ctx.w)).astype(np.float32)
            g = cv2.GaussianBlur(g, (0, 0), 0.7)
            self.tiles.append((g / g.std() * grain).astype(np.float16))
        self.order = r.integers(0, 8, max(1, ctx.n_frames))
        yy, xx = np.mgrid[0:ctx.h, 0:ctx.w].astype(np.float32)
        rr = np.sqrt(((xx - ctx.w / 2) / (ctx.w / 2)) ** 2 + ((yy - ctx.h / 2) / (ctx.h / 2)) ** 2) / np.sqrt(2)
        self.vig = (1 - vignette * _smooth((rr - 0.35) / 0.65))[..., None].astype(np.float32)

    def __call__(self, img, i, depth):
        g = self.tiles[self.order[i % len(self.order)]].astype(np.float32)[..., None]
        l = _luma(img)[..., None]
        img = img + g * (0.4 + 2.4 * l * (1 - l))  # grain mostly in mid-tones, like pigment on paper
        return img * self.vig


_REG = {"embers": Embers, "sparks": Sparks, "smoke": Smoke, "mist": Mist, "glow": Glow, "rays": Rays,
        "rain": Rain, "stars": Stars, "flash": Flash}


def build(names, ctx: Ctx, finish: bool = True):
    """Return chain(frame, i, depth=None) applying the named effects in a fixed, sensible order."""
    names = list(names or [])
    bad = [n for n in names if n not in _REG]
    if bad:
        raise ValueError(f"unknown fx: {bad}")
    fxs = [_REG[n](ctx) for n in ORDER if n in names]
    fin = Finish(ctx) if finish else None

    def chain(frame, i, depth=None, mask=None):
        """mask: optional HxW (1 = painted area); effects are kept off the bare paper border."""
        out = frame
        for f in fxs:
            out = f(out, i, depth)
        if mask is not None and fxs:
            m = mask[..., None]
            out = frame + (out - frame) * m
        if fin is not None:
            out = fin(out, i, depth)
        return np.clip(out, 0, 1)

    return chain


def apply(name, frame, i, ctx: Ctx, depth=None, _cache={}):
    """Single-effect convenience: frame-in / frame-out. Effect objects are cached per (id(ctx), name)."""
    key = (id(ctx), name)
    if key not in _cache:
        _cache[key] = (_REG[name] if name in _REG else (lambda c: Finish(c)))(ctx)
    return np.clip(_cache[key](frame, i, depth), 0, 1)
