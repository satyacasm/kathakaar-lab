#!/usr/bin/env python3
"""Per-video feature tags for the Kathakaar channel. Standard library only.

Phase 2 of the feedback loop: describe every published video with a small, CONSISTENT set of tags so Phase 3 can
correlate them with the performance numbers that analytics.py collects. Consistency matters more than richness, so
judged tags come from the closed vocabulary in pipeline/features_vocab.json and are validated on write.

  auto [--video ID]           compute the machine tags from the analytics DB + episode files (title language/length/
                              hashtags/emoji, publish hour and weekday in IST, series part, format/kind, narration,
                              song, look, resolution, shot count and mean shot length, Higgsfield credits). Unknown
                              is null, never a guess. Rewrites only the "auto" block of each video.
  context VIDEO_ID            compact pack for judging: title, description excerpt, script opening, first 3 shot
                              prompts, song, thumbnail path (downloaded to cache/analytics/thumbs/ if missing).
                              View the thumbnail image before tagging.
  set VIDEO_ID f=v [f=v ...] [--override]
                              validate against the vocabulary and write "judged" (default; stamps judged_by and
                              judged_at) or "overrides" (--override; wins over judged and auto, set by a human).
  todo                        videos that still lack any vocabulary field in judged/overrides.
  table [--csv PATH] [--no-csv]
                              one row per tagged video: effective tags (overrides > judged > auto) + latest
                              metrics + per-1k-view rates. Narrow on the terminal; the CSV (default
                              cache/analytics/features_table.csv) has every column.

Storage: episodes/<slug>/analytics/features.json = {video_id: {"auto": {...}, "judged": {...}, "judged_by": "claude",
"judged_at": ISO, "overrides": {...}}}. `auto` rewrites only "auto"; "overrides" is never touched by any command
except `set --override`. Only videos mapped to an episode are tagged (the private test upload is skipped).

Metrics: views are the Data API's latest count; avg_view_pct, avg_view_duration, engaged_views, shares, subs_gained,
likes, comments come from the latest snapshot with an_has_data = 1 (its bucket is reported). Rates per 1k views are
those Analytics counts divided by that same snapshot's an_views, so numerator and denominator share one time window.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
DB = LAB / "cache/analytics/analytics.sqlite"
THUMBS = LAB / "cache/analytics/thumbs"
VOCAB = LAB / "pipeline/features_vocab.json"
CSV_DEFAULT = LAB / "cache/analytics/features_table.csv"
EPISODES = LAB / "episodes"
IST = timezone(timedelta(hours=5, minutes=30))
FPS = 30  # Remotion timeline frame rate used by shots.json (frame ranges)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------------------------------------------------------------- helpers
def load_vocab() -> dict:
    return json.loads(VOCAB.read_text())["fields"]


def jload(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def db() -> sqlite3.Connection:
    if not DB.exists():
        sys.exit(f"no analytics DB at {DB}; run pipeline/analytics.py pull first")
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def tagged_videos(con: sqlite3.Connection, only: str | None = None) -> list[sqlite3.Row]:
    q = "SELECT * FROM videos WHERE episode_slug IS NOT NULL AND episode_slug != ''"
    args: tuple = ()
    if only:
        q += " AND video_id = ?"
        args = (only,)
    return con.execute(q + " ORDER BY published_at", args).fetchall()


def features_path(slug: str) -> Path:
    return EPISODES / slug / "analytics" / "features.json"


def load_features(slug: str) -> dict:
    return jload(features_path(slug)) or {}


def save_features(slug: str, data: dict) -> None:
    p = features_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def episode_info(slug: str) -> dict:
    return jload(EPISODES / slug / "episode.json") or {}


# ---------------------------------------------------------------- auto tags
def is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F300 or 0x2600 <= o <= 0x27BF or o in (0x2B50, 0x2B06, 0x2B55, 0x2B1B, 0x2B1C)


def title_core(title: str) -> str:
    return re.sub(r"#\S+", "", title).strip()


def devanagari_share(text: str) -> float | None:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    return sum(1 for c in letters if "ऀ" <= c <= "ॿ") / len(letters)


def series_part(title: str, info: dict) -> int | None:
    m = re.search(r"(?:भाग|Part)\s*(\d+)", title, re.I)
    if m:
        return int(m.group(1))
    return info.get("part") if isinstance(info.get("part"), int) else None


def episode_cut(slug: str, part: int | None, duration_s: int | None, is_short: bool) -> str | None:
    """005 Shorts are cuts of the long video: cuts/chNN whose timing total matches the Short's duration."""
    if not is_short or part is None or duration_s is None:
        return None
    t = jload(EPISODES / slug / "cuts" / f"ch{part:02d}" / "timing.json")
    if t and abs(float(t.get("total", 0)) - duration_s) <= 2.5:
        return f"ch{part:02d}"
    return None


