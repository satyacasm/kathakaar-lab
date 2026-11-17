#!/usr/bin/env python3
"""Trend scout for the Kathakaar channel (YouTube Data API v3 + unofficial suggest endpoint). Standard library only.

Phase 4 of the feedback loop: what is the niche (Indian mythology Shorts, India audience) doing right now, and where
do we have a gap? Read-only: it never calls a write endpoint. Reuses the OAuth token from youtube_publish.py.

  trends scan [--force]       at most once per IST day unless --force. Niche: for up to max_searches_per_scan queries
                              (rotating through the list across days, rotation kept in the DB) run search.list
                              (order=viewCount, last lookback_days, regionCode=IN), then videos.list for stats, skip
                              our own channel, detect Shorts (GET youtube.com/shorts/<id>, no redirects; cached),
                              store one row per video per scan with views/day. Also: India music chart
                              (videos.list chart=mostPopular, category 10), search suggestions for each seed
                              (unofficial suggestqueries endpoint; on failure logs one line and continues) and song
                              credit lines pulled from the descriptions of the top niche Shorts.
  trends digest [--out PATH]  write ideas/trends-<YYYY-MM-DD>.md (top Shorts, rising, topic heat, competitors, music,
                              suggestions, our gap, upcoming festivals, empty "Fit for Kathakaar" section for Claude).
  trends status               last scan, quota units spent today, rows stored.

Data lives in cache/analytics/trends.sqlite (git-ignored, its own file). Config: pipeline/trends_queries.json.
Festival calendar: ideas/festival_calendar.json (git-ignored).

Quota: search.list costs 100 units per call, videos.list / channels.list 1 unit. A default scan is 8 searches + ~10
cheap calls = ~810 units. A ledger per IST day is kept in the DB and a scan refuses to run if the day's trends spend
would exceed 2,000 units (the daily quota is 10,000 and uploads cost ~100 each, captions 400, so keep headroom).

Compliance (YouTube API policy): other channels' data must not be stored for more than 30 days. Every scan deletes
other-channel rows (videos, chart, song credit lines) older than 30 days. Only per-character/day aggregate heat
(counts and weights, no video data) is kept longer. Our own channel is excluded from the niche data entirely.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import youtube_publish as yt  # noqa: E402
import analytics as an  # noqa: E402  (request helper with retry, Shorts check, duration parse)

LAB = yt.LAB
STORE = LAB / "cache" / "analytics"
DB_PATH = STORE / "trends.sqlite"
CONFIG = Path(__file__).parent / "trends_queries.json"
IDEAS = LAB / "ideas"
CALENDAR = IDEAS / "festival_calendar.json"
EPISODES = LAB / "episodes"
IST = ZoneInfo("Asia/Kolkata")
SEARCH_COST, LIST_COST = 100, 1
DAILY_BUDGET = 2000
RETENTION_DAYS = 30
SHORT_MAX_S = 180
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS quota (day TEXT PRIMARY KEY, units INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, taken_at TEXT NOT NULL, scan_date TEXT NOT NULL,
  units INTEGER DEFAULT 0, queries TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS obs (                  -- other channels' video data: purged after 30 days
  scan_id INTEGER NOT NULL, video_id TEXT NOT NULL, scan_date TEXT NOT NULL, channel_id TEXT, channel_title TEXT,
  title TEXT, description TEXT, published_at TEXT, duration_s INTEGER, is_short INTEGER,
  views INTEGER, likes INTEGER, comments INTEGER, query TEXT, age_days REAL, views_per_day REAL,
  prev_views INTEGER, prev_at TEXT, velocity REAL,  -- velocity = views gained per day since the previous scan that saw it
  PRIMARY KEY (scan_id, video_id));
CREATE INDEX IF NOT EXISTS ix_obs_video ON obs(video_id, scan_id);
CREATE TABLE IF NOT EXISTS short_cache (video_id TEXT PRIMARY KEY, is_short INTEGER, method TEXT, checked_date TEXT);
CREATE TABLE IF NOT EXISTS chart (scan_id INTEGER NOT NULL, scan_date TEXT NOT NULL, rank INTEGER, video_id TEXT,
  title TEXT, channel TEXT, views INTEGER, PRIMARY KEY (scan_id, rank));
CREATE TABLE IF NOT EXISTS suggestions (scan_id INTEGER NOT NULL, scan_date TEXT NOT NULL, seed TEXT, completion TEXT,
  source TEXT DEFAULT 'unofficial');
CREATE TABLE IF NOT EXISTS credits (scan_id INTEGER NOT NULL, scan_date TEXT NOT NULL, video_id TEXT, line TEXT);
CREATE TABLE IF NOT EXISTS heat (                  -- aggregate only, no video data: kept
  scan_id INTEGER NOT NULL, scan_date TEXT NOT NULL, character TEXT NOT NULL, mentions INTEGER, heat REAL,
  PRIMARY KEY (scan_id, character));
"""

