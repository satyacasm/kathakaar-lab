#!/usr/bin/env python3
"""Weekly review pack for the Kathakaar channel (Phase 3 of the feedback loop). Standard library only.

  python3 pipeline/review.py pack [--since YYYY-MM-DD] [--out PATH] [--no-record]

Assembles one deterministic markdown "review pack" that Claude reads to update ideas/LEARNINGS.md. It makes no
judgements and writes no learnings: it only lays the evidence side by side. Sections: header (freshness, score mode,
medians), leaderboard, tag comparisons, retention (with the steepest drop mapped to a script line), traffic sources,
an Instagram Reels table (when IG data exists), videos new since the last pack, comments since the last pack
(YouTube, then Instagram labelled by platform), and an empty "Open questions" heading for Claude.

Inputs (all read-only): cache/analytics/analytics.sqlite (via analytics.py's tables), the tags+metrics CSV that
`features.py table` writes (regenerated on every run), pipeline/score.py (METRICS, ratio, score), and per-episode
timing files (episodes/<slug>/timing_hi.json, else timing.json; 005 Shorts use cuts/chNN/timing.json) plus
episodes/<slug>/script/lines.json for the line text. Videos without an episode_slug (test uploads) are excluded.

Score: score.py `score()` is used when written. While it still raises NotImplementedError the pack falls back to a
PROVISIONAL equal-weight geometric mean of the METRICS ratios and says so in a banner. In both paths, rates
(`*_per_1k`) for videos with fewer than 300 analytics views count as ratio 1.0 (too few views to trust), and the
medians of those rates are taken over videos with 300+ views only.

--since defaults to the time of the last pack (meta key `review_last_pack`, the only thing this script writes to the
DB); the first pack has no lower bound. Output defaults to cache/analytics/review/pack_<YYYY-MM-DD>.md (git-ignored).
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import math
import sqlite3
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features  # noqa: E402
import score as scoremod  # noqa: E402

LAB = Path(__file__).resolve().parents[1]
DB = LAB / "cache/analytics/analytics.sqlite"
EPISODES = LAB / "episodes"
REVIEW_DIR = LAB / "cache/analytics/review"


def _confine(path, *roots) -> Path:
    """Resolve `path` (symlinks followed) and refuse it unless it lies under one of `roots`."""
    p = Path(path).resolve()
    for r in roots:
        r = Path(r).resolve()
        if p == r or r in p.parents:
            return p
    sys.exit(f"error: refusing to write {p}: output must be under " + " or ".join(str(Path(r).resolve()) for r in roots))
CSV_PATH = LAB / "cache/analytics/features_table.csv"
META_KEY = "review_last_pack"
MIN_VIEWS = 300
OWNER_TITLE = "Kathakaar Animated"
POINTS = [0.05, 0.25, 0.5, 0.75, 1.0]
EXTRA_TAGS = ["title_lang", "title_has_number", "title_is_question", "is_short", "audio_type", "publish_hour_bucket"]
KEY_TAGS = ["hook_type", "story_type", "emotion", "audio_type", "title_lang", "opening_visual"]


# ---------------------------------------------------------------- helpers
def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def jload(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def md(s) -> str:
    """Make text safe inside a markdown table cell."""
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ").strip()


def trunc(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def f(x, nd=1, dash="-") -> str:
    return dash if x is None else f"{x:.{nd}f}"


def hour_bucket(h) -> str:
    h = num(h)
    if h is None:
        return ""
    h = int(h)
    if 5 <= h <= 11:
        return "morning"
    if 12 <= h <= 16:
        return "afternoon"
    if 17 <= h <= 21:
        return "evening"
    return "night"


def short_title(t: str) -> str:
    t = t.replace("#Shorts", "").replace("#shorts", "")
    t = " ".join(w for w in t.split() if not w.startswith("#"))
    return trunc(t, 48)


def to_bool_str(v) -> str:
    return str(v)


# ---------------------------------------------------------------- data
def load_rows() -> list[dict]:
    """Regenerate the features table, then read it back; drop videos without an episode slug."""
    with contextlib.redirect_stdout(io.StringIO()):
        features.cmd_table(argparse.Namespace(csv=str(CSV_PATH), no_csv=False))
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("episode_slug")]
    for r in rows:
        r["publish_hour_bucket"] = hour_bucket(r.get("publish_hour_ist"))
    return rows


def score_all(rows: list[dict]) -> tuple[dict, dict, str]:
    """Return (scores by video_id, medians by metric, mode 'user'|'provisional')."""
    metrics = scoremod.METRICS
    med = {}
    for m in metrics:
        vals = []
        for r in rows:
            v = num(r.get(m))
            if v is None:
                continue
            if m.endswith("_per_1k") and (num(r.get("an_views")) or 0) < MIN_VIEWS:
                continue
            vals.append(v)
        med[m] = statistics.median(vals) if vals else 0.0
    mode = "user"
    scores = {}
    for r in rows:
        low = (num(r.get("an_views")) or 0) < MIN_VIEWS
        ratios = {}
        for m in metrics:
            if m.endswith("_per_1k") and low:
                ratios[m] = 1.0
            else:
                ratios[m] = scoremod.ratio(r.get(m), med[m])
        try:
            scores[r["video_id"]] = float(scoremod.score(dict(ratios)))
        except NotImplementedError:
            mode = "provisional"
            vals = [max(v, 0.1) for v in ratios.values()]  # floor: one zero ratio must not zero the whole score
            scores[r["video_id"]] = math.exp(sum(math.log(v) for v in vals) / len(vals))
    return scores, med, mode


# ---------------------------------------------------------------- script timing
class Timing:
    """Lines (number, start, end, text) for one video, or None when no timing exists."""

    def __init__(self, lines: list[tuple], total: float | None, source: str):
        self.lines, self.total, self.source = lines, total, source

    def at(self, t: float) -> tuple:
        for ln in self.lines:
            if ln[1] <= t <= ln[2]:
                return ln
        before = [ln for ln in self.lines if ln[2] < t]
        return before[-1] if before else self.lines[0]


def load_timing(slug: str, cut: str | None) -> Timing | None:
    root = EPISODES / slug
    texts = jload(root / "script" / "lines.json") or {}
    if cut:
        t = jload(root / "cuts" / cut / "timing.json")
        hi = texts.get("hi") or []
        if not t:
            return None
        out = []
        for ln in t["lines"]:
            src = ln.get("src")
            txt = hi[src - 1] if isinstance(src, int) and 0 < src <= len(hi) else ""
            out.append((ln["line"], ln["start"], ln["end"], txt))
        return Timing(out, t.get("total"), f"cuts/{cut}/timing.json")
    for name, key in (("timing_hi.json", "hi"), ("timing.json", "en")):
        t = jload(root / name)
        if t and t.get("lines"):
            arr = texts.get("hi" if name == "timing_hi.json" else "en") or texts.get(key) or []
            out = [(ln["line"], ln["start"], ln["end"], arr[ln["line"] - 1] if 0 < ln["line"] <= len(arr) else "")
                   for ln in t["lines"]]
            return Timing(out, t.get("total"), name)
    return None


# ---------------------------------------------------------------- retention math
def interp(curve: list[tuple[float, float]], x: float):
    if not curve:
        return None
    if x <= curve[0][0]:
        return curve[0][1]
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return curve[-1][1]


def latest_snapshot(con, vid: str):
    return con.execute(
        "SELECT * FROM snapshots WHERE video_id=? ORDER BY an_has_data DESC, id DESC LIMIT 1", (vid,)).fetchone()


def curve_for(con, snap_id: int) -> list[tuple[float, float, float | None]]:
    return [(r["elapsed_ratio"], r["audience_watch_ratio"], r["relative_performance"]) for r in con.execute(
        "SELECT elapsed_ratio,audience_watch_ratio,relative_performance FROM retention WHERE snapshot_id=? "
        "AND audience_watch_ratio IS NOT NULL ORDER BY elapsed_ratio", (snap_id,))]


# ---------------------------------------------------------------- scoreboard
IST = ZoneInfo("Asia/Kolkata")
PLATFORMS = ("youtube", "instagram")
MIN_DAYS = 5          # distinct days of data a YouTube views window needs to count


def _pct(delta, base):
    return round(delta / base * 100, 1) if delta is not None and base else None


def week_over_week(rows: list[tuple[str, str, int]], today: date) -> dict[str, dict]:
    """rows = (day 'YYYY-MM-DD', platform, count). Per platform: now = latest row up to today; week_ago = latest row
    from today-10 to today-7 (older data is not a week-ago reading). Missing week_ago -> delta/pct None."""
    out = {}
    for pl in sorted({r[1] for r in rows}):
        mine = sorted((date.fromisoformat(d), c) for d, p, c in rows if p == pl)
        cur = [c for d, c in mine if d <= today]
        old = [c for d, c in mine if today - timedelta(days=10) <= d <= today - timedelta(days=7)]
        now, ago = (cur[-1] if cur else None), (old[-1] if old else None)
        if not any(d >= today - timedelta(days=2) for d, c in mine if d <= today):
            ago = None                                   # stale latest pull: no honest week-over-week
        delta = now - ago if now is not None and ago is not None else None
        out[pl] = {"now": now, "week_ago": ago, "delta": delta, "pct": _pct(delta, ago)}
    return out


def _window(a, b):
    """(delta, pct) of window sums, None when either side is unknown."""
    d = a - b if a is not None and b is not None else None
    return d, _pct(d, b)


def _ig_window_views(con, start: date, end: date):
    """Views gained in (start, end] from snapshot totals at the two boundaries, per Reel. A Reel with no snapshot at or
    before `start` that existed before it has an unknown baseline and is left out; returns (sum | None, excluded)."""
    total, used, excluded = 0, 0, 0
    for m in con.execute("SELECT media_id, timestamp FROM ig_media WHERE media_product_type='REELS'").fetchall():
        pub = (m["timestamp"] or "")[:10]
        if not pub or pub > end.isoformat():
            continue                                     # did not exist yet (or undated)

        def at(b):
            r = con.execute("SELECT id, day_ist, views FROM ig_snapshots WHERE media_id=? AND has_data=1 "
                            "AND views IS NOT NULL AND day_ist<=? ORDER BY day_ist DESC, id DESC LIMIT 1",
                            (m["media_id"], b.isoformat())).fetchone()
            return r
        hi = at(end)
        lo = 0 if pub > start.isoformat() else at(start)
        stale = hi is not None and hi["day_ist"] < (end - timedelta(days=2)).isoformat()
        same = hi is not None and lo != 0 and lo is not None and hi["id"] == lo["id"]
        if hi is None or lo is None or stale or same:
            excluded += 1
            continue
        total += max(hi["views"] - (lo if lo == 0 else lo["views"]), 0)
        used += 1
    return (total if used else None), excluded


def views_wow(con, today: date) -> dict[str, dict]:
    """Views in the last 7 days (today-6..today) vs the 7 before. YouTube sums the `daily` series; Instagram has no
    daily series, so it differences snapshot totals at the week boundaries (approx True)."""
    def yt_sum(a: date, b: date):
        r = con.execute("SELECT SUM(views) s, COUNT(DISTINCT day) n FROM daily WHERE day>=? AND day<=? "
                        "AND views IS NOT NULL", (a.isoformat(), b.isoformat())).fetchone()
        return (r["s"] if r["n"] >= MIN_DAYS else None), r["n"]
    # Analytics lags 1-2 days: windows end at today-2; each needs MIN_DAYS distinct days of data or it is unknown
    w1 = (today - timedelta(days=8), today - timedelta(days=2))
    w0 = (today - timedelta(days=15), today - timedelta(days=9))
    (now, n1), (prev, n0) = yt_sum(*w1), yt_sum(*w0)
    d, p = _window(now, prev)
    out = {"youtube": {"now": now, "prev": prev, "delta": d, "pct": p, "approx": False, "excluded": 0,
                       "windows": (w1, w0), "days": (n1, n0)}}
    b0, b1, b2 = today - timedelta(days=14), today - timedelta(days=7), today
    now, ex1 = _ig_window_views(con, b1, b2)
    prev, ex2 = _ig_window_views(con, b0, b1)
    d, p = _window(now, prev)
    out["instagram"] = {"now": now, "prev": prev, "delta": d, "pct": p, "approx": True, "excluded": max(ex1, ex2)}
    return out


def cell_table(con, records=None, rows=None, scores=None) -> list[dict]:
    """Loop videos grouped by format x audio x slot: n, median score, followers gained per 1,000 views (YouTube
    subs_gained / an_views from the features table; Instagram gives no per-video follower gain). Joined by episode
    slug. Only posted videos with a features row count."""
    if records is None:
        sys.path.insert(0, str(LAB / "pipeline" / "loop"))
        import vqueue
        records = vqueue.load()
    if rows is None:
        rows = load_rows()
    if scores is None:
        scores = score_all(rows)[0]
    by_slug = {r["episode_slug"]: r for r in rows}
    cells: dict[tuple, list] = {}
    for rec in records:
        row = by_slug.get(rec["id"])
        if rec.get("status") != "posted" or row is None or row["video_id"] not in scores:
            continue
        c = rec.get("cell") or {}
        slot = (datetime.fromisoformat(rec["slot"]).astimezone(IST).strftime("%H:%M") if rec.get("slot")
                else c.get("slot_pref") or "-")
        cells.setdefault((c.get("format", "-"), c.get("audio", "-"), slot), []).append((scores[row["video_id"]], row))
    out = []
    for (fmt, audio, slot), items in sorted(cells.items()):
        both = [(num(r.get("an_views")), num(r.get("subs_gained"))) for _, r in items]
        both = [(v, sb) for v, sb in both if v is not None and sb is not None]   # NULL subs is not zero subs
        views = sum(v for v, _ in both)
        subs = sum(sb for _, sb in both)
        out.append({"format": fmt, "audio": audio, "slot": slot, "n": len(items),
                    "median_score": statistics.median(s for s, _ in items),
                    "followers_per_1k": round(subs / views * 1000, 2) if views else None})
    return out


def sec_scoreboard(out, con, today: date):
    out.append("## 0. Scoreboard\n")
    out.append("Success measure: follower growth and views going up week over week.\n")
    has = bool(con.execute("SELECT 1 FROM sqlite_master WHERE name='followers'").fetchone())
    frows = [(r["day"], r["platform"], r["count"]) for r in con.execute("SELECT day, platform, count FROM followers")] if has else []
    wow = week_over_week(frows, today)
    vw = views_wow(con, today)
    sg = lambda x: "-" if x is None else f"{x:+d}"  # noqa: E731
    pc = lambda x: "-" if x is None else f"{x:+.1f}%"  # noqa: E731
    (a1, b1), (a0, b0) = vw["youtube"]["windows"]
    out.append(f"Views windows (IST): this week {a1} to {b1}, prior week {a0} to {b0} (YouTube analytics lags 1-2 days).\n")
    out.append("| platform | followers now | week ago | change | % | views this week | views prior week | change | % |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for pl in PLATFORMS:
        w = wow.get(pl, {"now": None, "week_ago": None, "delta": None, "pct": None})
        v = vw[pl]
        star = "*" if v["approx"] else ""
        out.append(f"| {pl} | {f(w['now'], 0)} | {f(w['week_ago'], 0)} | {sg(w['delta'])} | {pc(w['pct'])} | "
                   f"{f(v['now'], 0)}{star} | {f(v['prev'], 0)}{star} | {sg(v['delta'])} | {pc(v['pct'])} |")
    out.append("")
    out.append("`-` = no data (never a guess). Follower rows come from daily snapshots, so a week-ago reading appears "
               "once a week of history exists. YouTube views are the sum of the daily analytics series.")
    n1, n0 = vw["youtube"]["days"]
    if vw["youtube"]["now"] is None or vw["youtube"]["prev"] is None:
        out.append(f"YouTube views week over week not shown: a window needs {MIN_DAYS}+ days of data "
                   f"(this week has {n1}, prior week has {n0}).")
    if vw["instagram"]["approx"]:
        ex = vw["instagram"]["excluded"]
        out.append("\\* Instagram has no daily views series: views are the difference between per-Reel snapshot totals at "
                   "the week boundaries (latest snapshot on or before each date), so they are approximate"
                   + (f"; {ex} Reel(s) without a baseline snapshot are left out." if ex else "."))
    out.append("")
    cells = cell_table(con)
    out.append("### Cells (format x audio x slot, loop videos)\n")
    if not cells:
        out.append("no loop videos yet\n")
        return
    out.append("| format | audio | slot | n | median score | followers per 1k views |")
    out.append("|---|---|---|---|---|---|")
    for c in cells:
        out.append(f"| {c['format']} | {c['audio']} | {c['slot']} | {c['n']} | {f(c['median_score'], 2)} | "
                   f"{f(c['followers_per_1k'], 2)} |")
    out.append("")


# ---------------------------------------------------------------- sections
def sec_header(out, today, rows, con, med, mode, since):
    snaps = con.execute("SELECT MAX(taken_at) m FROM snapshots").fetchone()["m"]
    buckets: dict[str, int] = {}
    for r in rows:
        buckets[r.get("snapshot_bucket") or "?"] = buckets.get(r.get("snapshot_bucket") or "?", 0) + 1
    if mode == "provisional":
        out.append("> **Provisional score: pipeline/score.py score() not written yet.** Scores below are an "
                   "equal-weight geometric mean of the METRICS ratios, for ordering only.\n")
    out.append("## 1. Header\n")
    out.append(f"- Videos with an episode: **{len(rows)}** (videos without an episode_slug excluded)")
    out.append(f"- Data freshness: latest snapshot {snaps}; bucket mix: "
               + ", ".join(f"{k} x{v}" for k, v in sorted(buckets.items())))
    out.append(f"- Score mode: **{mode}** ({'score.py score()' if mode == 'user' else 'equal-weight geometric mean'})")
    out.append(f"- Since: {since or 'beginning (first pack)'}")
    out.append(f"- Small-sample guard: rates (`*_per_1k`) for videos with an_views < {MIN_VIEWS} count as ratio 1.0 "
               f"(too few views to trust); medians of rates use only videos with {MIN_VIEWS}+ views.")
    out.append("- Medians (the baseline each ratio divides by): "
               + ", ".join(f"{m}={med[m]:.3g}" for m in med))
    out.append("")


def sec_leaderboard(out, rows, scores):
    out.append("## 2. Leaderboard\n")
    out.append("Provisional or not, 1.0 = typical Kathakaar video. `*` = rates guarded (an_views < 300).\n")
    out.append("| # | video | score | views | avg_view_pct | shares/1k | subs/1k | bucket | hook | story | emotion | audio | "
               "title_lang | opening | title |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(sorted(rows, key=lambda r: -scores[r["video_id"]]), 1):
        star = "*" if (num(r.get("an_views")) or 0) < MIN_VIEWS else ""
        out.append(
            f"| {i} | {r['video_id']} ({r['episode_slug'][:3]}) | {scores[r['video_id']]:.2f} | {r.get('views')} | "
            f"{f(num(r.get('avg_view_pct')))} | {f(num(r.get('shares_per_1k')), 2)}{star} | "
            f"{f(num(r.get('subs_gained_per_1k')), 2)}{star} | {r.get('snapshot_bucket')} | "
            + " | ".join(md(r.get(k)) for k in KEY_TAGS)
            + f" | {md(short_title(r['title']))} |")
    out.append("")


def sec_tags(out, rows, scores):
    out.append("## 3. Tag comparisons\n")
    out.append("Median score per tag value (multi-valued tags count a video under each value). "
               "Values with n<3 are anecdotal.\n")
    vocab_fields = list(features.load_vocab().keys())
    fields = list(dict.fromkeys(vocab_fields + EXTRA_TAGS))
    flat = []
    for fld in fields:
        groups: dict[str, list[dict]] = {}
        for r in rows:
            raw = r.get(fld)
            if raw in (None, ""):
                continue
            for v in str(raw).split("|"):
                groups.setdefault(v, []).append(r)
        if len(groups) <= 1 and sum(len(g) for g in groups.values()) >= len(rows):
            flat.append(fld)
            continue
        if not groups:
            flat.append(fld)
            continue
        out.append(f"### {fld}\n")
        out.append("| value | n | median score | min-max | videos |")
        out.append("|---|---|---|---|---|")
        for v, g in sorted(groups.items(), key=lambda kv: -statistics.median(scores[x["video_id"]] for x in kv[1])):
            sc = [scores[x["video_id"]] for x in g]
            tag = " (n<3, anecdotal)" if len(g) < 3 else ""
            out.append(f"| {md(v)}{tag} | {len(g)} | {statistics.median(sc):.2f} | {min(sc):.2f}-{max(sc):.2f} | "
                       f"{', '.join(x['video_id'] for x in g)} |")
        out.append("")
    out.append("No variation yet (or no data): " + (", ".join(flat) if flat else "none") + "\n")


def sec_retention(out, rows, con):
    out.append("## 4. Retention\n")
    out.append("`audience_watch_ratio` as % of starting audience, interpolated at each point; for Shorts values over "
               "100% mean rewatches. 3s = retention at 3 seconds (3 / duration). Steepest drop = largest fall across "
               "any 5%-of-runtime window after the first 5% (second variant stops at 90% of runtime, to skip the outro); its time is mapped to the script line at the window "
               "midpoint (spoken line for narrated episodes, per-cut timing for 005 Shorts). "
               "Weak hook = relative_performance at 0.1 below 0.5 (weaker than similar-length YouTube videos).\n")
    out.append("| video | dur s | 5% | 25% | 50% | 75% | end | 3s | steepest drop | at (s) | line | steepest before final 10% | at (s) | line |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    notes, flags = [], []
    for r in rows:
        vid = r["video_id"]
        snap = latest_snapshot(con, vid)
        c3 = curve_for(con, snap["id"]) if snap else []
        if not c3:
            out.append(f"| {vid} ({r['episode_slug'][:3]}) | {r.get('duration_s')} | no retention data |||||||| |")
            continue
        curve = [(x, y) for x, y, _ in c3]
        dur = num(r.get("duration_s"))
        vals = [interp(curve, p) for p in POINTS]
        r3 = interp(curve, 3 / dur) if dur else None
        tm = load_timing(r["episode_slug"], r.get("episode_cut") or None)
        if tm and dur and tm.total and abs(tm.total - dur) > 3:
            notes.append(f"{vid}: timing total {tm.total:.0f}s vs video {dur:.0f}s ({tm.source}); "
                         "line mapping approximate.")
        cells = []
        for last in (1.0, 0.9):
            pts = [(a, interp(curve, a)) for a in [0.05 + 0.05 * k for k in range(20)] if a <= last + 1e-9]
            best = max(((ya - yb, a, b) for (a, ya), (b, yb) in zip(pts, pts[1:])), default=None)
            if not best or not dur:
                cells += ["-", "-", "-"]
                continue
            d, a, b = best
            t0, t1 = a * dur, b * dur
            line = "(no timing)"
            if tm:
                ln = tm.at((t0 + t1) / 2)
                line = f"L{ln[0]}: {md(trunc(ln[3], 80))}"
            cells += [f"-{d * 100:.0f} pts ({interp(curve, a) * 100:.0f}% to {interp(curve, b) * 100:.0f}%)",
                      f"{t0:.0f}-{t1:.0f}", line]
        rp = next((rp for x, _, rp in c3 if abs(x - 0.1) < 1e-9), None)
        if rp is not None and rp < 0.5:
            flags.append(f"{vid} ({short_title(r['title'])}): relative_performance at 0.1 = {rp:.2f}")
        out.append(
            f"| {vid} ({r['episode_slug'][:3]}) | {f(dur, 0)} | "
            + " | ".join(f"{v * 100:.0f}%" if v is not None else "-" for v in vals)
            + f" | {f(r3 * 100 if r3 is not None else None, 0)}% | " + " | ".join(cells) + " |")
    out.append("")
    out.append("Weak hook vs similar-length YouTube videos (relative_performance at 0.1 < 0.5): "
               + ("none" if not flags else "") + "")
    for fl in flags:
        out.append(f"- {fl}")
    for n in notes:
        out.append(f"- Note: {n}")
    out.append("")


def sec_traffic(out, rows, con):
    out.append("## 5. Traffic sources\n")
    out.append("Share of views by source (latest snapshot). Flag = YT_SEARCH above 3% (search demand).\n")
    order = ["SHORTS", "YT_SEARCH"]
    data, others = {}, set()
    for r in rows:
        snap = latest_snapshot(con, r["video_id"])
        t = {x["source"]: x["views"] or 0 for x in con.execute(
            "SELECT source,views FROM traffic WHERE snapshot_id=?", (snap["id"],))} if snap else {}
        data[r["video_id"]] = t
        others |= {k for k, v in t.items() if v and k not in order}
    others = sorted(others)
    cols = order + others
    out.append("| video | total | " + " | ".join(cols) + " | flag |")
    out.append("|---|---|" + "---|" * len(cols) + "---|")
    for r in rows:
        t = data[r["video_id"]]
        tot = sum(t.values())
        if not tot:
            out.append(f"| {r['video_id']} ({r['episode_slug'][:3]}) | 0 |" + " |" * len(cols) + " |")
            continue
        sp = t.get("YT_SEARCH", 0) / tot * 100
        out.append(f"| {r['video_id']} ({r['episode_slug'][:3]}) | {tot} | "
                   + " | ".join(f"{t.get(c, 0) / tot * 100:.1f}%" for c in cols)
                   + f" | {'search demand' if sp > 3 else ''} |")
    out.append("")


def has_ig(con) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE name='ig_snapshots'").fetchone()) and \
        bool(con.execute("SELECT 1 FROM ig_snapshots LIMIT 1").fetchone())


def sec_instagram(out, con):
    out.append("## 5b. Instagram Reels\n")
    if not has_ig(con):
        out.append("Instagram: no data yet\n")
        return
    out.append("Latest insights snapshot with data per Reel (insights lag up to 48 h; `-` = no data). Rates are per 1,000 "
               "views (noisy under 300 views). skip % = reels_skip_rate as returned by "
               "Meta; avg watch s = ig_reels_avg_watch_time in seconds. Episode `-` = not mapped "
               "(`analytics.py ig map`).\n")
    out.append("| reel | episode | published | bucket | views | reach | avg watch s | skip % | shares/1k | saves/1k | "
               "comments/1k | likes/1k | caption |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = con.execute("SELECT * FROM ig_media WHERE media_product_type='REELS' ORDER BY timestamp DESC").fetchall()
    for m in rows:
        s = con.execute("SELECT * FROM ig_snapshots WHERE media_id=? AND has_data=1 ORDER BY id DESC LIMIT 1",
                        (m["media_id"],)).fetchone()
        first = (m["caption"] or "").strip().splitlines()[0] if (m["caption"] or "").strip() else ""
        head = f"| {m['media_id']} | {m['episode_slug'] or '-'} | {(m['timestamp'] or '')[:10]} | "
        if not s:
            out.append(head + f"- | - | - | - | - | - | - | - | - | {md(trunc(first, 40))} |")
            continue
        v = s["views"]
        per = lambda k: f(s[k] / v * 1000, 1) if v and s[k] is not None else "-"  # noqa: E731
        out.append(head + f"{s['bucket']} | {f(v, 0)} | {f(s['reach'], 0)} | {f(s['avg_watch_s'], 1)} | "
                   f"{f(s['skip_rate'], 1)} | {per('shares')} | {per('saved')} | {per('comments')} | {per('likes')} | "
                   f"{md(trunc(first, 40))} |")
    out.append("")


def sec_new(out, rows, con, since):
    out.append("## 6. New since last pack\n")
    new = []
    for r in rows:
        first = con.execute("SELECT MIN(taken_at) m FROM snapshots WHERE video_id=?", (r["video_id"],)).fetchone()["m"]
        pub = r.get("published_at") or ""
        if since is None or pub > since or (first and first > since):
            new.append((r, pub, first))
    if not new:
        out.append(f"No videos published or first snapshotted after {since}.\n")
        return
    for r, pub, first in new:
        out.append(f"- {r['video_id']} ({r['episode_slug']}): published {pub}, first snapshot {first}; "
                   f"{md(short_title(r['title']))}")
    out.append("")


def sec_comments(out, rows, con, since):
    out.append("## 7. Comments\n")
    ours = lambda a: "kathakaar" in "".join(ch for ch in (a or "").lower() if ch.isalnum())  # noqa: E731
    total = n_ours = 0
    summary = []
    body = []
    for r in rows:
        q = "SELECT * FROM comments WHERE video_id=?" + (" AND published_at > ?" if since else "") + \
            " ORDER BY published_at DESC"
        cs = con.execute(q, (r["video_id"], since) if since else (r["video_id"],)).fetchall()
        if not cs:
            continue
        n_ours += sum(1 for c in cs if ours(c["author"]))
        total += len(cs)
        summary.append(f"{r['video_id']} ({r['episode_slug'][:3]}): {len(cs)}")
        body.append(f"### {r['video_id']}, {md(short_title(r['title']))} ({len(cs)})\n")
        for c in cs:
            who = " (ours)" if ours(c["author"]) else ""
            rep = "reply" if c["parent_id"] else "comment"
            text = " ".join((c["text"] or "").split())
            body.append(f"- [{rep}] {c['published_at']} | {c['like_count'] or 0} likes | {c['author']}{who}: {text}")
        body.append("")
    out.append(f"Comments published after {since or 'the beginning'}: **{total}** "
               f"({n_ours} by the channel owner, labelled \"(ours)\", author matching \"{OWNER_TITLE}\"). "
               "Author channel ids are not stored, so ownership is judged by name only.\n")
    if summary:
        out.append("Per video: " + "; ".join(summary) + "\n")
    out.extend(body)
    if not total:
        out.append("No new comments.\n")
    sec_ig_comments(out, con, since, ours)


def sec_ig_comments(out, con, since, ours):
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE name='ig_comments'").fetchone()
    cs_all = con.execute("SELECT c.*, m.episode_slug, m.caption FROM ig_comments c JOIN ig_media m ON m.media_id=c.media_id "
                         + ("WHERE c.timestamp > ? " if since else "") + "ORDER BY c.media_id, c.timestamp DESC",
                         (since,) if since else ()).fetchall() if exists else []
    out.append("### [Instagram] comments\n")
    if not cs_all:
        out.append("Instagram: no new comments.\n")
        return
    by: dict[str, list] = {}
    for c in cs_all:
        by.setdefault(c["media_id"], []).append(c)
    n_ours = sum(1 for c in cs_all if ours(c["username"]))
    out.append(f"Instagram comments published after {since or 'the beginning'}: **{len(cs_all)}** "
               f"({n_ours} by the channel, labelled \"(ours)\").\n")
    for mid, cs in by.items():
        first = (cs[0]["caption"] or "").strip().splitlines()[0] if (cs[0]["caption"] or "").strip() else ""
        out.append(f"#### [Instagram] {mid} ({cs[0]['episode_slug'] or 'unmapped'}), {md(trunc(first, 48))} ({len(cs)})\n")
        for c in cs:
            who = " (ours)" if ours(c["username"]) else ""
            rep = "reply" if c["parent_id"] else "comment"
            text = " ".join((c["text"] or "").split())
            out.append(f"- [Instagram {rep}] {c['timestamp']} | {c['like_count'] or 0} likes | {c['username']}{who}: {text}")
        out.append("")


# ---------------------------------------------------------------- command
class _StrictParser(argparse.ArgumentParser):
    """No flag abbreviations (--ou, --cs, --pa), including in sub-commands."""
    def __init__(self, *a, **k):
        k.setdefault("allow_abbrev", False)
        super().__init__(*a, **k)

def cmd_pack(a) -> None:
    dest = _confine(a.out, REVIEW_DIR) if a.out else None   # refuse a stray --out before any work
    if not DB.exists():
        sys.exit(f"no analytics DB at {DB}: run analytics.py pull first")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)
    last = con.execute("SELECT value FROM meta WHERE key=?", (META_KEY,)).fetchone()
    since = a.since or (last["value"] if last else None)
    rows = load_rows()
    if not rows:
        sys.exit("no videos with an episode_slug in the features table")
    scores, med, mode = score_all(rows)
    today = datetime.now().strftime("%Y-%m-%d")
    out: list[str] = []
    out.append(f"# Kathakaar review pack, {today}\n")
    sec_scoreboard(out, con, datetime.now(IST).date())
    sec_header(out, today, rows, con, med, mode, since)
    sec_leaderboard(out, rows, scores)
    sec_tags(out, rows, scores)
    sec_retention(out, rows, con)
    sec_traffic(out, rows, con)
    sec_instagram(out, con)
    sec_new(out, rows, con, since)
    sec_comments(out, rows, con, since)
    out.append("## 8. Open questions\n\n")
    path = dest if dest else REVIEW_DIR / f"pack_{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    con.close()
    if not a.no_record:
        w = sqlite3.connect(DB)
        with w:
            w.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (META_KEY, now.strftime("%Y-%m-%dT%H:%M:%SZ")))
        w.close()
    print(f"pack: {path}  ({len(out)} blocks, score mode {mode}, since {since or 'beginning'})")


def main() -> None:
    ap = _StrictParser(description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pack", help="write the review pack markdown")
    p.add_argument("--since", help="YYYY-MM-DD; default = time of the last pack")
    p.add_argument("--out", help="output path (default cache/analytics/review/pack_<date>.md)")
    p.add_argument("--no-record", action="store_true", help="do not update review_last_pack")
    p.set_defaults(fn=cmd_pack)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