def shot_stats(slug: str, cut: str | None) -> tuple[int | None, float | None]:
    root = EPISODES / slug
    edit = jload(root / "script" / "edit.json")
    if edit and edit.get("shots") and "song_in" in edit and "song_out" in edit:
        n = len(edit["shots"])
        return n, round((edit["song_out"] - edit["song_in"]) / n, 2)
    for p in (root / "shots.json", root / "script" / "shots.json"):
        d = jload(p)
        if d and d.get("shots") and all("a" in s and "b" in s for s in d["shots"]):
            sh = d["shots"]
            n = len(sh)
            return n, round((sh[-1]["b"] - sh[0]["a"]) / FPS / n, 2)
    return None, None


def auto_tags(v: sqlite3.Row) -> dict:
    title = v["title"] or ""
    desc = v["description"] or ""
    slug = v["episode_slug"]
    info = episode_info(slug)
    core = title_core(title)
    share = devanagari_share(core)
    lang = None if share is None else ("hi" if share >= 0.8 else "en" if share <= 0.2 else "mixed")
    numbers_text = re.sub(r"(?:भाग|Part)\s*\d+", "", core, flags=re.I)
    pub = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")).astimezone(IST)
    tags: list[str] = []
    for h in re.findall(r"#[\wऀ-ॿ]+", title + " " + desc):
        if h.lower() not in [t.lower() for t in tags]:
            tags.append(h)
    part = series_part(title, info)
    is_short = bool(v["is_short"])
    cut = episode_cut(slug, part, v["duration_s"], is_short)
    n_shots, mean_len = shot_stats(slug, cut)
    song = info.get("song") if isinstance(info.get("song"), dict) else None
    hf = info.get("higgsfield") if isinstance(info.get("higgsfield"), dict) else {}
    credits = hf.get("credits_spent", info.get("higgsfield_credits_spent"))
    edit = jload(EPISODES / slug / "script" / "edit.json") or {}
    res = info.get("resolution")
    if not res and isinstance(edit.get("size"), list) and len(edit["size"]) == 2:
        res = f"{edit['size'][0]}x{edit['size'][1]}"
    aspect = None
    if res and "x" in res:
        w, h = (int(x) for x in res.split("x"))
        aspect = "9:16" if h > w else "16:9" if w > h else "1:1"
    narration = info.get("narration")
    if narration is None and (EPISODES / slug / "voice").is_dir():
        narration = True  # narrated episodes keep their voice takes in voice/
    style = info.get("look") or (jload(EPISODES / slug / "script" / "shots.json") or {}).get("style")
    return {
        "title_lang": lang,
        "title_has_number": bool(re.search(r"[0-9०-९]", numbers_text)),
        "title_is_question": "?" in core or "？" in core,
        "title_emoji_count": sum(1 for c in core if is_emoji(c)),
        "title_len_chars": len(title),
        "hashtags": tags,
        "duration_s": v["duration_s"],
        "is_short": is_short,
        "publish_hour_ist": pub.hour,
        "publish_weekday_ist": WEEKDAYS[pub.weekday()],
        "series_part": part,
        "episode_slug": slug,
        "episode_cut": cut,
        "format": info.get("format"),
        "kind": info.get("kind"),
        "narration": narration,
        "song_title": (song or {}).get("title") or None,
        "song_artist": (song or {}).get("artist") or None,
        "look": style,
        "resolution": res,
        "aspect": aspect,
        "shot_count": n_shots,
        "mean_shot_len_s": mean_len,
        "higgsfield_credits": credits,  # episode-level spend, shared by every video cut from the episode
    }