CREDIT_RE = re.compile(r"(?i)\b(song|music|track|audio|singer|lyrics|bgm|composer)\b|🎵|🎶|🎼|गीत|संगीत|गाना|गायक|ऑडियो")
CREDIT_SKIP = re.compile(r"(?i)copyright|disclaimer|subscribe|follow us|business|inquir|http|@|#")


# ------------------------------------------------------------------ helpers
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def db() -> sqlite3.Connection:
    STORE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()
    return con


def meta_get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))


def spent_today(con) -> int:
    r = con.execute("SELECT units FROM quota WHERE day=?", (today_ist(),)).fetchone()
    return r["units"] if r else 0


def spend(con, units: int) -> None:
    con.execute("INSERT INTO quota(day,units) VALUES(?,?) ON CONFLICT(day) DO UPDATE SET units=units+excluded.units",
                (today_ist(), units))
    con.commit()


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def log(msg: str) -> None:
    print(yt.scrub(msg))


def api(con, url: str, params: dict, cost: int) -> dict:
    """Authorised GET via analytics.request (retries). The cost is booked in the ledger even if the call fails."""
    try:
        return an.request(url, params)
    finally:
        spend(con, cost)


# ------------------------------------------------------------------ characters
def compile_aliases(chars: dict[str, list[str]]) -> dict[str, re.Pattern]:
    edge_l, edge_r = r"(?<![A-Za-z0-9ऀ-ॿ])", r"(?![A-Za-z0-9ऀ-ॿ])"
    out = {}
    for key, aliases in chars.items():
        alts = sorted({a.lower() for a in aliases} | {key}, key=len, reverse=True)
        out[key] = re.compile(edge_l + "(?:" + "|".join(re.escape(a) for a in alts) + ")" + edge_r)
    return out


def mentions(text: str, pats: dict[str, re.Pattern]) -> list[str]:
    t = (text or "").lower()
    return [k for k, p in pats.items() if p.search(t)]


def canon_character(name: str, pats: dict[str, re.Pattern]) -> str | None:
    hits = mentions(name, pats)
    return hits[0] if hits else None


# ------------------------------------------------------------------ scan
def own_channel_id(con) -> str | None:
    cid = meta_get(con, "own_channel_id")
    if cid:
        return cid
    r = api(con, f"{yt.API}/channels", {"part": "id", "mine": "true"}, LIST_COST)
    items = r.get("items") or []
    if items:
        meta_set(con, "own_channel_id", items[0]["id"])
        con.commit()
        return items[0]["id"]
    return None


def pick_queries(con, cfg: dict) -> list[str]:
    qs = cfg["queries"]
    n = min(int(cfg.get("max_searches_per_scan", 8)), len(qs))
    start = int(meta_get(con, "rotation_idx", 0)) % len(qs)
    chosen = [qs[(start + i) % len(qs)] for i in range(n)]
    meta_set(con, "rotation_idx", (start + n) % len(qs))
    return chosen


