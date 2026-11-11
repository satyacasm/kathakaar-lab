"""Animated cinematic captions for music reels (generalised from episodes/006-jatayu-ravana/captions_anim.py).

Caption spec (script/edit.json "captions"):
  {"text": "He fought *anyway.*", "b0": 2, "b1": 3, "hit": true}
  - *words* between asterisks render gold, the rest white
  - b0/b1 = bar indices (times follow the song grid); off0/off1 = second offsets
  - or t0/t1 = absolute seconds from the start of the reel (used for the end card)
  - hit: small scale punch on entry (for lines that land on a beat)
  - style "title": large gold word + optional "sub" line
Motion: blur-to-sharp + letters converge on entry (0.45 s), slow tracking "breath" while held,
blur-out on exit (0.35 s).
"""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/System/Library/Fonts/Avenir Next.ttc"
WHITE = (250, 247, 240)
GOLD = (242, 193, 78)        # brand yellow #f2c14e
IN, OUT = 0.45, 0.35


@lru_cache(None)
def font(size, want):
    for i in range(16):
        try:
            f = ImageFont.truetype(FONT, size, index=i)
        except OSError:
            break
        if " ".join(f.getname()).lower().endswith(want.lower()):
            return f
    return ImageFont.truetype(FONT, size)


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def runs(text):
    """'He fought *anyway.*' -> [(char, colour), ...] uppercase."""
    out, gold = [], False
    for ch in text:
        if ch == "*":
            gold = not gold
            continue
        out.append((ch.upper(), GOLD if gold else WHITE))
    return out


def line_image(chars, f, tracking, halo_px):
    w = int(sum(f.getlength(c) for c, _ in chars) + tracking * (len(chars) - 1)) + 4 * halo_px
    h = int(f.size * 1.5) + 4 * halo_px
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td, hd = ImageDraw.Draw(txt), ImageDraw.Draw(halo)
    x, y = 2 * halo_px, 2 * halo_px
    for c, col in chars:
        hd.text((x, y), c, font=f, fill=(0, 0, 0, 230))
        td.text((x, y), c, font=f, fill=col + (255,))
        x += f.getlength(c) + tracking
    halo = halo.filter(ImageFilter.GaussianBlur(halo_px))
    return Image.alpha_composite(Image.alpha_composite(halo, halo), txt)