def cmd_auto(a) -> None:
    con = db()
    rows = tagged_videos(con, a.video)
    if a.video and not rows:
        sys.exit(f"{a.video}: not a tagged video (unknown id, or not mapped to an episode)")
    by_slug: dict[str, dict] = {}
    for v in rows:
        slug = v["episode_slug"]
        data = by_slug.setdefault(slug, load_features(slug))
        entry = data.setdefault(v["video_id"], {})
        entry["auto"] = auto_tags(v)
        entry.setdefault("overrides", {})
        print(f"auto  {v['video_id']}  {slug}  {len(entry['auto'])} fields")
    for slug, data in by_slug.items():
        save_features(slug, data)


# ---------------------------------------------------------------- context
def fetch_thumb(vid: str) -> Path | None:
    THUMBS.mkdir(parents=True, exist_ok=True)
    dest = THUMBS / f"{vid}.jpg"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    for name in ("maxresdefault", "hqdefault"):
        try:
            req = urllib.request.Request(f"https://i.ytimg.com/vi/{vid}/{name}.jpg", headers={"User-Agent": "kathakaar-features"})
            with urllib.request.urlopen(req, timeout=20) as r:
                dest.write_bytes(r.read())
            return dest
        except (urllib.error.URLError, OSError):
            continue
    return None


def numbered_lines(path: Path, n: int) -> list[str]:
    out = []
    for ln in path.read_text().splitlines():
        if re.match(r"\s*\d+[.)]\s+\S", ln):
            out.append(ln.strip())
        if len(out) >= n:
            break
    return out


def script_opening(slug: str, cut: str | None, part: int | None, is_short: bool, n: int = 6) -> list[str]:
    root = EPISODES / slug
    out: list[str] = []
    lines = jload(root / "script" / "lines.json") or {}
    if lines.get("hi") and (cut or not is_short):
        idx = (lines.get("chapters") or {}).get(str(part if cut else 1)) or list(range(1, n + 1))
        for lang in ("hi", "en"):
            seq = lines.get(lang) or []
            out.append(f"[{lang}] " + " / ".join(seq[i - 1] for i in idx[:n] if 0 < i <= len(seq)))
        return out
    for name in ("SCRIPT_HI.md", "SCRIPT.md"):
        p = root / "script" / name
        if p.exists():
            ls = numbered_lines(p, n)
            if ls:
                out.append(f"[{name}] " + " / ".join(ls))
    if out:
        return out
    bs = root / "script" / "BEATSHEET.md"
    if bs.exists():
        rows = [ln for ln in bs.read_text().splitlines() if re.match(r"\|\s*[1-3]\s*\|", ln)]
        out.append("[BEATSHEET first rows] " + " // ".join(r[:230] for r in rows[:3]))
    return out


def shot_prompts(slug: str, n: int = 3) -> list[str]:
    root = EPISODES / slug
    for p in (root / "script" / "shots.json", root / "shots.json"):
        d = jload(p)
        if d and d.get("shots") and "prompt" in d["shots"][0]:
            return [s["prompt"][:400] for s in d["shots"][:n]]
    return []