def detect_shorts(con, vids: list[dict]) -> dict[str, int]:
    """Short/not per video id (cached). Only videos <= 200 s can be Shorts; others are False without a request."""
    res, todo = {}, []
    for v in vids:
        vid, dur = v["id"], v["dur"]
        row = con.execute("SELECT is_short FROM short_cache WHERE video_id=?", (vid,)).fetchone()
        if row:
            res[vid] = row["is_short"]
        elif dur is not None and dur > 200:
            res[vid] = 0
            con.execute("INSERT OR REPLACE INTO short_cache VALUES(?,?,?,?)", (vid, 0, "duration", today_ist()))
        else:
            todo.append(v)
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            checks = list(ex.map(lambda v: an.check_short(v["id"]), todo))
        for v, c in zip(todo, checks):
            if c is not None:
                val, method = int(c), "shorts_url"
            else:
                val, method = int(v["dur"] is not None and v["dur"] <= SHORT_MAX_S), "duration"
            res[v["id"]] = val
            con.execute("INSERT OR REPLACE INTO short_cache VALUES(?,?,?,?)", (v["id"], val, method, today_ist()))
    return res


def fetch_suggestions(seed: str) -> list[str]:
    url = f"{SUGGEST_URL}?{urllib.parse.urlencode({'client': 'firefox', 'ds': 'yt', 'hl': 'hi', 'q': seed})}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    return [str(x) for x in data[1]][:15]


def extract_credits(desc: str) -> list[str]:
    out = []
    for line in (desc or "").splitlines():
        line = line.strip()
        if 3 <= len(line) and CREDIT_RE.search(line) and not CREDIT_SKIP.search(line):
            out.append(line[:120])
    return out[:4]