class Captions:
    # landscape defaults; make_short.py passes a vertical layout
    LAYOUT = dict(cap_size=36, cap_y=None, lyric_size=96, lyric_tr=30, lyric_y=None,
                  title_y=0.10, title_size=96, title_tr=26, sub_size=22, sub_tr=7)

    def __init__(self, spec, bars, size, layout=None):
        self.W, self.H = size
        self.L = dict(self.LAYOUT, **(layout or {}))
        self.items = []
        for c in spec:
            if "t0" in c:
                t0, t1 = c["t0"], c["t1"]
            else:
                t0 = bars[c["b0"]] + c.get("off0", 0.12)
                t1 = bars[c["b1"]] + c.get("off1", -0.12)
            self.items.append((t0, t1, c))

    def frame(self, t):
        """Return an RGBA overlay for time t, or None when no caption is visible."""
        layer = None
        for t0, t1, c in self.items:
            if not (t0 <= t <= t1):
                continue
            layer = layer or Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            self._draw(layer, t, t0, t1, c)
        return layer

    @lru_cache(None)
    def _static_title(self, text, sub):
        """The approved end card (v3), drawn exactly as before: plain fade, no motion."""
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        hd, td = ImageDraw.Draw(halo), ImageDraw.Draw(img)
        L = self.L
        y = int(self.H * L["title_y"])
        for txt, f, col, tr in [(text.upper(), font(L["title_size"], "Bold"), GOLD, L["title_tr"]),
                                (sub.upper(), font(L["sub_size"], "Medium"), WHITE, L["sub_tr"])]:
            w = sum(f.getlength(ch) for ch in txt) + tr * (len(txt) - 1)
            x = (self.W - w) / 2
            for ch in txt:
                hd.text((x, y), ch, font=f, fill=(0, 0, 0, 210))
                td.text((x, y), ch, font=f, fill=col + (255,))
                x += f.getlength(ch) + tr
            y += f.size + 22
        halo = halo.filter(ImageFilter.GaussianBlur(10))
        return Image.alpha_composite(Image.alpha_composite(halo, halo), img)

    def _lyric(self, layer, t, t0, t1, c):
        """Song lyric, centre screen: Optima caps, word 1 white / word 2 gold, gold glow, blur-in on the beat."""
        p_in = ease_out((t - t0) / 0.22)
        p_out = ease_out((t1 - t) / 0.18)
        alpha = min(p_in, p_out)
        held = (t - t0) / max(0.01, t1 - t0)
        L = self.L
        f = ImageFont.truetype("/System/Library/Fonts/Optima.ttc", L["lyric_size"], index=1)
        k = L["lyric_tr"] / 30
        tracking = L["lyric_tr"] + ((1 - p_in) * 40 + held * 8) * k
        words = c["text"].upper().split()
        chars = [(ch, WHITE) for ch in words[0]] + [(" ", WHITE)] + [(ch, GOLD) for ch in " ".join(words[1:])]
        img = line_image(chars, f, tracking, 6)
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        x = 12
        for ch, _ in chars:
            gd.text((x, 12), ch, font=f, fill=GOLD + (150,))
            x += f.getlength(ch) + tracking
        glow = glow.filter(ImageFilter.GaussianBlur(22))
        img = Image.alpha_composite(glow, img)
        s = 1.0 + 0.05 * held + (0.06 * (1 - p_in))
        img = img.resize((int(img.width * s), int(img.height * s)), Image.BILINEAR)
        blur = (1 - p_in) * 9 + (1 - p_out) * 7
        if blur > 0.3:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        if alpha < 1:
            img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
        cy = self.L["lyric_y"] or self.H // 2
        layer.alpha_composite(img, ((self.W - img.width) // 2, cy - img.height // 2))

    def _draw(self, layer, t, t0, t1, c):
        title = c.get("style") == "title"
        if c.get("style") == "lyric":
            return self._lyric(layer, t, t0, t1, c)
        if c.get("static"):
            im = self._static_title(c["text"].strip("*"), c.get("sub", "")).copy()
            a = min(1.0, (t - t0) / 0.6, (t1 - t) / 0.6)
            im.putalpha(im.getchannel("A").point(lambda v: int(v * max(0.0, a))))
            layer.alpha_composite(im)
            return
        p_in = ease_out((t - t0) / IN)
        p_out = ease_out((t1 - t) / OUT)
        alpha = min(p_in, p_out)
        held = (t - t0) / max(0.01, t1 - t0)                   # 0..1 across the caption's life
        base_tr = 28 if title else 7
        tracking = base_tr + (1 - p_in) * (18 if title else 12) + held * (10 if title else 3)
        blur = (1 - p_in) * 7 + (1 - p_out) * 6
        scale = 1.0 + (0.10 * (1 - ease_out((t - t0) / 0.25)) if c.get("hit") else 0)

        lines = [(runs(c["text"]), font(100 if title else self.L["cap_size"], "Bold" if title else "Demi Bold"), tracking)]
        if title and c.get("sub"):
            lines.append((runs(c["sub"]), font(24, "Medium"), 8 + held * 3))
        imgs = [line_image(ch, f, tr, 8 if title else 5) for ch, f, tr in lines]
        if scale != 1.0:
            imgs[0] = imgs[0].resize((int(imgs[0].width * scale), int(imgs[0].height * scale)), Image.LANCZOS)

        y = int(self.H * 0.08) if title else (self.L["cap_y"] or self.H - 150)
        y += int((1 - p_in) * 12)                               # slight rise on entry
        for im in imgs:
            if blur > 0.3:
                im = im.filter(ImageFilter.GaussianBlur(blur))
            if alpha < 1:
                a = im.getchannel("A").point(lambda v: int(v * alpha))
                im.putalpha(a)
            layer.alpha_composite(im, ((self.W - im.width) // 2, y))
            y += im.height - (10 if title else 0)


def tracked_width_chars(chars, f, tracking):
    return sum(f.getlength(c) for c, _ in chars) + tracking * (len(chars) - 1)


# ---- layouts -------------------------------------------------------------------------------------------------
INSET_PIC_W = 1080
INSET_PIC_H = 608                                   # 1080 * 9 / 16, rounded to even
INSET_PIC_Y = (1920 - INSET_PIC_H) // 2             # 656


def layout_for(layout, size):
    """Caption layout dict for an edit.json layout name ("full" | "inset") and reel size."""
    W, H = size
    if layout == "inset":
        y, h = (H - INSET_PIC_H) // 2, INSET_PIC_H
        return dict(cap_size=34, cap_y=y + h + 46, lyric_size=58, lyric_tr=18, lyric_y=y + h // 2,
                    title_y=0.215, title_size=92, title_tr=24, sub_size=19, sub_tr=5)
    return {}                                        # landscape defaults (the approved 006 look)


def caption_width_errors(spec, layout, size):
    """Messages for captions too wide for the frame (make_short.py asserted this for the vertical layout)."""
    W, _ = size
    L = dict(Captions.LAYOUT, **layout)
    out = []
    for i, c in enumerate(spec, 1):
        st = c.get("style")
        if st == "title" or c.get("static"):
            continue
        if st == "lyric":
            f = ImageFont.truetype("/System/Library/Fonts/Optima.ttc", L["lyric_size"], index=1)
            tr = L["lyric_tr"] + 8 * L["lyric_tr"] / 30
            w = (sum(f.getlength(ch) for ch in c["text"].upper()) + tr * (len(c["text"]) - 1)) * 1.11
            limit = W - 40
        else:
            w = tracked_width_chars(runs(c["text"]), font(L["cap_size"], "Demi Bold"), 10)
            limit = W - 60
        if w >= limit:
            out.append(f"caption {i} ({c['text']!r}) is too wide for the frame ({w:.0f}px, limit {limit}px)")
    return out