def cmd_context(a) -> None:
    con = db()
    v = next(iter(tagged_videos(con, a.video_id)), None)
    if not v:
        sys.exit(f"{a.video_id}: not a tagged video")
    slug = v["episode_slug"]
    auto = auto_tags(v)
    info = episode_info(slug)
    print(f"video   {v['video_id']}  ({slug}; short={auto['is_short']}; {v['duration_s']}s; part={auto['series_part']}; cut={auto['episode_cut']})")
    print(f"title   {v['title']}")
    d = (v["description"] or "").strip().replace("\n", " | ")
    print(f"desc    {d[:500] or '(none stored)'}")
    for ln in script_opening(slug, auto["episode_cut"], auto["series_part"], auto["is_short"]) or ["(no script found)"]:
        print(f"script  {ln}")
    prompts = shot_prompts(slug)
    for i, p in enumerate(prompts, 1):
        print(f"shot{i}   {p}")
    if not prompts:
        print("shots   (no stored shot prompts for this episode)")
    song = info.get("song") if isinstance(info.get("song"), dict) else None
    print(f"song    {song.get('title')} / {song.get('artist')}" if song and song.get("title") else "song    none recorded")
    th = fetch_thumb(v["video_id"])
    print(f"thumb   {th or 'download failed'}")
    cur = load_features(slug).get(v["video_id"], {})
    if cur.get("judged"):
        print(f"judged  {json.dumps(cur['judged'], ensure_ascii=False)}")


# ---------------------------------------------------------------- set / todo
def validate(vocab: dict, field: str, value: str) -> str:
    if field not in vocab:
        sys.exit(f"unknown field '{field}'. Allowed fields: {', '.join(vocab)}")
    spec = vocab[field]
    if spec.get("free_text"):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", value):
            sys.exit(f"{field}: must be one lowercase single name (letters/digits/-/_), got '{value}'")
        return value
    if value not in spec["values"]:
        sys.exit(f"{field}: '{value}' is not allowed. Allowed: {' | '.join(spec['values'])}")
    return value