def purge(con) -> int:
    cutoff = (datetime.now(IST) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    n = 0
    for t, col in (("obs", "scan_date"), ("chart", "scan_date"), ("credits", "scan_date"),
                   ("short_cache", "checked_date")):
        n += con.execute(f"DELETE FROM {t} WHERE {col} < ?", (cutoff,)).rowcount
    con.commit()
    return n


def cmd_scan(a):
    con = db()
    cfg = load_config()
    today = today_ist()
    if not a.force and meta_get(con, "last_scan_date") == today:
        log(f"Already scanned today ({today} IST); use --force to scan again.")
        return 0
    n_search = min(int(cfg.get("max_searches_per_scan", 8)), len(cfg["queries"]))
    estimate = n_search * SEARCH_COST + 16 * LIST_COST
    spent = spent_today(con)
    if spent + estimate > DAILY_BUDGET:
        log(f"Refusing: {spent} units already spent today + ~{estimate} for this scan > {DAILY_BUDGET} budget.")
        return 1
    pats = compile_aliases(cfg["characters"])
    started_units = spent
    queries = pick_queries(con, cfg)
    scan_id = con.execute("INSERT INTO scans(taken_at,scan_date,queries) VALUES(?,?,?)",
                          (iso(now_utc()), today, json.dumps(queries, ensure_ascii=False))).lastrowid
    con.commit()
    notes = []
    own = own_channel_id(con)

    # --- niche search
    after = iso(now_utc() - timedelta(days=int(cfg.get("lookback_days", 14))))
    found: dict[str, str] = {}
    for q in queries:
        try:
            r = api(con, f"{yt.API}/search", {"part": "id", "type": "video", "order": "viewCount", "q": q,
                                               "publishedAfter": after, "regionCode": "IN", "maxResults": 50}, SEARCH_COST)
        except an.ApiError as e:
            notes.append(f"search '{q}' failed: {e}")
            log(f"search '{q}' failed: {e}")
            if e.reason == "quotaExceeded":
                break
            continue
        for it in r.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                found.setdefault(vid, q)
    log(f"search: {len(queries)} queries, {len(found)} unique videos")

    vids = []
    ids = list(found)
    for i in range(0, len(ids), 50):
        try:
            r = api(con, f"{yt.API}/videos", {"part": "snippet,contentDetails,statistics", "id": ",".join(ids[i:i + 50]),
                                               "maxResults": 50}, LIST_COST)
        except an.ApiError as e:
            notes.append(f"videos.list failed: {e}")
            log(f"videos.list failed: {e}")
            continue
        for v in r.get("items", []):
            sn = v["snippet"]
            if own and sn.get("channelId") == own:
                continue
            vids.append({"id": v["id"], "sn": sn, "st": v.get("statistics", {}),
                         "dur": an.parse_duration(v.get("contentDetails", {}).get("duration"))})
    shorts = detect_shorts(con, vids)
    now = now_utc()
    toint = lambda x: int(x) if x is not None else None  # noqa: E731
    for v in vids:
        sn, st = v["sn"], v["st"]
        views = toint(st.get("viewCount")) or 0
        pub = parse_ts(sn["publishedAt"])
        age = max((now - pub).total_seconds() / 86400, 0.25)
        prev = con.execute("SELECT views, scan_id, (SELECT taken_at FROM scans s WHERE s.id=o.scan_id) AS at "
                           "FROM obs o WHERE video_id=? AND scan_id<? ORDER BY scan_id DESC LIMIT 1",
                           (v["id"], scan_id)).fetchone()
        pv = pat = vel = None
        if prev:
            pv, pat = prev["views"], prev["at"]
            hrs = (now - parse_ts(pat)).total_seconds() / 3600
            if hrs >= 6:
                vel = (views - pv) / hrs * 24
        con.execute("INSERT OR REPLACE INTO obs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (scan_id, v["id"], today, sn.get("channelId"), sn.get("channelTitle"), sn.get("title"),
                     (sn.get("description") or "")[:1500], sn["publishedAt"], v["dur"], shorts.get(v["id"]),
                     views, toint(st.get("likeCount")), toint(st.get("commentCount")), found.get(v["id"]),
                     round(age, 2), round(views / age, 1), pv, pat, vel))
    con.commit()
    log(f"stored {len(vids)} niche videos (own channel excluded)")

    # --- aggregate topic heat (top 100 by views/day, titles only)
    top = con.execute("SELECT title, views_per_day FROM obs WHERE scan_id=? ORDER BY views_per_day DESC LIMIT 100",
                      (scan_id,)).fetchall()
    agg: dict[str, list[float]] = {}
    for r in top:
        for c in mentions(r["title"], pats):
            agg.setdefault(c, []).append(r["views_per_day"])
    for c, vals in agg.items():
        con.execute("INSERT OR REPLACE INTO heat VALUES(?,?,?,?,?)", (scan_id, today, c, len(vals), round(sum(vals), 1)))

    # --- song credits from the top niche Shorts
    for r in con.execute("SELECT video_id, description FROM obs WHERE scan_id=? AND is_short=1 "
                         "ORDER BY views_per_day DESC LIMIT 30", (scan_id,)).fetchall():
        for line in extract_credits(r["description"]):
            con.execute("INSERT INTO credits VALUES(?,?,?,?)", (scan_id, today, r["video_id"], line))

    # --- music chart
    try:
        r = api(con, f"{yt.API}/videos", {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": "IN",
                                           "videoCategoryId": "10", "maxResults": 50}, LIST_COST)
        for i, v in enumerate(r.get("items", []), 1):
            con.execute("INSERT OR REPLACE INTO chart VALUES(?,?,?,?,?,?,?)",
                        (scan_id, today, i, v["id"], v["snippet"].get("title"), v["snippet"].get("channelTitle"),
                         toint(v.get("statistics", {}).get("viewCount"))))
        log(f"music chart: {len(r.get('items', []))} rows")
    except an.ApiError as e:
        notes.append(f"chart failed: {e}")
        log(f"music chart failed: {e}")

    # --- search suggestions (unofficial, free)
    for seed in cfg.get("suggestion_seeds", []):
        try:
            comps = fetch_suggestions(seed)
        except Exception as e:  # noqa: BLE001
            msg = f"suggestions unavailable for '{seed}' (unofficial endpoint): {type(e).__name__}"
            notes.append(msg)
            log(msg)
            continue
        for c in comps:
            con.execute("INSERT INTO suggestions VALUES(?,?,?,?,'unofficial')", (scan_id, today, seed, c))
    log(f"suggestions: {con.execute('SELECT COUNT(*) FROM suggestions WHERE scan_id=?', (scan_id,)).fetchone()[0]} rows")

    deleted = purge(con)
    units = spent_today(con) - started_units
    con.execute("UPDATE scans SET units=?, notes=? WHERE id=?", (units, "; ".join(notes) or None, scan_id))
    if vids:
        meta_set(con, "last_scan_date", today)
        meta_set(con, "last_scan_at", iso(now_utc()))
    con.commit()
    log(f"scan {scan_id} done: {units} units this scan, {spent_today(con)} today; purged {deleted} rows older than "
        f"{RETENTION_DAYS} days")
    return 0 if vids else 1


