"""Sky title: a film-title line that rises into the sky of a local shot, behind the figures (motion stage).

shots.json, on a `source: "local"` shot:
    "sky_title": {"text": "Mahakali", "sub": ["जयन्ती ... ।", "दुर्गा ... ॥"], "start": 0.2, "rise": 1.4, "y": 0.24}

How it is built (motion.py calls `SkyTitle.apply` on every frame, before the fx chain):
- The title is laid out in the *still's* coordinates (positions given as fractions of the 1920x1080 picture are
  converted with the camera at the moment the title settles) and drawn at 2x still resolution. Each frame it is
  pulled through the same per-pixel camera maps as the painting, so it drifts and parallaxes exactly with the sky
  it sits in: part of the scene, not an overlay.
- Occlusion: the depth map is thresholded a little nearer than the sky behind the title, opened with a disc about
  3 % of the still width (so thin things such as a trident shaft or petals do not cut holes in the letters; only
  large shapes such as figures, the lion and hills do), grown 2 px and feathered. The matte lives in still space
  and is computed once per depth map, so it cannot flicker.
- Look: title in Avenir Next Demi Bold capitals with a vertical gradient (pale gold -> brand gold -> deeper gold),
  a thin soft umber shadow for edge definition, and a warm glow that blooms as the letters arrive, then settles.
- Sub lines (`sub`, one string with newlines or a list): Latin lines in Avenir Next Medium capitals; lines with
  Devanagari in Devanagari Sangam MN Bold, shaped by HarfBuzz/libraqm (see shape_text.py; the render stops with an
  error rather than draw unshaped Devanagari). Pale-gold gradient, same shadow, a gentler glow.
- Motion: the title rises `travel` with a slow ease-out (power 2.4) over `rise` s, fading in over the first 55 % and
  sharpening from a soft blur while its letter-spacing opens from 0.16 to 0.22 em; then it holds (moving only with
  the camera). Each sub line does the same, smaller and quicker (`sub_rise`), starting at `sub_at`, one after
  another `sub_stagger` s apart. No overshoot.

Keys (fractions are of the picture, i.e. the 1920x1080 clip; seconds from the start of the clip):
  text         required; Latin, drawn in capitals
  sub          optional; string (newline = new line) or list of lines; Latin or Devanagari per line
  start        0.2    when the title starts rising (s)
  rise         1.4    length of the title's rise (s); it is settled at start + rise
  x            0.5    centre of the title block (fraction of picture width); move it into open sky
  y            0.26   resting height of the title's centre (fraction of picture height)
  size         0.12   title capital height (fraction of picture height); shrunk if wider than max_width
  max_width    0.72   widest the title and each sub line may be (fraction of picture width)
  travel       0.10   how far below its resting place the title starts (fraction of picture height)
  sub_size     0.034  sub-line letter height: capitals, or headline to baseline for Devanagari (fraction of
                      picture height); shrunk if a line would exceed max_width
  sub_at       start + rise - 0.1   when the first sub line starts (s)
  sub_rise     0.9    length of each sub line's rise (s)
  sub_stagger  0.22   delay between sub lines (s)
  glow         1.0    glow strength (0 = none, 2 = double)
  occlude      true   hide the title behind nearer things (depth matte)
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .captions import font as _font

DEFAULTS = {"start": 0.2, "rise": 1.4, "x": 0.5, "y": 0.26, "size": 0.12, "max_width": 0.72, "travel": 0.10,
            "sub_size": 0.034, "sub_rise": 0.9, "sub_stagger": 0.22, "glow": 1.0, "occlude": True}
# (min, max) for every numeric key; shots.py uses this for validation
RANGES = {"start": (0.0, 5.0), "rise": (0.3, 4.0), "x": (0.2, 0.8), "y": (0.06, 0.8), "size": (0.03, 0.3), "max_width": (0.3, 0.9),
          "travel": (0.0, 0.4), "sub_size": (0.012, 0.08), "sub_at": (0.0, 8.0), "sub_rise": (0.2, 3.0),
          "sub_stagger": (0.0, 2.0), "glow": (0.0, 2.0)}
KEYS = set(DEFAULTS) | {"text", "sub", "sub_at", "note"}

DEVA_FONT = ("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc", 1)   # Bold
SS = 2                 # supersampling of the title layers relative to the still
TR0, TR1 = 0.16, 0.22  # title letter-spacing (em) at the start / end of the rise
SUB_TR = 0.20          # Latin sub-line letter-spacing (em)

_c = lambda *v: np.float32(v) / 255.0
TOP, MID, BOT = _c(255, 243, 212), _c(244, 198, 92), _c(206, 136, 44)   # title gradient (MID ~ brand #f2c14e)
STOP, SBOT = _c(255, 244, 218), _c(240, 190, 98)                         # sub-line gradient
GLOW = _c(255, 178, 96)
SHADOW = _c(46, 18, 8)
SHADE = np.float32([0.62, 0.42, 0.36])   # multiply colour of the sky shade (warm: the sky deepens toward red)
SHADE_K, SHADOW_K = 0.42, 0.7


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _ease_out(x):
    """Slow ease-out (power 2.4: the rise stays visible after the fade-in, then glides to rest; no overshoot)."""
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 2.4


def is_devanagari(s: str) -> bool:
    return any("ऀ" <= c <= "ॿ" for c in s)


def sub_lines(spec: dict) -> list[str]:
    sub = spec.get("sub") or []
    if isinstance(sub, str):
        sub = sub.split("\n")
    return [str(x).strip() for x in sub if str(x).strip()]


def timing(spec: dict) -> dict:
    """Key times (s from clip start): title settled, every sub line settled, all settled."""
    s = dict(DEFAULTS, **spec)
    t_title = float(s["start"]) + float(s["rise"])
    sub_at = float(s.get("sub_at", t_title - 0.1))
    n = len(sub_lines(s))
    t_sub = sub_at + (n - 1) * float(s["sub_stagger"]) + float(s["sub_rise"]) if n else t_title
    return {"title": t_title, "sub_at": sub_at, "all": max(t_title, t_sub)}


class _Glyphs:
    """Per-character alpha bitmaps of one font, placed at sub-pixel positions (no 1-px jitter while spacing eases)."""

    def __init__(self, f):
        self.f = f
        self.asc, self.desc = f.getmetrics()
        self.pad = 3
        self.cache = {}

    def glyph(self, ch):
        if ch not in self.cache:
            w = int(math.ceil(self.f.getlength(ch))) + 2 * self.pad
            h = self.asc + self.desc + 2 * self.pad
            im = Image.new("L", (max(1, w), h), 0)
            ImageDraw.Draw(im).text((self.pad, self.pad + self.asc), ch, font=self.f, fill=255, anchor="ls")
            self.cache[ch] = np.asarray(im, np.float32) / 255.0
        return self.cache[ch]

    def width(self, text, tr):
        return sum(self.f.getlength(c) for c in text) + tr * (len(text) - 1)

    def draw(self, canvas, text, x, base_y, tr):
        """Draw `text` with its left end at x and baseline at base_y (float canvas px)."""
        for ch in text:
            if ch != " ":
                _paste(canvas, self.glyph(ch), x - self.pad, base_y - self.pad - self.asc)
            x += self.f.getlength(ch) + tr


def _paste(canvas, g, ox, oy):
    """max-composite bitmap g into canvas with its top-left at float (ox, oy)."""
    ix, iy = int(math.floor(ox)), int(math.floor(oy))
    gh, gw = g.shape
    M = np.float32([[1, 0, ox - ix], [0, 1, oy - iy]])
    gs = cv2.warpAffine(g, M, (gw + 1, gh + 1), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    H, W = canvas.shape
    x0, y0, x1, y1 = max(0, ix), max(0, iy), min(W, ix + gw + 1), min(H, iy + gh + 1)
    if x1 > x0 and y1 > y0:
        canvas[y0:y1, x0:x1] = np.maximum(canvas[y0:y1, x0:x1], gs[y0 - iy:y1 - iy, x0 - ix:x1 - ix])


def _sub_bitmaps(lines, body_px, maxw):
    """Static alpha bitmap per sub line: [(alpha, baseline_y, body_height)], each line at most maxw wide."""
    from .shape_text import render_lines
    out = [None] * len(lines)
    deva = [k for k, l in enumerate(lines) if is_devanagari(l)]
    if deva:
        def req(size):
            return [{"text": lines[k], "font": DEVA_FONT[0], "index": DEVA_FONT[1], "size": size} for k in deva]
        probe = render_lines(req(100))
        ratio = min(p[2] for p in probe) / 100.0            # body height per px of font size
        size = body_px / ratio
        widest = max(p[0].shape[1] for p in probe) / 100.0
        size = min(size, maxw / widest)
        for k, r in zip(deva, render_lines(req(int(round(size))))):
            out[k] = r
    for k, l in enumerate(lines):
        if out[k] is not None:
            continue
        txt = l.upper()
        f = _font(max(8, int(round(body_px / 0.71))), "Medium")
        g = _Glyphs(f)
        w = g.width(txt, SUB_TR * f.size)
        if w > maxw:
            f = _font(max(8, int(round(f.size * maxw / w))), "Medium")
            g = _Glyphs(f)
            w = g.width(txt, SUB_TR * f.size)
        canvas = np.zeros((g.asc + g.desc + 8, int(math.ceil(w)) + 8), np.float32)
        g.draw(canvas, txt, 4, 4 + g.asc, SUB_TR * f.size)
        out[k] = (canvas, 4 + g.asc, f.size * 0.71)
    return out


class SkyTitle:
    def __init__(self, spec: dict, cam, fps: int, sky_depth: np.ndarray, pdepth: np.ndarray):
        """cam: motion.Camera; sky_depth: raw depth of the still (1 = near); pdepth: its parallax depth."""
        self.spec = dict(DEFAULTS, **spec)
        s = self.spec
        self.fps = fps
        tm = timing(s)
        self.start, self.rise = float(s["start"]), float(s["rise"])
        self.sub_at, self.sub_rise, self.sub_stagger = tm["sub_at"], float(s["sub_rise"]), float(s["sub_stagger"])
        self.text = str(s["text"]).upper()
        self.glow_k = float(s["glow"])
        sw, sh, W, H = cam.sw, cam.sh, cam.W, cam.H

        # --- picture -> still conversion at the moment the title settles (sky depth for the parallax terms)
        i_s = min(cam.n - 1, max(0, int(round(tm["title"] * fps))))
        z, ox, oy, dolly = cam.params(i_s)
        y_pic = float(s["y"]) * H
        row = int(np.clip(sh / 2 + (y_pic - H / 2) / cam.k0 + oy, 0, sh - 1))
        band = pdepth[max(0, row - sh // 20):row + sh // 20 + 1]
        dsky = float(np.percentile(band, 20))
        sc = 1.0 + cam.P * 1.25 * dsky
        k = cam.k0 * math.exp(math.log(z) * sc)    # picture px per still px at the sky's depth
        dl = 0.012 * sw * dolly * cam.P
        cx_s = sw / 2 + (float(s["x"]) - 0.5) * W / k + ox * sc - dl * dsky
        cy_s = sh / 2 + (y_pic - H / 2) / k + oy * sc
        to_c = SS * 1.0 / k                          # picture px -> canvas px

        # --- title font, fitted to max_width
        maxw = float(s["max_width"]) * W * to_c
        cap = float(s["size"]) * H * to_c
        f = _font(max(8, int(round(cap / 0.71))), "Demi Bold")   # Avenir Next cap height is 0.71 em
        wt = _Glyphs(f).width(self.text, TR1 * f.size)
        if wt > maxw:
            f = _font(max(8, int(round(f.size * maxw / wt))), "Demi Bold")
        self.gl, self.cap = _Glyphs(f), f.size * 0.71
        wmax = self.gl.width(self.text, TR1 * f.size)

        # --- sub lines (static bitmaps), stacked under the title
        self.subs = []
        lines = sub_lines(s)
        if lines:
            body = float(s["sub_size"]) * H * to_c
            bms = _sub_bitmaps(lines, body, maxw)
            body = max(b[2] for b in bms)
            self.sub_body = body
            deva = any(is_devanagari(l) for l in lines)
            pitch = body * (2.15 if deva else 1.9)
            # first sub line's top (headline) sits 0.62 title caps below the title baseline
            base = self.cap / 2 + 0.62 * self.cap + body       # baseline of line 1, relative to the title centre
            for j, (bm, bl, bd) in enumerate(bms):
                self.subs.append({"bm": bm, "bl": bl, "dy": base + j * pitch, "w": bm.shape[1]})
                wmax = max(wmax, bm.shape[1])
            self.sub_travel = 0.35 * self.cap
        self.travel = float(s["travel"]) * H * to_c

        # --- canvas: a box in still*SS space covering the whole travel plus glow margin
        margin = 1.2 * self.cap
        below = (self.subs[-1]["dy"] + self.subs[-1]["bm"].shape[0] - self.subs[-1]["bl"] + self.sub_travel
                 if self.subs else self.cap / 2)
        top = cy_s * SS - self.cap / 2 - margin
        bottom = cy_s * SS + max(below, self.cap / 2 + self.travel) + margin
        left, right = cx_s * SS - wmax / 2 - margin, cx_s * SS + wmax / 2 + margin
        self.bx0, self.by0 = int(math.floor(left)), int(math.floor(top))
        self.cw, self.ch = int(math.ceil(right)) - self.bx0, int(math.ceil(bottom)) - self.by0
        self.cx = cx_s * SS - self.bx0           # title centre x in canvas px
        self.cy = cy_s * SS - self.by0           # resting cap-centre y in canvas px
        self.rows = np.arange(self.ch, dtype=np.float32)[:, None, None]

        # --- occlusion matte (still space -> canvas)
        self.occlude = bool(s["occlude"])
        self._vis_cache = {}
        self.sky_band = (int(np.clip(top / SS, 0, sh - 1)), int(np.clip(bottom / SS, 1, sh)))
        self.vis0 = self._vis(sky_depth)

    # ------------------------------------------------------------------ matte
    def _vis(self, d):
        """Visibility of the title (1 = sky, 0 = something nearer in front), canvas-sized; cached per depth map."""
        key = id(d)
        if key in self._vis_cache:
            return self._vis_cache[key]
        if not self.occlude or d is None:
            v = np.ones((self.ch, self.cw), np.float32)
        else:
            sh, sw = d.shape
            y0, y1 = self.sky_band
            x0 = int(np.clip(self.bx0 / SS, 0, sw - 1))
            x1 = int(np.clip((self.bx0 + self.cw) / SS, x0 + 1, sw))
            dsky = float(np.percentile(d[y0:y1, x0:x1], 25))   # the sky behind the title (figures cover < 75 %)
            occ = (d > dsky + 0.10).astype(np.uint8)
            r = max(5, int(sw * 0.03)) | 1                       # opening: only large shapes occlude
            occ = cv2.morphologyEx(occ, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r)))
            occ = cv2.dilate(occ, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
            vis = 1.0 - cv2.GaussianBlur(occ.astype(np.float32), (0, 0), max(1.5, sw / 600))
            xs = (np.arange(self.cw, dtype=np.float32) + self.bx0 - (SS - 1) / 2) / SS
            ys = (np.arange(self.ch, dtype=np.float32) + self.by0 - (SS - 1) / 2) / SS
            mx, my = np.meshgrid(xs, ys)
            v = cv2.remap(vis, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        self._vis_cache = {key: v}
        return v

    # ------------------------------------------------------------------ layers
    @staticmethod
    def _grad(rows, top, h, cols):
        g = np.clip((rows - top) / max(1.0, h), 0, 1)
        if len(cols) == 2:
            return cols[0] + (cols[1] - cols[0]) * g
        a, b, c = cols
        return np.where(g < 0.5, a + (b - a) * (g * 2), b + (c - b) * (g * 2 - 1))

    def _layers(self, t):
        """Canvas-sized layers: premultiplied colour, alpha, glow, shadow (or None before the title starts)."""
        u = (t - self.start) / self.rise
        if u <= 0:
            return None
        cap = self.cap
        e = _ease_out(u)
        tr = (TR0 + (TR1 - TR0) * e) * self.gl.f.size
        base = self.cy + self.travel * (1 - e) + cap / 2
        A = np.zeros((self.ch, self.cw), np.float32)
        self.gl.draw(A, self.text, self.cx - self.gl.width(self.text, tr) / 2, base, tr)
        blur = 0.09 * cap * (1 - e) ** 1.5
        if blur > 0.25:
            A = cv2.GaussianBlur(A, (0, 0), blur)
        A *= float(_smooth(u / 0.55))
        prem = self._grad(self.rows, base - cap, cap, (TOP, MID, BOT)) * A[..., None]
        alpha = A.copy()
        bloom = 0.42 + 0.75 * float(_smooth((u - 0.1) / 0.65)) * math.exp(-max(0.0, u - 0.8) / 0.45)

        Ssum = None
        for j, sl in enumerate(self.subs):
            v = (t - self.sub_at - j * self.sub_stagger) / self.sub_rise
            if v <= 0:
                continue
            ev = _ease_out(v)
            S = np.zeros_like(A)
            sbase = self.cy + sl["dy"] + self.sub_travel * (1 - ev)
            _paste(S, sl["bm"], self.cx - sl["w"] / 2, sbase - sl["bl"])
            sb = 0.15 * self.sub_body * (1 - ev) ** 1.5
            if sb > 0.25:
                S = cv2.GaussianBlur(S, (0, 0), sb)
            S *= float(_smooth(v / 0.6))
            col = self._grad(self.rows, sbase - 1.5 * self.sub_body, 2.2 * self.sub_body, (STOP, SBOT))
            prem = prem * (1 - S[..., None]) + col * S[..., None]
            alpha = 1 - (1 - alpha) * (1 - S)
            Ssum = S if Ssum is None else np.maximum(Ssum, S)

        # shadow: thin, soft, a touch below -> edge definition on a bright sky
        q = 2
        sm = cv2.resize(alpha, (self.cw // q, self.ch // q), interpolation=cv2.INTER_AREA)
        shadow = cv2.GaussianBlur(sm, (0, 0), max(0.8, 0.05 * cap / q))
        shadow = np.roll(shadow, max(1, int(round(0.025 * cap / q))), axis=0)
        # glow: wide warm bloom + tight halo; blooms as the letters arrive, then settles
        q2 = 4
        sm2 = cv2.resize(A, (self.cw // q2, self.ch // q2), interpolation=cv2.INTER_AREA)
        glow = (cv2.GaussianBlur(sm2, (0, 0), 0.45 * cap / q2) * 0.9 +
                cv2.GaussianBlur(sm2, (0, 0), 0.12 * cap / q2) * 0.6) * bloom * self.glow_k
        if Ssum is not None:
            sm3 = cv2.resize(Ssum, (self.cw // q2, self.ch // q2), interpolation=cv2.INTER_AREA)
            glow += cv2.GaussianBlur(sm3, (0, 0), 0.8 * self.sub_body / q2 + 1) * 0.18 * self.glow_k
        # shade: a broad, soft deepening of the sky behind the letters (like the shadow of a thin cloud), so pale
        # gold stays readable on a bright dawn sky; it arrives with the letters
        shade = cv2.GaussianBlur(sm2, (0, 0), 0.35 * cap / q2) * 1.6
        if Ssum is not None:
            shade = np.maximum(shade, cv2.GaussianBlur(sm3, (0, 0), 0.9 * self.sub_body / q2 + 1) * 2.2)
        shade = np.clip(shade, 0, 1) * SHADE_K
        shadow = cv2.resize(shadow, (self.cw, self.ch), interpolation=cv2.INTER_LINEAR)
        glow = cv2.resize(glow, (self.cw, self.ch), interpolation=cv2.INTER_LINEAR)
        shade = cv2.resize(shade, (self.cw, self.ch), interpolation=cv2.INTER_LINEAR)
        return prem, alpha, glow, shadow, shade

    def apply(self, rgb, i, mx, my, raw_depth=None):
        """Composite the title into the camera-warped frame `rgb` (float 0..1, HxWx3) using the frame's maps."""
        L = self._layers(i / self.fps)
        if L is None:
            return rgb
        prem, alpha, glow, shadow, shade = L
        vis = self._vis(raw_depth) if raw_depth is not None else self.vis0
        l1 = np.dstack([prem * vis[..., None], alpha * vis]).astype(np.float32)
        l2 = np.dstack([glow * vis, shadow * vis, shade * vis, np.zeros_like(vis)]).astype(np.float32)
        # output px -> canvas px (canvas = still px * SS, pixel centres aligned)
        cx = (mx * SS + (SS - 1) / 2 - self.bx0).astype(np.float32)
        cy = (my * SS + (SS - 1) / 2 - self.by0).astype(np.float32)
        o1 = cv2.remap(l1, cx, cy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        o2 = cv2.remap(l2, cx, cy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        sd = np.clip(o2[..., 2:3], 0, 1)
        out = rgb * (1 - sd) + SHADE * sd * rgb          # deepen (multiply toward a warm dark), keeps the sky's hue
        sh = np.clip(o2[..., 1:2] * SHADOW_K, 0, 1)
        out = out * (1 - sh) + SHADOW * sh
        out = 1.0 - (1.0 - out) * (1.0 - np.clip(GLOW * o2[..., 0:1], 0, 1))
        a = np.clip(o1[..., 3:4], 0, 1)
        return out * (1 - a) + o1[..., :3]
