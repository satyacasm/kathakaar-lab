"""Render lines of text with complex-script shaping (HarfBuzz through libraqm) to 8-bit alpha PNGs.

Devanagari needs shaping (conjuncts such as ङ्ग क्ष त्र, the short-i sign drawn left of its consonant). Pillow does
this only when it can load libraqm. The pip wheel of Pillow looks for libraqm through the dynamic loader, and on
this Mac it lives in Homebrew's lib folder, so this module is run as a subprocess with DYLD_LIBRARY_PATH set
(`render_lines` does that). It refuses to draw (exit 3) if raqm still is not available, so unshaped Devanagari can
never be produced silently.

stdin: JSON list of {"text", "font", "index", "size", "out"}; stdout: JSON list of
{"w", "h", "baseline", "body"} (body = height from the top of the headline / capitals to the baseline).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BREW_LIB = "/opt/homebrew/lib"
PAD = 4


def _main():
    from PIL import Image, ImageDraw, ImageFont, features
    if not features.check("raqm"):
        print("shape_text: Pillow cannot load libraqm (needed to shape Devanagari); install it with "
              "`brew install libraqm`", file=sys.stderr)
        sys.exit(3)
    out = []
    for it in json.load(sys.stdin):
        f = ImageFont.truetype(it["font"], int(it["size"]), index=int(it.get("index", 0)),
                               layout_engine=ImageFont.Layout.RAQM)
        asc, desc = f.getmetrics()
        x0, y0, x1, y1 = f.getbbox(it["text"], anchor="ls")
        ref = "क" if any("ऀ" <= c <= "ॿ" for c in it["text"]) else "H"
        body = -f.getbbox(ref, anchor="ls")[1]
        top = min(y0, -asc)
        w = int(x1 - min(0, x0)) + 2 * PAD
        h = int(max(y1, desc) - top) + 2 * PAD
        im = Image.new("L", (w, h), 0)
        base = PAD - top
        ImageDraw.Draw(im).text((PAD - min(0, x0), base), it["text"], font=f, fill=255, anchor="ls")
        im.save(it["out"])
        out.append({"w": w, "h": h, "baseline": base, "body": body})
    json.dump(out, sys.stdout)


def render_lines(items: list[dict]):
    """items: {"text", "font", "index", "size"}. Returns [(alpha float32 HxW, baseline_y, body_height)]."""
    import numpy as np
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        req = [dict(it, out=str(Path(td) / f"l{k}.png")) for k, it in enumerate(items)]
        env = dict(os.environ)
        env["DYLD_LIBRARY_PATH"] = BREW_LIB + (":" + env["DYLD_LIBRARY_PATH"] if env.get("DYLD_LIBRARY_PATH") else "")
        r = subprocess.run([sys.executable, str(Path(__file__).resolve())], input=json.dumps(req), env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"shape_text failed ({r.returncode})")
        meta = json.loads(r.stdout)
        return [(np.asarray(Image.open(q["out"]), np.float32) / 255.0, m["baseline"], m["body"])
                for q, m in zip(req, meta)]


def shaping_available() -> bool:
    env = dict(os.environ, DYLD_LIBRARY_PATH=BREW_LIB)
    r = subprocess.run([sys.executable, "-c", "from PIL import features; import sys; sys.exit(0 if features.check('raqm') else 1)"],
                       env=env, capture_output=True)
    return r.returncode == 0


if __name__ == "__main__":
    _main()