# ------------------------------------------------------------------ digest
def fmt_n(n) -> str:
    return f"{int(n):,}" if n is not None else "-"


def fmt_dur(s) -> str:
    return f"{s // 60}:{s % 60:02d}" if s is not None else "-"


def esc(t) -> str:
    return (t or "").replace("|", "/").replace("\n", " ").strip()


def story_filter(cfg: dict):
    """Return (title, channel) -> bool: False for non-story formats (non_story_terms in title or channel name, or
    fewer than min_story_words real words once hashtags are stripped: bhajan/status clips)."""
    terms = [t.lower() for t in cfg.get("non_story_terms", [])]
    min_words = int(cfg.get("min_story_words", 4))

    def ok(title: str, channel: str = "") -> bool:
        text = f"{title or ''} {channel or ''}".lower()
        if any(t in text for t in terms):
            return False
        bare = re.sub(r"#\S+|@\S+", " ", title or "")
        words = [w for w in re.findall(r"[^\W_]+", bare) if not w.isdigit()]
        return len(words) >= min_words
    return ok


def our_coverage(pats) -> tuple[dict[str, list[str]], dict[str, float]]:
    """Characters we have made videos about (features.json protagonist) and mean score per character if available."""
    cover: dict[str, list[str]] = {}
    vid_char: dict[str, str] = {}
    for p in sorted(EPISODES.glob("*/analytics/features.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for vid, rec in data.items():
            prot = ((rec.get("overrides") or {}).get("protagonist")) or ((rec.get("judged") or {}).get("protagonist"))
            c = canon_character(prot or "", pats)
            if c:
                cover.setdefault(c, []).append(p.parent.parent.name)
                vid_char[vid] = c
    scores: dict[str, float] = {}
    try:
        import review  # noqa: PLC0415
        rows = review.load_rows()
        sc, _, mode = review.score_all(rows)
        per: dict[str, list[float]] = {}
        for vid, s in sc.items():
            if vid in vid_char:
                per.setdefault(vid_char[vid], []).append(s)
        scores = {c: sum(v) / len(v) for c, v in per.items()}
    except Exception as e:  # noqa: BLE001
        print(f"(score unavailable: {type(e).__name__})", file=sys.stderr)
    return cover, scores


def cmd_digest(a):
    con = db()
    cfg = load_config()
    pats = compile_aliases(cfg["characters"])
    scan = con.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    if not scan:
        log("No scans yet; run `trends.py scan` first.")
        return 1
    sid = scan["id"]
    prev = con.execute("SELECT id, scan_date FROM scans WHERE id<? AND EXISTS (SELECT 1 FROM heat WHERE scan_id=scans.id) "
                       "ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    out = [f"# Trend scout - {today_ist()}", "",
           f"Scan #{sid} taken {scan['taken_at']} ({scan['units']} quota units). Region IN, last {cfg.get('lookback_days', 14)} "
           f"days, queries this scan: {', '.join(json.loads(scan['queries']))}.", ""]
    if scan["notes"]:
        out += [f"Scan notes: {esc(scan['notes'])}", ""]
    out += ["Other channels' data is kept 30 days only (YouTube API policy).", ""]

    # top 20 shorts
    story = story_filter(cfg)
    allrows = con.execute("SELECT * FROM obs WHERE scan_id=? AND is_short=1 ORDER BY views_per_day DESC", (sid,)).fetchall()
    rows = [r for r in allrows if story(r["title"], r["channel_title"])][:20]
    dropped = sum(1 for r in allrows if not story(r["title"], r["channel_title"]))
    out += ["## Top 20 niche storytelling Shorts by views/day", "",
            f"Left out {dropped} of {len(allrows)} Shorts as non-story (`non_story_terms` in title or channel, or a "
            "hashtag-only title). Topic heat below still counts them.", "",
            "| # | title | channel | views | age (d) | views/day | dur | link | query |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        out.append(f"| {i} | {esc(r['title'])[:70]} | {esc(r['channel_title'])[:30]} | {fmt_n(r['views'])} | {r['age_days']:.1f} | "
                   f"{fmt_n(r['views_per_day'])} | {fmt_dur(r['duration_s'])} | https://youtube.com/shorts/{r['video_id']} | {esc(r['query'])} |")
    out.append("")

    # rising
    out += ["## Rising (views gained per day since previous scan)", ""]
    rising = con.execute("SELECT * FROM obs WHERE scan_id=? AND velocity IS NOT NULL ORDER BY velocity DESC LIMIT 15", (sid,)).fetchall()
    if not rising:
        out += ["Needs 2+ scans at least 6 hours apart that saw the same videos; none yet.", ""]
    else:
        out += ["| # | title | channel | views | gained/day | was (at prev scan) | link |", "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rising, 1):
            out.append(f"| {i} | {esc(r['title'])[:60]} | {esc(r['channel_title'])[:25]} | {fmt_n(r['views'])} | {fmt_n(r['velocity'])} | "
                       f"{fmt_n(r['prev_views'])} | https://youtube.com/watch?v={r['video_id']} |")
        out.append("")

    # heat
    heat = con.execute("SELECT * FROM heat WHERE scan_id=? ORDER BY heat DESC", (sid,)).fetchall()
    prank, pheat = {}, {}
    if prev:
        for i, r in enumerate(con.execute("SELECT * FROM heat WHERE scan_id=? ORDER BY heat DESC", (prev["id"],)).fetchall(), 1):
            prank[r["character"]], pheat[r["character"]] = i, r["heat"]
    out += ["## Topic heat (character mentions in titles of top-100 niche results, weighted by views/day)", ""]
    if prev:
        out += [f"Compared with scan of {prev['scan_date']}.", ""]
    out += ["| rank | character | mentions | heat (sum views/day) | prev rank | change |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(heat[:20], 1):
        c = r["character"]
        pr = prank.get(c)
        chg = "-" if c not in pheat else f"{(r['heat'] - pheat[c]) / pheat[c] * 100:+.0f}%" if pheat[c] else "-"
        out.append(f"| {i} | {c} | {r['mentions']} | {fmt_n(r['heat'])} | {pr or ('new' if prev else '-')} | {chg} |")
    out.append("")

    # competitors
    agg: dict[str, dict] = {}
    for r in con.execute("SELECT channel_id, channel_title, title, views_per_day FROM obs WHERE scan_id=?", (sid,)):
        if story(r["title"], r["channel_title"]):
            g = agg.setdefault(r["channel_id"], {"channel_title": r["channel_title"], "n": 0, "vpd": 0.0})
            g["n"] += 1
            g["vpd"] += r["views_per_day"] or 0
    comp = sorted((g for g in agg.values() if g["n"] >= 3), key=lambda g: -g["vpd"])[:15]
    out += ["## Competitor storytelling channels (3+ story-titled appearances this scan)", ""]
    if comp:
        out += ["| channel | videos | total views/day |", "|---|---|---|"]
        out += [f"| {esc(r['channel_title'])} | {r['n']} | {fmt_n(r['vpd'])} |" for r in comp]
    else:
        out.append("None.")
    out.append("")

    # music
    chart = con.execute("SELECT * FROM chart WHERE scan_id=? ORDER BY rank LIMIT 20", (sid,)).fetchall()
    out += ["## Music chart - India top 20 (YouTube Music category, mostPopular)", "",
            "| rank | title | channel | views |", "|---|---|---|---|"]
    out += [f"| {r['rank']} | {esc(r['title'])[:70]} | {esc(r['channel'])[:30]} | {fmt_n(r['views'])} |" for r in chart]
    out.append("")
    credits: dict[str, int] = {}
    for r in con.execute("SELECT line FROM credits WHERE scan_id=?", (sid,)).fetchall():
        credits[r["line"]] = credits.get(r["line"], 0) + 1
    out += ["### Song credits seen in top niche Shorts (raw description lines)", ""]
    if credits:
        out += [f"- {esc(k)}" + (f"  (x{n})" if n > 1 else "") for k, n in sorted(credits.items(), key=lambda kv: -kv[1])[:30]]
    else:
        out.append("None found.")
    out.append("")

    # suggestions
    out += ["## Search suggestions (unofficial endpoint)", ""]
    sugg = con.execute("SELECT seed, completion FROM suggestions WHERE scan_id=? ORDER BY rowid", (sid,)).fetchall()
    if sugg:
        by: dict[str, list[str]] = {}
        for r in sugg:
            by.setdefault(r["seed"], []).append(r["completion"])
        out += [f"- **{s}**: " + "; ".join(v) for s, v in by.items()]
    else:
        out.append("Unavailable this scan.")
    out.append("")

    # gap
    cover, scores = our_coverage(pats)
    out += ["## Our gap", ""]
    hot = [r["character"] for r in heat[:10]]
    missing = [c for c in hot if c not in cover]
    out += ["Hot characters (top 10 by heat) we have never made a video about (by features.json protagonist):", ""]
    out += [f"- {c} (heat {fmt_n(next(r['heat'] for r in heat if r['character'] == c))})" for c in missing] or ["- none"]
    out += ["", "Hot characters we HAVE covered:", ""]
    have = [c for c in hot if c in cover]
    for c in have:
        s = f", score {scores[c]:.2f}" if c in scores else ""
        out.append(f"- {c}: {len(cover[c])} video(s) ({', '.join(sorted(set(cover[c])))}){s}")
    if not have:
        out.append("- none")
    out.append("")

    # festivals
    out += ["## Festivals in the next 45 days", ""]
    try:
        fest = json.loads(CALENDAR.read_text(encoding="utf-8"))["festivals"]
        t0 = datetime.now(IST).date()
        rows = []
        for f in fest:
            d = datetime.strptime(f["date"], "%Y-%m-%d").date()
            if 0 <= (d - t0).days <= 45:
                rows.append((d, f))
        if rows:
            out += ["| date | in days | festival | stories | verified |", "|---|---|---|---|---|"]
            for d, f in sorted(rows, key=lambda x: x[0]):
                out.append(f"| {d} | {(d - t0).days} | {f['name']} ({f.get('name_hi', '')}) | {'; '.join(f.get('related_stories', []))} | "
                           f"{'yes' if f.get('verified') else 'NO'} |")
        else:
            out.append("None in range.")
    except Exception as e:  # noqa: BLE001
        out.append(f"Calendar unavailable ({type(e).__name__}).")
    out += ["", "## Fit for Kathakaar (Claude)", "", ""]

    path = Path(a.out) if a.out else IDEAS / f"trends-{today_ist()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    log(f"wrote {path}")
    return 0


# ------------------------------------------------------------------ status
def cmd_status(_):
    con = db()
    last = meta_get(con, "last_scan_at")
    log(f"last scan: {last or 'never'} (IST date {meta_get(con, 'last_scan_date') or '-'})")
    log(f"units spent today ({today_ist()} IST): {spent_today(con)} / {DAILY_BUDGET} trends budget")
    for t in ("scans", "obs", "chart", "suggestions", "credits", "heat", "short_cache"):
        log(f"  {t}: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows")
    log(f"  rotation index: {meta_get(con, 'rotation_idx', 0)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_scan)
    d = sub.add_parser("digest")
    d.add_argument("--out")
    d.set_defaults(fn=cmd_digest)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = ap.parse_args()
    try:
        sys.exit(a.fn(a) or 0)
    except an.ApiError as e:
        sys.exit(f"API error: {e}")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"error: {yt.scrub(str(e))}")


if __name__ == "__main__":
    main()
