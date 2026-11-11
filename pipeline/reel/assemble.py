"""Assemble a music reel from per-shot clips (generalised from episodes/006-jatayu-ravana/make_reel.py + make_short.py).

  run(ep_dir, captions_only=False)

Reads script/edit.json. Cuts each shot's clip to its bar span with exact cumulative frame counts, applies the hero
transitions and grade, then the other transitions, shakes and mask reveals (all in pipeline/reel_fx.py; in the inset
layout that pass also puts each shot on the 1080x1920 canvas), draws animated captions and the end card, and writes
to out/final/:
  reel_SILENT.mp4     the upload master, no audio stream (the song is added in the Instagram app)
  reel_with_song.mp4  preview with the song mixed in
  cover.jpg           cover image (hook + title), kept inside the profile-grid crop
Intermediate files go in out/segments/ (joined.mp4 = graded footage without captions).
captions_only=True redoes only the caption/end-card pass, preview and cover from the existing joined.mp4.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from reel import captions as C
from reel import shots as S

FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
FADE_VIDEO = 0.8


def _run(cmd):
    subprocess.run(cmd, check=True)


def probe_dur(p) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _probe_size(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


# ---- background texture ------------------------------------------------------------------------------------
def make_background(path: Path, size=(1080, 1920), seed=11):
    """Procedural near-black charcoal with fine grain, soft mottling and a gentle vignette."""
    W, H = size
    rng = np.random.default_rng(seed)

    def lowfreq(w, h, amp):
        a = rng.normal(0, 1, (h, w)).astype(np.float32)
        a = (a - a.min()) / (a.max() - a.min()) - 0.5
        return np.asarray(Image.fromarray(((a + 0.5) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),
                          np.float32) / 255 * amp - amp / 2

    base = 40.0 + lowfreq(W // 24, H // 24, 12) + lowfreq(W // 5, H // 5, 8) + rng.normal(0, 3.6, (H, W))
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vign = 1.0 - 0.45 * np.clip(r - 0.3, 0, None) ** 1.5
    lum = np.clip(base * vign, 0, 255)
    rgb = np.stack([lum * 1.0, lum * 1.0, lum * 1.04], axis=-1).clip(0, 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(path)
    return path


# ---- segments ----------------------------------------------------------------------------------------------
def render_segments(ep: Path, E, seg_dir: Path, size, fps):
    SW, SH = size
    bars = E["bars"]
    seg_dir.mkdir(parents=True, exist_ok=True)
    segs = []
    for i, s in enumerate(E["shots"]):                    # index in the name: one clip may be cut into several shots
        dur = bars[s["to_bar"]] - bars[s["from_bar"]]
        clip = ep / s["clip"]
        t_in = s.get("in", 0.0)
        avail = s.get("out", probe_dur(clip)) - t_in      # optional "out" drops a bad clip tail
        speed = min(1.0, avail / dur)                      # <1 = slow down slightly to fill the bars
        out = seg_dir / f"seg{i:02d}_c{s['n']:02d}.mp4"
        # tpad clones the last frame so the exact frame count is always reached
        vf = (f"setpts=PTS/{speed:.5f},scale={SW}:{SH}:force_original_aspect_ratio=increase,crop={SW}:{SH},"
              f"fps={fps},tpad=stop_mode=clone:stop_duration=2")
        # optional "black_tail": seconds of black at the end of the shot (2-frame cut to black), for
        # close-ups separated by darkness on isolated intro hits
        bt = float(s.get("black_tail", 0) or 0)
        if bt > 0:
            vf += f",fade=t=out:st={max(0.0, dur - bt):.3f}:d={2 / fps:.3f}"
        vf += ",format=yuv420p"
        # exact frame count from cumulative frame positions, so rounding never accumulates into drift
        nframes = round(bars[s["to_bar"]] * fps) - round(bars[s["from_bar"]] * fps)
        _run([FFMPEG, "-v", "error", "-y", "-ss", f"{t_in:.3f}", "-i", str(clip), "-an", "-vf", vf,
              "-frames:v", str(nframes), "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(out)])
        print(f"shot {s['n']:2d}: bars {s['from_bar']:2d}-{s['to_bar']:2d} {dur:5.2f}s "
              f"(clip {avail:4.2f}s, speed {speed:.3f})")
        segs.append(out)
    return segs


def join_segments(segs, seg_dir: Path) -> Path:
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in segs))
    joined = seg_dir / "joined.mp4"
    _run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    return joined


# ---- final pass --------------------------------------------------------------------------------------------
def caption_spec(E, total):
    spec = list(E.get("captions", []))
    ec = E.get("end_card")
    if ec:
        spec.append({"text": ec["text"], "sub": ec.get("sub", ""), "static": True,
                     "t0": max(0.0, total - ec.get("hold", 2.5)), "t1": total + 1.0})
    return spec


def compose(ep: Path, E, joined: Path, out_dir: Path, bg: Path | None):
    W, H = E["size"]
    fps = E["fps"]
    layout = E.get("layout", "full")
    total = E["bars"][-1]
    nframes = round(total * fps)
    cap = C.Captions(caption_spec(E, total), E["bars"], (W, H), C.layout_for(layout, (W, H)))
    silent = out_dir / "reel_SILENT.mp4"
    tail = f"fade=out:st={total - FADE_VIDEO:.3f}:d={FADE_VIDEO},format=yuv420p[vout]"
    if layout == "inset" and _probe_size(joined) != (W, H):       # joined.mp4 from before the canvas pass
        fc = (f"[0:v]scale={C.INSET_PIC_W}:{C.INSET_PIC_H}:flags=lanczos[fg];"
              f"[1:v][fg]overlay=0:{C.INSET_PIC_Y}[base];[base][2:v]overlay=0:0:format=auto,{tail}")
        inputs = ["-i", str(joined), "-loop", "1", "-framerate", str(fps), "-i", str(bg)]
    else:
        fc = f"[0:v][1:v]overlay=0:0:format=auto,{tail}"
        inputs = ["-i", str(joined)]
    p = subprocess.Popen([FFMPEG, "-v", "error", "-y", *inputs,
                          "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "pipe:0",
                          "-filter_complex", fc, "-map", "[vout]", "-an", "-frames:v", str(nframes),
                          "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-movflags", "+faststart",
                          str(silent)], stdin=subprocess.PIPE)
    blank = bytes(W * H * 4)
    for i in range(nframes):
        im = cap.frame(i / fps)
        p.stdin.write(blank if im is None else im.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise S.ReelError("ffmpeg failed in the caption/overlay pass")

    preview = out_dir / "reel_with_song.mp4"
    fo = E.get("fade_out", 1.5)
    _run([FFMPEG, "-v", "error", "-y", "-i", str(silent), "-ss", f"{E['song_in']:.3f}", "-t", f"{total:.3f}",
          "-i", str(ep / E["song"]), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af",
          f"afade=in:st=0:d=0.03,afade=out:st={total - fo:.3f}:d={fo}", "-c:a", "aac", "-b:a", "256k",
          "-movflags", "+faststart", str(preview)])
    return silent, preview


# ---- cover -------------------------------------------------------------------------------------------------
def _tw(text, f, tr):
    return sum(f.getlength(c) for c in text) + tr * (len(text) - 1)


def _fit_font(text, want, size, tr, maxw):
    while size > 14 and _tw(text, C.font(size, want), tr) > maxw:
        size -= 2
    return C.font(size, want)


def _cover_art(ep: Path, E, shots_by_n=None) -> Image.Image:
    cv = E.get("cover", {})
    if cv.get("image"):
        return Image.open(ep / cv["image"]).convert("RGB")
    n = cv.get("shot")
    if n is None:
        hero = [t for t in E.get("transitions", []) if t.get("type") == "hero"]
        n = next((s["n"] for s in E["shots"] if hero and s["from_bar"] == hero[0]["bar"]), E["shots"][0]["n"])
    key = ep / f"out/keyframes/s{int(n):02d}.png"
    if key.exists():
        return Image.open(key).convert("RGB")
    shot = next(s for s in E["shots"] if s["n"] == n)
    tmp = ep / "out/segments/cover_frame.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    _run([FFMPEG, "-v", "error", "-y", "-ss", "1.0", "-i", str(ep / shot["clip"]), "-frames:v", "1", str(tmp)])
    return Image.open(tmp).convert("RGB")


def _cover_fit(im, W, H):
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((l, t, l + W, t + H)).convert("RGBA")


def _cover_texts(E):
    cv, ec = E.get("cover", {}), E.get("end_card", {})
    hook = cv.get("hook")
    if hook is None:
        hook = next((c["text"].replace("*", "") for c in E.get("captions", [])
                     if c.get("style") in (None, "hit") and not c.get("static")), "")
    return hook.upper(), (cv.get("title") or ec.get("text", "")).upper(), (cv.get("sub") or ec.get("sub", "")).upper()


def _tracked(draw, cx, y, text, f, fill, tr):
    x = cx - _tw(text, f, tr) / 2
    for c in text:
        draw.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + tr


def make_cover(ep: Path, E, out: Path, bg: Path | None):
    W, H = E["size"]
    hook, title, sub = _cover_texts(E)
    art = _cover_art(ep, E)
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd, td = ImageDraw.Draw(halo), ImageDraw.Draw(txt)
    lines = []                              # (text, font, colour, tracking, y)
    if E.get("layout", "full") == "inset":
        im = Image.open(bg).convert("RGBA")
        im.alpha_composite(_cover_fit(art, C.INSET_PIC_W, C.INSET_PIC_H), (0, C.INSET_PIC_Y))
        py, ph = C.INSET_PIC_Y, C.INSET_PIC_H
        # all text stays inside the profile-grid crop (middle 1080x1440: y 240..1680)
        if title:
            lines.append((title, _fit_font(title, "Bold", 132, 26, W - 120), C.GOLD, 26, 380))
        if sub:
            lines.append((sub, _fit_font(sub, "Medium", 26, 7, W - 120), C.WHITE, 7, 560))
        if hook:
            lines.append((hook, _fit_font(hook, "Demi Bold", 40, 8, W - 100), C.WHITE, 8, py + ph + 70))
    else:
        portrait = H > W
        im = _cover_fit(art, W, H)
        if portrait:
            sizes, ys, shade_from = (34, 132, 26), (1415, 1461, 1625), 1250
        else:
            sizes, ys, shade_from = (28, 112, 22), (812, 850, 990), 640
        shade = Image.new("L", (W, H), 0)
        sd = ImageDraw.Draw(shade)
        for y in range(H):
            sd.line([(0, y), (W, y)], fill=int(175 * min(1, max(0, (y - shade_from) / (H - 60 - shade_from)))))
        zero = Image.new("L", (W, H), 0)
        im = Image.alpha_composite(im, Image.merge("RGBA", (zero, zero, zero, shade)))
        gw = 1080 if portrait else 810
        for t, want, sz, tr, col, y in ((hook, "Demi Bold", sizes[0], 8, C.WHITE, ys[0]),
                                        (title, "Bold", sizes[1], 28, C.GOLD, ys[1]),
                                        (sub, "Medium", sizes[2], 7, C.WHITE, ys[2])):
            if t:
                lines.append((t, _fit_font(t, want, sz, tr, gw - 60), col, tr, y))
    for t, f, col, tr, y in lines:
        _tracked(hd, W / 2, y, t, f, (0, 0, 0, 220), tr)
        _tracked(td, W / 2, y, t, f, col + (255,), tr)
    halo = halo.filter(ImageFilter.GaussianBlur(12))
    im = Image.alpha_composite(Image.alpha_composite(Image.alpha_composite(im, halo), halo), txt).convert("RGB")
    im.save(out, quality=95)
    return out


# ---- entry point -------------------------------------------------------------------------------------------
def run(ep_dir, captions_only=False):
    ep = Path(ep_dir).resolve()
    rep = S.validate(ep, strict_clips=not captions_only)
    for m in rep.warnings:
        print("warning:", m)
    if rep.errors:
        raise S.ReelError("cannot assemble:\n  " + "\n  ".join(rep.errors))
    E = S.load_edit(ep)
    cfg = S.load_config()
    W, H = E["size"]
    fps = E["fps"]
    layout = E.get("layout", "full")
    seg_dir = ep / "out/segments"
    out_dir = ep / "out/final"
    out_dir.mkdir(parents=True, exist_ok=True)
    bg = make_background(seg_dir / "bg_inset.png", (W, H)) if layout == "inset" else None

    joined = seg_dir / "joined.mp4"
    if captions_only:
        if not joined.exists():
            raise S.ReelError("--captions needs out/segments/joined.mp4 from a full assemble first")
    else:
        sys.path.insert(0, str(S.PIPE))
        import reel_fx
        size = (W, H) if layout == "full" else (cfg["clip"]["width"], cfg["clip"]["height"])
        segs = render_segments(ep, E, seg_dir, size, fps)
        reel_fx.apply_transitions(E, segs, fps, size)
        reel_fx.apply_grade(E, segs, fps, size)
        # new transitions, shakes and masks. A masked shot fills the whole 1080x1920 screen, so when an inset reel has
        # one, this pass also puts every shot on the canvas (same scale/overlay filter as below); otherwise the
        # segments stay picture-sized and the final pass is exactly as before.
        canvas_pass = layout == "inset" and any(s.get("mask") for s in E["shots"])
        reel_fx.apply_edits(E, segs, fps, size, (W, H), bg if canvas_pass else None)
        joined = join_segments(segs, seg_dir)
    silent, preview = compose(ep, E, joined, out_dir, bg)
    cover = make_cover(ep, E, out_dir / "cover.jpg", bg)
    for p in (silent, preview):
        print(f"{p.relative_to(ep)}  {probe_dur(p):.2f}s")
    print(cover.relative_to(ep))