def cmd_set(a) -> None:
    vocab = load_vocab()
    pairs: dict[str, str] = {}
    for item in a.pairs:
        if "=" not in item:
            sys.exit(f"expected field=value, got '{item}'")
        k, val = item.split("=", 1)
        pairs[k.strip()] = validate(vocab, k.strip(), val.strip())
    v = next(iter(tagged_videos(db(), a.video_id)), None)
    if not v:
        sys.exit(f"{a.video_id}: not a tagged video")
    slug = v["episode_slug"]
    data = load_features(slug)
    entry = data.setdefault(a.video_id, {})
    entry.setdefault("overrides", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if a.override:
        entry["overrides"].update(pairs)
    else:
        entry.setdefault("judged", {}).update(pairs)
        entry["judged_by"] = "claude"
        entry["judged_at"] = now
    save_features(slug, data)
    print(f"{'override' if a.override else 'judged'}  {a.video_id}  " + " ".join(f"{k}={x}" for k, x in pairs.items()))


def cmd_todo(a) -> None:
    vocab = load_vocab()
    con = db()
    missing_any = False
    for v in tagged_videos(con):
        e = load_features(v["episode_slug"]).get(v["video_id"], {})
        have = set(e.get("judged", {})) | set(e.get("overrides", {}))
        miss = [f for f in vocab if f not in have]
        if miss:
            missing_any = True
            print(f"{v['video_id']}  {v['episode_slug']:<26} missing {len(miss)}: {', '.join(miss)}")
    if not missing_any:
        print("todo: nothing, all videos have every judged field")


# ---------------------------------------------------------------- table
METRICS = ["views", "avg_view_pct", "avg_view_duration_s", "engaged_views", "shares", "subs_gained", "likes", "comments"]


def latest_metrics(con: sqlite3.Connection, v: sqlite3.Row) -> dict:
    s = con.execute(
        "SELECT * FROM snapshots WHERE video_id = ? AND an_has_data = 1 ORDER BY id DESC LIMIT 1", (v["video_id"],)
    ).fetchone()
    m: dict = {"views": v["view_count"], "snapshot_bucket": None, "an_views": None}
    for k in METRICS[1:]:
        m[k] = None
    if s:
        m.update(
            snapshot_bucket=s["bucket"], an_views=s["an_views"], avg_view_pct=s["an_avg_view_pct"],
            avg_view_duration_s=s["an_avg_view_duration"], engaged_views=s["an_engaged_views"], shares=s["an_shares"],
            subs_gained=s["an_subs_gained"], likes=s["an_likes"], comments=s["an_comments"],
        )
    base = m["an_views"]
    for k in ("shares", "subs_gained", "comments"):
        m[f"{k}_per_1k"] = round(m[k] * 1000 / base, 2) if base and m[k] is not None else None
    return m


def effective(vocab: dict, e: dict) -> dict:
    out = dict(e.get("auto", {}))
    out.update(e.get("judged", {}))
    out.update(e.get("overrides", {}))
    return out


def table_rows() -> tuple[list[dict], list[str]]:
    vocab = load_vocab()
    con = db()
    rows = []
    for v in tagged_videos(con):
        e = load_features(v["episode_slug"]).get(v["video_id"])
        if not e:
            continue
        eff = effective(vocab, e)
        eff = {k: ("|".join(x) if isinstance(x, list) else x) for k, x in eff.items()}
        row = {"video_id": v["video_id"], "title": v["title"], "published_at": v["published_at"]}
        row.update(eff)
        row.update(latest_metrics(con, v))
        rows.append(row)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    return rows, cols


def fmt(x, w: int, nd: int = 1) -> str:
    if x is None:
        return "-".rjust(w)
    if isinstance(x, float):
        return f"{x:.{nd}f}".rjust(w)
    return str(x).rjust(w)


def cmd_table(a) -> None:
    rows, cols = table_rows()
    if not rows:
        sys.exit("no tagged videos yet; run `features.py auto`")
    hdr = f"{'video':<11} {'ep':<4} {'pt':>2} {'views':>6} {'avp%':>5} {'avd':>5} {'eng':>6} {'sh/1k':>5} {'sub/1k':>6} {'cm/1k':>5} {'bkt':<4} | hook story emotion audio open"
    print(hdr)
    for r in rows:
        ep = str(r.get("episode_slug") or "")[:3]
        short = lambda k, n: str(r.get(k) or "-")[:n]  # noqa: E731
        print(
            f"{r['video_id']:<11} {ep:<4} {fmt(r.get('series_part'), 2)} {fmt(r['views'], 6)} {fmt(r['avg_view_pct'], 5)} "
            f"{fmt(r['avg_view_duration_s'], 5)} {fmt(r['engaged_views'], 6)} {fmt(r['shares_per_1k'], 5)} "
            f"{fmt(r['subs_gained_per_1k'], 6)} {fmt(r['comments_per_1k'], 5)} {str(r['snapshot_bucket'] or '-'):<4} | "
            f"{short('hook_type', 9)} {short('story_type', 10)} {short('emotion', 7)} {short('audio_type', 10)} {short('opening_visual', 8)}"
        )
    if not a.no_csv:
        path = Path(a.csv) if a.csv else CSV_DEFAULT
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, restval="")
            w.writeheader()
            w.writerows(rows)
        print(f"csv: {path}  ({len(rows)} rows, {len(cols)} columns)")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("auto"); p.add_argument("--video"); p.set_defaults(fn=cmd_auto)  # noqa: E702
    p = sp.add_parser("context"); p.add_argument("video_id"); p.set_defaults(fn=cmd_context)  # noqa: E702
    p = sp.add_parser("set"); p.add_argument("video_id"); p.add_argument("pairs", nargs="+")  # noqa: E702
    p.add_argument("--override", action="store_true"); p.set_defaults(fn=cmd_set)  # noqa: E702
    p = sp.add_parser("todo"); p.set_defaults(fn=cmd_todo)  # noqa: E702
    p = sp.add_parser("table"); p.add_argument("--csv"); p.add_argument("--no-csv", action="store_true")  # noqa: E702
    p.set_defaults(fn=cmd_table)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
