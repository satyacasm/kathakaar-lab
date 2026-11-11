"""Load and validate script/shots.json and script/edit.json (rules in pipeline/REEL_PIPELINE.md).

validate(ep_dir, strict_clips=False) -> Report with .errors (block every stage) and .warnings.
Each message names the shot ("shot 3: ...") or the edit.json key it is about, one message per problem.
strict_clips=True (used by assemble) also makes a missing clip file an error; otherwise it is a note
because clips are made by earlier stages.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
STYLES_DIR = Path(__file__).resolve().parent / "styles"

SOURCES = ("local", "hero")
MOTION_TYPES = ("drift", "morph", "step")
CAMERA_MOVES = ("static", "push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down")
EASES = ("linear", "in_out", "out")
FX = ("embers", "sparks", "smoke", "mist", "glow", "rays", "rain", "stars", "flash")
LAYOUTS = ("full", "inset")
# Brand rule: the art style is never named in on-screen text.
STYLE_WORDS = ("watercolor", "watercolour", "water colour", "ink wash", "ghibli", "anime", "ai", "ai-generated",
               "midjourney", "flux", "higgsfield", "seedance", "pattachitra", "patachitra", "madhubani")


class ReelError(Exception):
    """A problem that stops the command; the message is shown as-is."""


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warnings.append(m)

    def note(self, m):
        self.notes.append(m)


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def _load_json(path: Path):
    if not path.exists():
        raise ReelError(f"missing file: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ReelError(f"{path}: invalid JSON ({e})")


def load_shots(ep_dir) -> dict:
    return _load_json(Path(ep_dir) / "script/shots.json")


def load_edit(ep_dir) -> dict:
    return _load_json(Path(ep_dir) / "script/edit.json")


def style_names() -> list[str]:
    if not STYLES_DIR.exists():
        return []
    return sorted(p.stem for p in STYLES_DIR.glob("*.txt") if not p.stem.endswith(".avoid"))


def shot_by_n(shots: dict) -> dict:
    return {s.get("n"): s for s in shots.get("shots", [])}


def hero_cost(shot: dict, cfg: dict):
    """Estimated credits for a hero shot, or None if the model/resolution has no rate."""
    h = shot.get("hero") or {}
    rate = cfg["hero_rate"].get(h.get("model"), {}).get(h.get("resolution"))
    if rate is None or not isinstance(h.get("duration"), (int, float)):
        return None
    return rate * h["duration"]


def clip_path(ep_dir, n) -> Path:
    return Path(ep_dir) / f"out/clips/c{int(n):02d}.mp4"


def _check_shots(ep, shots, cfg, r: Report):
    styles = style_names()
    st = shots.get("style")
    if not st:
        r.err("shots.json: 'style' is missing")
    elif styles and st not in styles:
        r.err(f"shots.json: unknown style {st!r} (known: {', '.join(styles)})")
    chars = shots.get("characters", {})
    for cid, c in chars.items():
        if not c.get("desc"):
            r.err(f"character {cid}: 'desc' is missing")
        if not c.get("ref"):
            r.err(f"character {cid}: 'ref' is missing")
        elif not (ep / c["ref"]).exists():
            r.err(f"character {cid}: reference image {c['ref']} does not exist")
    lst = shots.get("shots")
    if not isinstance(lst, list) or not lst:
        r.err("shots.json: 'shots' must be a non-empty list")
        return
    seen = set()
    for s in lst:
        n = s.get("n")
        tag = f"shot {n}"
        if not isinstance(n, int) or n < 1:
            r.err(f"{tag}: 'n' must be a positive integer")
            continue
        if n in seen:
            r.err(f"{tag}: duplicate shot number")
        seen.add(n)
        if not s.get("prompt"):
            r.err(f"{tag}: 'prompt' is missing")
        if not isinstance(s.get("seed"), int):
            r.err(f"{tag}: 'seed' must be an integer")
        for cid in s.get("characters", []):
            if cid not in chars:
                r.err(f"{tag}: unknown character {cid!r}")
        poses = s.get("poses", [])
        pids = [p.get("id") for p in poses]
        if len(set(pids)) != len(pids):
            r.err(f"{tag}: duplicate pose ids")
        for p in poses:
            if not p.get("id") or not p.get("edit"):
                r.err(f"{tag}: every pose needs 'id' and 'edit'")
        src = s.get("source")
        if src not in SOURCES:
            r.err(f"{tag}: unknown source {src!r} (use {' or '.join(SOURCES)})")
            continue
        for fx in s.get("fx", []):
            if fx not in FX:
                r.err(f"{tag}: unknown fx {fx!r} (known: {', '.join(FX)})")
        m = s.get("motion")
        if src == "local":
            if not m:
                r.err(f"{tag}: local shot needs 'motion'")
            else:
                mt = m.get("type")
                if mt not in MOTION_TYPES:
                    r.err(f"{tag}: unknown motion.type {mt!r} (known: {', '.join(MOTION_TYPES)})")
                elif mt in ("morph", "step") and not poses:
                    r.err(f"{tag}: motion.type {mt!r} needs at least one pose")
                cam = m.get("camera", {"move": "static"})
                if cam.get("move") not in CAMERA_MOVES:
                    r.err(f"{tag}: unknown camera.move {cam.get('move')!r} (known: {', '.join(CAMERA_MOVES)})")
                if cam.get("ease", "linear") not in EASES:
                    r.err(f"{tag}: unknown camera.ease {cam.get('ease')!r} (known: {', '.join(EASES)})")
                amt = cam.get("amount", 0)
                if not isinstance(amt, (int, float)) or amt < 0:
                    r.err(f"{tag}: camera.amount must be a number >= 0")
                elif amt > 0.08:
                    r.warn(f"{tag}: camera.amount {amt} is above 0.08 (edges may show)")
                par = m.get("parallax", 0)
                if not isinstance(par, (int, float)) or not 0 <= par <= 1:
                    r.err(f"{tag}: parallax must be between 0 and 1")
            if s.get("hero"):
                r.warn(f"{tag}: has a 'hero' block but source is local (ignored)")
            if "sky_title" in s:
                _check_sky_title(s["sky_title"], tag, r)
        else:
            if "sky_title" in s:
                r.err(f"{tag}: sky_title works only on local shots (it is drawn by the motion stage)")
            h = s.get("hero")
            if not h:
                r.err(f"{tag}: hero shot needs a 'hero' block")
                continue
            model, res = h.get("model"), h.get("resolution")
            if model not in cfg["hero_rate"]:
                r.err(f"{tag}: unknown hero.model {model!r} (known: {', '.join(cfg['hero_rate'])})")
            elif res not in cfg["hero_rate"][model]:
                r.err(f"{tag}: hero.resolution {res!r} not priced for {model} (known: "
                      f"{', '.join(cfg['hero_rate'][model])})")
            if not isinstance(h.get("duration"), (int, float)) or h["duration"] <= 0:
                r.err(f"{tag}: hero.duration must be a positive number of seconds")
            if not h.get("prompt"):
                r.err(f"{tag}: hero.prompt is missing")
            if h.get("end_pose") and h["end_pose"] not in pids:
                r.err(f"{tag}: hero.end_pose {h['end_pose']!r} is not one of this shot's poses")


def _check_sky_title(st, tag, r: Report):
    """shots.json sky_title (see pipeline/reel/skytitle.py for the keys and defaults)."""
    from reel import skytitle
    tag = f"{tag}: sky_title"
    if not isinstance(st, dict):
        r.err(f"{tag} must be an object")
        return
    for k in st:
        if k not in skytitle.KEYS:
            r.err(f"{tag}: unknown key {k!r} (known: {', '.join(sorted(skytitle.KEYS))})")
    text = st.get("text")
    if not isinstance(text, str) or not text.strip():
        r.err(f"{tag}: 'text' must be a non-empty string")
        text = ""
    elif not all(c.isascii() or c in "·–—’" for c in text):
        r.err(f"{tag}: 'text' is drawn in Latin capitals (Avenir Next); put Devanagari in 'sub'")
    sub = st.get("sub", [])
    if not (isinstance(sub, str) or (isinstance(sub, list) and all(isinstance(x, str) for x in sub))):
        r.err(f"{tag}: 'sub' must be a string (newlines split lines) or a list of strings")
        sub = []
    lines = skytitle.sub_lines({"sub": sub})
    for ln in lines:
        other = [c for c in ln if not (c.isascii() or skytitle.is_devanagari(c) or c in "·–—’‘“”")]
        if other:
            r.err(f"{tag}: sub line {ln!r} has characters outside Latin and Devanagari ({''.join(other)!r})")
        if skytitle.is_devanagari(ln) and any(c.isalpha() and c.isascii() for c in ln):
            r.err(f"{tag}: sub line {ln!r} mixes Latin and Devanagari letters (use one script per line)")
    if any(skytitle.is_devanagari(ln) for ln in lines):
        from reel import shape_text
        if not shape_text.shaping_available():
            r.err(f"{tag}: Devanagari needs text shaping, but Pillow cannot load libraqm "
                  f"(brew install libraqm); refusing to draw unshaped Devanagari")
    for w in _bad_words(text + " " + " ".join(lines)):
        r.err(f"{tag}: on-screen text names the art style or tooling ({w!r})")
    for k, (lo, hi) in skytitle.RANGES.items():
        v = st.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi):
            r.err(f"{tag}: {k} must be a number from {lo} to {hi}, got {v!r}")
    if "occlude" in st and not isinstance(st["occlude"], bool):
        r.err(f"{tag}: occlude must be true or false")


def _bad_words(text):
    low = text.lower()
    return [w for w in STYLE_WORDS if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low)]


def _check_edit(ep, shots, edit, cfg, r: Report, strict_clips):
    bars = edit.get("bars")
    if not isinstance(bars, list) or len(bars) < 2 or any(b2 <= b1 for b1, b2 in zip(bars, bars[1:])) or bars[0] != 0:
        r.err("edit.json: 'bars' must start at 0 and strictly increase")
        return
    nb = len(bars) - 1
    size, fps = edit.get("size"), edit.get("fps")
    if not (isinstance(size, list) and len(size) == 2):
        r.err("edit.json: 'size' must be [width, height]")
        return
    if not isinstance(fps, (int, float)) or fps <= 0:
        r.err("edit.json: 'fps' must be a positive number")
    layout = edit.get("layout", "full")
    if layout not in LAYOUTS:
        r.err(f"edit.json: unknown layout {layout!r} (use {' or '.join(LAYOUTS)})")
    elif layout == "inset" and size != [1080, 1920]:
        r.err(f"edit.json: layout 'inset' needs size [1080, 1920], got {size}")
    # song
    song = edit.get("song")
    if not song:
        r.err("edit.json: 'song' is missing")
    elif not (ep / song).exists():
        r.err(f"edit.json: song file {song} does not exist")
    si, so = edit.get("song_in"), edit.get("song_out")
    if not isinstance(si, (int, float)):
        r.err("edit.json: 'song_in' must be a number")
    elif isinstance(so, (int, float)) and so - si < bars[-1] - 0.01:
        r.warn(f"edit.json: song_out - song_in ({so - si:.2f}s) is shorter than the reel ({bars[-1]:.2f}s)")
    if not isinstance(edit.get("fade_out", 0), (int, float)):
        r.err("edit.json: 'fade_out' must be a number")
    # shots
    by_n = shot_by_n(shots)
    es = edit.get("shots", [])
    if not es:
        r.err("edit.json: 'shots' is empty")
    prev_to, used = 0, set()
    for e in es:
        n = e.get("n")
        tag = f"shot {n}"
        if n not in by_n:
            r.err(f"{tag}: in edit.json but not in shots.json")
        used.add(n)
        fb, tb = e.get("from_bar"), e.get("to_bar")
        if not (isinstance(fb, int) and isinstance(tb, int) and 0 <= fb < tb <= nb):
            r.err(f"{tag}: from_bar/to_bar must be integers with 0 <= from_bar < to_bar <= {nb}")
            continue
        if fb != prev_to:
            r.err(f"{tag}: starts at bar {fb} but the previous shot ends at bar {prev_to} (shots must be contiguous)")
        prev_to = tb
        if not e.get("clip"):
            r.err(f"{tag}: 'clip' is missing in edit.json")
            continue
        cp = ep / e["clip"]
        if not cp.exists():
            src = by_n.get(n, {}).get("source")
            hero_pending = src == "hero" and not (ep / f"out/hero_raw/c{int(n):02d}.mp4").exists()
            why = " (hero clip not bought yet)" if hero_pending else ""
            (r.err if strict_clips else r.note)(f"{tag}: clip {e['clip']} does not exist{why}")
        if not isinstance(e.get("in", 0), (int, float)) or e.get("in", 0) < 0:
            r.err(f"{tag}: 'in' must be a number >= 0")
    if es and prev_to != nb:
        r.err(f"edit.json: shots end at bar {prev_to} but bars end at {nb} (the reel must cover every bar)")
    for n in by_n:
        if n not in used:
            r.warn(f"shot {n}: in shots.json but not used in edit.json")
    # captions
    for i, c in enumerate(edit.get("captions", []), 1):
        tag = f"caption {i}"
        if not c.get("text"):
            r.err(f"{tag}: 'text' is missing")
            continue
        if "t0" in c:
            if not (isinstance(c.get("t1"), (int, float)) and c["t0"] < c["t1"]):
                r.err(f"{tag}: t0/t1 must be numbers with t0 < t1")
        elif not (isinstance(c.get("b0"), int) and isinstance(c.get("b1"), int) and 0 <= c["b0"] <= c["b1"] <= nb):
            r.err(f"{tag}: b0/b1 must be bar indices with 0 <= b0 <= b1 <= {nb}")
        for w in _bad_words(c["text"] + " " + c.get("sub", "")):
            r.err(f"{tag}: on-screen text names the art style or tooling ({w!r})")
    ec = edit.get("end_card")
    if ec is not None:
        if not ec.get("text"):
            r.err("edit.json: end_card.text is missing")
        else:
            for w in _bad_words(ec["text"] + " " + ec.get("sub", "")):
                r.err(f"edit.json: end_card text names the art style or tooling ({w!r})")
        hold = ec.get("hold", 2.5)
        if not isinstance(hold, (int, float)) or hold <= 0:
            r.err("edit.json: end_card.hold must be a positive number")
        elif es and es[-1].get("from_bar") is not None and es[-1].get("to_bar") is not None:
            last = bars[es[-1]["to_bar"]] - bars[es[-1]["from_bar"]]
            if hold > last + 0.01:
                r.warn(f"edit.json: end_card.hold ({hold}s) is longer than the last shot ({last:.2f}s)")
    # sky titles must be settled and readable for the last second (or more) of their shot
    from reel import skytitle
    for e in es:
        st = by_n.get(e.get("n"), {}).get("sky_title")
        fb, tb = e.get("from_bar"), e.get("to_bar")
        if not isinstance(st, dict) or not (isinstance(fb, int) and isinstance(tb, int) and 0 <= fb < tb <= nb):
            continue
        try:
            tm = skytitle.timing(st)
        except (TypeError, ValueError):
            continue
        on = bars[tb] - bars[fb] - float(e.get("in", 0) or 0)
        if on - tm["all"] < 1.0:
            r.warn(f"shot {e['n']}: sky_title is fully settled at {tm['all']:.2f}s but the shot is on screen for "
                   f"{on:.2f}s (want at least 1 s settled; start earlier or rise faster)")
    # masks (per shot) and transitions
    _check_masks_and_transitions(edit, es, bars, r)
    g = edit.get("grade")
    if g:
        if g.get("type") != "hero":
            r.err(f"edit.json: unknown grade type {g.get('type')!r} (only 'hero')")
        for k in ("from_bar", "letterbox_out_bar"):
            if g.get(k) is not None and not (isinstance(g[k], int) and 0 <= g[k] <= nb):
                r.err(f"edit.json: grade.{k} must be a bar index between 0 and {nb}")
        if not isinstance(g.get("from_bar"), int):
            r.err("edit.json: grade.from_bar is required")
    # caption widths (needs Pillow; skipped quietly if layout is unusable)
    if not r.errors:
        try:
            from reel import captions as cap
            for m in cap.caption_width_errors(edit.get("captions", []), cap.layout_for(layout, tuple(size)),
                                              tuple(size)):
                r.err(m)
        except ImportError:
            r.warn("caption width check skipped (Pillow not available)")


TRANSITION_TYPES = ("hero", "whip", "slash", "glitch", "zoom", "flash", "shake")
TRANSITION_KEYS = {"type", "bar", "t", "pre", "post", "strength", "note", "dir", "color", "angle", "edge", "seed",
                   "cx", "cy"}


def _check_masks_and_transitions(edit, es, bars, r: Report):
    from reel import masks
    nb = len(bars) - 1
    for e in es:
        if "mask" in e:
            for m in masks.check(e["mask"], f"shot {e.get('n')}"):
                r.err(m)
    masked = {e.get("from_bar") for e in es if e.get("mask")}
    tails = {e.get("to_bar") for e in es if (e.get("black_tail") or 0) > 0}
    mask_out = {e.get("to_bar") for e in es if e.get("mask")}
    cut_bars = {}
    for i, t in enumerate(edit.get("transitions", []), 1):
        typ = t.get("type")
        b = t.get("bar")
        tag = f"transition {i} ({typ} at bar {b})" if "bar" in t else f"transition {i} ({typ} at t={t.get('t')})"
        if typ not in TRANSITION_TYPES:
            r.err(f"{tag}: unknown transition type {typ!r} (known: {', '.join(TRANSITION_TYPES)})")
            continue
        for k in t:
            if k not in TRANSITION_KEYS:
                r.err(f"{tag}: unknown key {k!r}")
        for k, lo, hi in (("strength", 0.05, 3.0), ("pre", 0.0, 1.5), ("post", 0.0, 1.5)):
            v = t.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi):
                r.err(f"{tag}: {k} must be a number from {lo} to {hi}, got {v!r}")
        if typ == "shake":
            if ("bar" in t) == ("t" in t):
                r.err(f"{tag}: shake needs exactly one of 'bar' (index into bars) or 't' (seconds)")
            elif "bar" in t and not (isinstance(b, int) and 0 <= b < nb):
                r.err(f"{tag}: bar must be an integer from 0 to {nb - 1}")
            elif "t" in t and not (isinstance(t["t"], (int, float)) and 0 <= t["t"] < bars[-1]):
                r.err(f"{tag}: t must be seconds from 0 to {bars[-1]}")
        else:
            if "t" in t:
                r.err(f"{tag}: only 'shake' takes 't'; cut transitions are placed with 'bar'")
            if not (isinstance(b, int) and any(e.get("to_bar") == b for e in es)
                    and any(e.get("from_bar") == b for e in es)):
                r.err(f"{tag}: needs one shot ending and one starting at bar {b} (a cut)")
                continue
            if b in cut_bars:
                r.err(f"{tag}: bar {b} already has a {cut_bars[b]} transition (one cut transition per bar; "
                      f"'shake' may be added on top)")
            cut_bars[b] = typ
            if typ != "hero":
                if b in masked or (b in mask_out and typ != "flash"):
                    r.warn(f"{tag}: touches a masked shot, so it is ignored (masks have their own open/close)")
                elif b in tails and t.get("pre", 1) and typ != "flash":
                    r.note(f"{tag}: the outgoing shot ends in black_tail, so only the incoming half plays")
        if typ == "whip" and t.get("dir", "left") not in ("left", "right", "up", "down"):
            r.err(f"{tag}: dir must be left, right, up or down, got {t.get('dir')!r}")
        if typ == "slash":
            if t.get("dir", "right") not in ("left", "right"):
                r.err(f"{tag}: dir must be left or right, got {t.get('dir')!r}")
            a = t.get("angle", 22)
            if isinstance(a, bool) or not isinstance(a, (int, float)) or not -45 <= a <= 45:
                r.err(f"{tag}: angle must be a number from -45 to 45 (lean from vertical), got {a!r}")
            if t.get("edge", "gold") not in ("gold", "white"):
                r.err(f"{tag}: edge must be gold or white, got {t.get('edge')!r}")
        if typ == "flash":
            c = t.get("color", "white")
            ok = c in ("white", "gold", "red") or (isinstance(c, list) and len(c) == 3 and
                                                   all(isinstance(v, int) and 0 <= v <= 255 for v in c))
            if not ok:
                r.err(f"{tag}: color must be white, gold, red or [r, g, b], got {c!r}")
        if typ == "zoom":
            for k in ("cx", "cy"):
                v = t.get(k, 0.5)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
                    r.err(f"{tag}: {k} must be between 0 and 1")
        if typ == "hero":
            for k in ("dir", "color", "angle", "edge", "cx", "cy"):
                if k in t:
                    r.err(f"{tag}: key {k!r} does not apply to hero")


def validate(ep_dir, strict_clips=False) -> Report:
    """Validate both files; raises ReelError only if a file is missing or not JSON."""
    ep = Path(ep_dir)
    r = Report()
    cfg = load_config()
    shots = load_shots(ep)
    edit = load_edit(ep)
    _check_shots(ep, shots, cfg, r)
    _check_edit(ep, shots, edit, cfg, r, strict_clips)
    return r
