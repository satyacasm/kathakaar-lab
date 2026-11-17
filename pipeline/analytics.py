#!/usr/bin/env python3
"""YouTube analytics collector for the Kathakaar channel (Data API v3 + YouTube Analytics API). Standard library only.

Phase 1 of the feedback loop: collect clean, append-only performance data that later phases read. Read-only: it never
calls a write endpoint. Reuses the OAuth token from youtube_publish.py (scopes: youtube.force-ssl, yt-analytics.readonly).

  yt pull [--video ID] [--force] [--no-comments]
                              discover every upload on the channel (uploads playlist), upsert `videos`, detect
                              Short vs long (GET youtube.com/shorts/<id>, no redirects; 200 = Short; falls back to
                              duration <= 180 s), then take snapshots on an age schedule (1h 6h 24h 72h 7d 14d 28d 90d
                              = the latest bucket the video has passed, once; plus one `daily` per IST day while
                              younger than 90 days). --force snapshots everything now, tagged `manual`. Each snapshot
                              = Data API statistics + Analytics lifetime totals + retention curve + traffic sources;
                              it also refreshes the per-day series and new comments. Idempotent: safe from hourly cron.
  yt status [--limit N]       table of videos, newest first, with the latest numbers and the mapped episode
  yt map                      suggest episodes for unmapped videos (difflib on titles, score >= 0.5)
  yt map --set VIDEO_ID SLUG  / --unset VIDEO_ID: edit cache/analytics/episode_map.json (the user confirms mappings)
  yt export                   write episodes/<slug>/analytics/youtube.json for each mapped episode (also run by pull)

Data lives in cache/analytics/ (git-ignored): analytics.sqlite (tables videos, snapshots, retention, traffic, daily,
comments, meta) and episode_map.json. Timestamps are ISO-8601 UTC. Data API statistics are real-time; Analytics API
numbers lag 1-2 days: both are stored side by side on each snapshot (api_* vs an_*), never reconciled.
An episode.json with published.youtube.id maps automatically and wins over episode_map.json.

Quota: Data API channels/videos/playlistItems/commentThreads list calls cost 1 unit each (10,000/day free); the
Analytics API has its own separate quota. A pull makes ~4 Analytics calls per snapshotted video.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import youtube_publish as yt  # noqa: E402

LAB = yt.LAB
STORE = LAB / "cache" / "analytics"
DB_PATH = STORE / "analytics.sqlite"
MAP_PATH = STORE / "episode_map.json"
EPISODES = LAB / "episodes"
IST = ZoneInfo("Asia/Kolkata")
SCHEMA_VERSION = 1

BUCKETS = [("1h", 1), ("6h", 6), ("24h", 24), ("72h", 72), ("7d", 168), ("14d", 336), ("28d", 672), ("90d", 2160)]
DAILY_MAX_AGE_H = 90 * 24
SHORT_MAX_S = 180

AN_FULL = ["views", "engagedViews", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
           "likes", "comments", "shares", "subscribersGained", "subscribersLost"]
AN_CORE = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "likes", "shares",
           "subscribersGained"]
AN_COL = {"views": "an_views", "engagedViews": "an_engaged_views", "estimatedMinutesWatched": "an_minutes",
          "averageViewDuration": "an_avg_view_duration", "averageViewPercentage": "an_avg_view_pct",
          "likes": "an_likes", "comments": "an_comments", "shares": "an_shares",
          "subscribersGained": "an_subs_gained", "subscribersLost": "an_subs_lost"}
DAILY_METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "likes", "shares", "subscribersGained"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY, title TEXT, description TEXT, published_at TEXT, duration_s INTEGER,
  is_short INTEGER, short_method TEXT,            -- is_short 1/0; short_method 'shorts_url' | 'duration'
  privacy TEXT, category_id TEXT, tags TEXT, default_language TEXT, thumbnail_url TEXT,
  comments_disabled INTEGER DEFAULT 0, episode_slug TEXT,
  view_count INTEGER, like_count INTEGER, comment_count INTEGER, stats_at TEXT,   -- latest Data API statistics
  first_seen TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL, taken_at TEXT NOT NULL, day_ist TEXT NOT NULL,
  bucket TEXT NOT NULL,                           -- 1h 6h 24h 72h 7d 14d 28d 90d | daily | manual
  age_hours REAL,
  api_views INTEGER, api_likes INTEGER, api_comments INTEGER,                      -- Data API (real time)
  an_views INTEGER, an_engaged_views INTEGER, an_minutes REAL, an_avg_view_duration REAL, an_avg_view_pct REAL,
  an_likes INTEGER, an_comments INTEGER, an_shares INTEGER, an_subs_gained INTEGER, an_subs_lost INTEGER,
  an_start TEXT, an_end TEXT, an_has_data INTEGER DEFAULT 0);                       -- Analytics API (lags 1-2 days)
CREATE INDEX IF NOT EXISTS ix_snap_video ON snapshots(video_id, id);
CREATE TABLE IF NOT EXISTS retention (
  snapshot_id INTEGER NOT NULL, elapsed_ratio REAL NOT NULL, audience_watch_ratio REAL, relative_performance REAL,
  PRIMARY KEY (snapshot_id, elapsed_ratio));
CREATE TABLE IF NOT EXISTS traffic (
  snapshot_id INTEGER NOT NULL, source TEXT NOT NULL, views INTEGER, PRIMARY KEY (snapshot_id, source));
CREATE TABLE IF NOT EXISTS daily (
  video_id TEXT NOT NULL, day TEXT NOT NULL, views INTEGER, minutes REAL, avg_view_duration REAL, likes INTEGER,
  shares INTEGER, subs_gained INTEGER, fetched_at TEXT, PRIMARY KEY (video_id, day));
CREATE TABLE IF NOT EXISTS comments (
  comment_id TEXT PRIMARY KEY, video_id TEXT NOT NULL, parent_id TEXT, author TEXT, text TEXT, like_count INTEGER,
  published_at TEXT, updated_at TEXT, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_comments_video ON comments(video_id, published_at);
"""


# ------------------------------------------------------------------ helpers
class ApiError(Exception):
    def __init__(self, status: int, body: str, url: str = ""):
        self.status, self.body, self.url = status, yt.scrub(body or ""), url.split("?")[0]
        super().__init__(f"HTTP {status} {self.url}: {self.body[:300]}")

    @property
    def reason(self) -> str:
        try:
            return json.loads(self.body)["error"]["errors"][0]["reason"]
        except Exception:
            return ""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_duration(s: str | None) -> int | None:
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def request(url: str, params: dict | None = None) -> dict:
    """GET with auth. Retries 429/5xx/network errors 3 times; raises ApiError on any other HTTP error."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, method="GET", headers=yt.auth_headers())
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            err = ApiError(e.code, e.read().decode(errors="replace"), url)
            if e.code != 429 and e.code < 500:
                raise err
            last = err
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = ApiError(0, f"network error: {e}", url)
        if attempt < 2:
            time.sleep(2 ** (attempt + 1))
    assert last is not None
    raise last


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def check_short(video_id: str) -> bool | None:
    """True/False from the /shorts/ URL (200 = Short, redirect = not), None if the check failed."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(f"https://www.youtube.com/shorts/{video_id}", method="HEAD",
                                 headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(req, timeout=20) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            return False
        return None
    except Exception:
        return None


def db() -> sqlite3.Connection:
    STORE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    con.commit()
    return con


def meta_get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))


# ------------------------------------------------------------------ episode mapping
def load_episodes() -> dict[str, dict]:
    eps = {}
    for p in sorted(EPISODES.glob("*/episode.json")):
        try:
            eps[p.parent.name] = json.loads(p.read_text())
        except Exception:
            continue
    return eps


def load_map() -> dict[str, str]:
    try:
        return json.loads(MAP_PATH.read_text())
    except Exception:
        return {}


def effective_map(eps: dict[str, dict]) -> dict[str, str]:
    m = dict(load_map())
    for slug, ep in eps.items():                      # episode.json wins over the map file
        vid = ((ep.get("published") or {}).get("youtube") or {}).get("id")
        if vid:
            m[vid] = ep.get("slug", slug)
    return m


# ------------------------------------------------------------------ discovery
def discover_ids() -> list[str]:
    ch = request(f"{yt.API}/channels", {"part": "contentDetails", "mine": "true"})
    items = ch.get("items") or []
    if not items:
        raise ApiError(404, "no channel for this token")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if token:
            p["pageToken"] = token
        r = request(f"{yt.API}/playlistItems", p)
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            return list(dict.fromkeys(ids))


def fetch_videos(ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        r = request(f"{yt.API}/videos", {"part": "snippet,contentDetails,statistics,status",
                                         "id": ",".join(ids[i:i + 50]), "maxResults": 50})
        out += r.get("items", [])
    return out


def upsert_video(con, v: dict, slug_map: dict[str, str]) -> None:
    vid, sn, st = v["id"], v["snippet"], v.get("statistics", {})
    dur = parse_duration(v.get("contentDetails", {}).get("duration"))
    now = iso(now_utc())
    old = con.execute("SELECT is_short, short_method FROM videos WHERE video_id=?", (vid,)).fetchone()
    is_short, method = (old["is_short"], old["short_method"]) if old and old["is_short"] is not None else (None, None)
    if is_short is None:
        res = check_short(vid)
        if res is not None:
            is_short, method = int(res), "shorts_url"
        elif dur is not None:
            is_short, method = int(dur <= SHORT_MAX_S), "duration"
    thumbs = sn.get("thumbnails", {})
    thumb = (thumbs.get("high") or thumbs.get("default") or {}).get("url")
    toint = lambda x: int(x) if x is not None else None  # noqa: E731
    con.execute("""
      INSERT INTO videos(video_id,title,description,published_at,duration_s,is_short,short_method,privacy,category_id,
        tags,default_language,thumbnail_url,episode_slug,view_count,like_count,comment_count,stats_at,first_seen,last_seen)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(video_id) DO UPDATE SET title=excluded.title, description=excluded.description,
        published_at=excluded.published_at, duration_s=excluded.duration_s, is_short=excluded.is_short,
        short_method=excluded.short_method, privacy=excluded.privacy, category_id=excluded.category_id,
        tags=excluded.tags, default_language=excluded.default_language, thumbnail_url=excluded.thumbnail_url,
        episode_slug=excluded.episode_slug, view_count=excluded.view_count, like_count=excluded.like_count,
        comment_count=excluded.comment_count, stats_at=excluded.stats_at, last_seen=excluded.last_seen""",
                (vid, sn.get("title"), sn.get("description"), sn.get("publishedAt"), dur, is_short, method,
                 v.get("status", {}).get("privacyStatus"), sn.get("categoryId"),
                 json.dumps(sn.get("tags", []), ensure_ascii=False),
                 sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"), thumb, slug_map.get(vid),
                 toint(st.get("viewCount")), toint(st.get("likeCount")), toint(st.get("commentCount")), now, now, now))


# ------------------------------------------------------------------ snapshot schedule
def due_bucket(con, video_id: str, published_at: str, force: bool) -> tuple[str | None, float]:
    pub = parse_ts(published_at)
    now = now_utc()
    age_h = (now - pub).total_seconds() / 3600
    if force:
        return "manual", age_h
    if age_h < 1:
        return None, age_h
    passed = [b for b in BUCKETS if age_h >= b[1]]
    latest = passed[-1][0]
    have = {r["bucket"] for r in con.execute("SELECT bucket FROM snapshots WHERE video_id=?", (video_id,))}
    if latest not in have:
        return latest, age_h
    if age_h < DAILY_MAX_AGE_H:
        today = now.astimezone(IST).date().isoformat()
        if not con.execute("SELECT 1 FROM snapshots WHERE video_id=? AND day_ist=?", (video_id, today)).fetchone():
            return "daily", age_h
    return None, age_h


def analytics_report(video_id: str, start: str, end: str, metrics: list[str], dims: str | None = None,
                     extra: dict | None = None) -> tuple[list[str], list[list]]:
    p = {"ids": "channel==MINE", "filters": f"video=={video_id}", "startDate": start, "endDate": end,
         "metrics": ",".join(metrics)}
    if dims:
        p["dimensions"] = dims
    p.update(extra or {})
    r = request(yt.ANALYTICS, p)
    return [h["name"] for h in r.get("columnHeaders", [])], r.get("rows") or []


def lifetime_totals(con, video_id: str, start: str, end: str) -> dict:
    unsupported = set(json.loads(meta_get(con, "unsupported_metrics", "[]")))
    wanted = [m for m in AN_FULL if m not in unsupported]
    try:
        names, rows = analytics_report(video_id, start, end, wanted)
    except ApiError as e:
        if e.status != 400:
            raise
        named = [m for m in wanted if re.search(rf"\b{m}\b", e.body)]
        core = [m for m in AN_CORE if m not in unsupported and m not in named]
        if named:
            unsupported |= set(named)
            meta_set(con, "unsupported_metrics", json.dumps(sorted(unsupported)))
            print(f"  note: Analytics rejected metric(s) {named}; will stop requesting them", file=sys.stderr)
            retry = [m for m in wanted if m not in named]
        else:
            retry = core
        names, rows = analytics_report(video_id, start, end, retry)
    return dict(zip(names, rows[0])) if rows else {}


def take_snapshot(con, v: sqlite3.Row, bucket: str, age_h: float) -> int:
    vid = v["video_id"]
    api = request(f"{yt.API}/videos", {"part": "statistics", "id": vid}).get("items") or [{}]
    st = api[0].get("statistics", {})
    start = parse_ts(v["published_at"]).date().isoformat()
    end = now_utc().date().isoformat()
    if end < start:
        end = start
    tot = lifetime_totals(con, vid, start, end)
    taken = now_utc()
    toint = lambda x: int(x) if x is not None else None  # noqa: E731
    cols = {AN_COL[m]: tot.get(m) for m in AN_COL}
    cur = con.execute(
        f"""INSERT INTO snapshots(video_id,taken_at,day_ist,bucket,age_hours,api_views,api_likes,api_comments,
            {','.join(AN_COL.values())},an_start,an_end,an_has_data)
            VALUES(?,?,?,?,?,?,?,?,{','.join('?' * len(AN_COL))},?,?,?)""",
        (vid, iso(taken), taken.astimezone(IST).date().isoformat(), bucket, round(age_h, 2),
         toint(st.get("viewCount")), toint(st.get("likeCount")), toint(st.get("commentCount")),
         *cols.values(), start, end, 1 if tot else 0))
    sid = cur.lastrowid
    # retention curve + traffic sources: a failure here must not lose the snapshot
    for label, fn in (("retention", lambda: store_retention(con, sid, vid, start, end)),
                      ("traffic", lambda: store_traffic(con, sid, vid, start, end))):
        try:
            fn()
        except ApiError as e:
            print(f"  warn: {vid} {label}: {e}", file=sys.stderr)
    try:
        store_daily(con, vid, start, end)
    except ApiError as e:
        print(f"  warn: {vid} daily series: {e}", file=sys.stderr)
    return sid


def store_retention(con, sid, vid, start, end):
    names, rows = analytics_report(vid, start, end, ["audienceWatchRatio", "relativeRetentionPerformance"],
                                   dims="elapsedVideoTimeRatio", extra={"sort": "elapsedVideoTimeRatio"})
    con.executemany("INSERT OR REPLACE INTO retention VALUES(?,?,?,?)", [(sid, r[0], r[1], r[2]) for r in rows])


def store_traffic(con, sid, vid, start, end):
    names, rows = analytics_report(vid, start, end, ["views"], dims="insightTrafficSourceType",
                                   extra={"sort": "-views"})
    con.executemany("INSERT OR REPLACE INTO traffic VALUES(?,?,?)", [(sid, r[0], r[1]) for r in rows])


def store_daily(con, vid, start, end):
    names, rows = analytics_report(vid, start, end, DAILY_METRICS, dims="day", extra={"sort": "day"})
    fetched = iso(now_utc())
    con.executemany("INSERT OR REPLACE INTO daily VALUES(?,?,?,?,?,?,?,?,?)",
                    [(vid, r[0], *r[1:], fetched) for r in rows])


# ------------------------------------------------------------------ comments
def pull_comments(con, v: sqlite3.Row) -> int:
    vid = v["video_id"]
    if v["comments_disabled"]:
        return 0
    token, new, fetched = None, 0, iso(now_utc())
    while True:
        p = {"part": "snippet,replies", "videoId": vid, "maxResults": 100, "order": "time", "textFormat": "plainText"}
        if token:
            p["pageToken"] = token
        try:
            r = request(f"{yt.API}/commentThreads", p)
        except ApiError as e:
            if e.status == 403 and e.reason == "commentsDisabled":
                con.execute("UPDATE videos SET comments_disabled=1 WHERE video_id=?", (vid,))
                return new
            raise
        hit_known = False
        for th in r.get("items", []):
            top = th["snippet"]["topLevelComment"]
            rows = [(top, None)] + [(c, top["id"]) for c in th.get("replies", {}).get("comments", [])]
            if con.execute("SELECT 1 FROM comments WHERE comment_id=?", (top["id"],)).fetchone():
                hit_known = True
            for c, parent in rows:
                s = c["snippet"]
                existed = con.execute("SELECT 1 FROM comments WHERE comment_id=?", (c["id"],)).fetchone()
                con.execute("""INSERT INTO comments VALUES(?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(comment_id) DO UPDATE SET text=excluded.text, like_count=excluded.like_count,
                  updated_at=excluded.updated_at, author=excluded.author, fetched_at=excluded.fetched_at""",
                            (c["id"], vid, parent, s.get("authorDisplayName"), s.get("textDisplay"),
                             s.get("likeCount", 0), s.get("publishedAt"), s.get("updatedAt"), fetched))
                new += 0 if existed else 1
        token = r.get("nextPageToken")
        if hit_known or not token:
            return new


# ------------------------------------------------------------------ pull
def cmd_pull(a):
    con = db()
    eps = load_episodes()
    slug_map = effective_map(eps)
    errors, snaps, new_comments = [], {}, 0
    try:
        ids = [a.video] if a.video else discover_ids()
        vids = fetch_videos(ids)
    except ApiError as e:
        sys.exit(f"discovery failed: {e}")
    for v in vids:
        try:
            upsert_video(con, v, slug_map)
        except Exception as e:
            errors.append(f"{v.get('id')}: upsert: {yt.scrub(str(e))}")
    con.commit()
    if a.video and not vids:
        sys.exit(f"video {a.video} not found on this channel")
    for row in con.execute("SELECT * FROM videos" + (" WHERE video_id=?" if a.video else " ORDER BY published_at DESC"),
                           (a.video,) if a.video else ()).fetchall():
        vid = row["video_id"]
        try:
            if not row["published_at"]:
                continue
            bucket, age_h = due_bucket(con, vid, row["published_at"], a.force)
            first_comments = meta_get(con, f"comments_done:{vid}") is None
            if bucket:
                take_snapshot(con, row, bucket, age_h)
                snaps[bucket] = snaps.get(bucket, 0) + 1
            if not a.no_comments and (bucket or first_comments):
                new_comments += pull_comments(con, con.execute("SELECT * FROM videos WHERE video_id=?", (vid,)).fetchone())
                meta_set(con, f"comments_done:{vid}", iso(now_utc()))
            con.commit()
        except Exception as e:
            con.rollback()
            msg = f"{vid}: {yt.scrub(str(e))}"[:300]
            errors.append(msg)
            print(f"  error: {msg}", file=sys.stderr)
    total = con.execute("SELECT COUNT(*) c, COALESCE(SUM(is_short),0) s FROM videos").fetchone()
    try:
        exported = export_all(con, eps, slug_map)
    except Exception as e:
        exported = 0
        errors.append(f"export: {yt.scrub(str(e))}")
    print(f"videos: {len(vids)} fetched ({total['c']} stored, {total['s']} shorts)")
    print("snapshots: " + (", ".join(f"{k}={n}" for k, n in snaps.items()) if snaps else "none due"))
    print(f"new comments: {new_comments}")
    print(f"episodes exported: {exported}")
    print(f"errors: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    con.close()
    sys.exit(1 if errors else 0)


# ------------------------------------------------------------------ status
def width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 0 if unicodedata.combining(c) else 1 for c in s)


def trunc(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    return s[:n - 1] + "…"


def human_age(h: float) -> str:
    if h < 0:
        return "sched"
    if h < 48:
        return f"{h:.0f}h"
    return f"{h / 24:.0f}d"


def fmt(x, spec="{:.0f}"):
    return "-" if x is None else spec.format(x)


def cmd_status(a):
    con = db()
    slug_map = effective_map(load_episodes())
    rows = con.execute("SELECT * FROM videos ORDER BY published_at DESC LIMIT ?", (a.limit,)).fetchall()
    if not rows:
        sys.exit("no videos stored yet: run `yt pull` first")
    hdr = f"{'published':<10} {'kind':<5} {'age':>4} {'views':>7} {'avg%':>5} {'avgdur':>6} {'shares':>6} {'subs':>5} " \
          f"{'cmts':>5}  {'episode':<22} title"
    print(hdr)
    print("-" * min(len(hdr) + 30, 140))
    now = now_utc()
    for r in rows:
        s = con.execute("SELECT * FROM snapshots WHERE video_id=? AND an_has_data=1 ORDER BY id DESC LIMIT 1",
                        (r["video_id"],)).fetchone()
        ncom = con.execute("SELECT COUNT(*) c FROM comments WHERE video_id=?", (r["video_id"],)).fetchone()["c"]
        age = (now - parse_ts(r["published_at"])).total_seconds() / 3600
        kind = "short" if r["is_short"] else "long" if r["is_short"] == 0 else "?"
        print(f"{r['published_at'][:10]:<10} {kind:<5} {human_age(age):>4} {fmt(r['view_count']):>7} "
              f"{fmt(s and s['an_avg_view_pct'], '{:.0f}%'):>5} {fmt(s and s['an_avg_view_duration'], '{:.0f}s'):>6} "
              f"{fmt(s and s['an_shares']):>6} {fmt(s and s['an_subs_gained']):>5} {ncom:>5}  "
              f"{(r['episode_slug'] or slug_map.get(r['video_id']) or '-')[:22]:<22} {trunc(r['title'], 52)}")
    con.close()


# ------------------------------------------------------------------ map
def cmd_map(a):
    if a.set or a.unset:
        m = load_map()
        if a.set:
            vid, slug = a.set
            if slug not in load_episodes():
                sys.exit(f"unknown episode slug: {slug}")
            m[vid] = slug
            print(f"mapped {vid} -> {slug}")
        else:
            if m.pop(a.unset, None) is None:
                print(f"{a.unset} was not in the map file")
            else:
                print(f"unmapped {a.unset}")
        STORE.mkdir(parents=True, exist_ok=True)
        MAP_PATH.write_text(json.dumps(dict(sorted(m.items())), indent=1, ensure_ascii=False) + "\n")
        con = db()
        eps = load_episodes()
        eff = effective_map(eps)
        for vid in {k for k in list(eff) + list(m)}:
            con.execute("UPDATE videos SET episode_slug=? WHERE video_id=?", (eff.get(vid), vid))
        con.commit()
        return
    con = db()
    eps = load_episodes()
    eff = effective_map(eps)
    rows = con.execute("SELECT * FROM videos ORDER BY published_at DESC").fetchall()
    unmapped = [r for r in rows if r["video_id"] not in eff]
    print(f"{len(rows) - len(unmapped)} mapped, {len(unmapped)} unmapped\n")
    norm = lambda s: " ".join((s or "").lower().replace("#shorts", "").split())  # noqa: E731
    for r in unmapped:
        best = (0.0, None, "")
        for slug, ep in eps.items():
            for key in ("title_en", "title_hi"):
                t = ep.get(key)
                if t:
                    sc = difflib.SequenceMatcher(None, norm(r["title"]), norm(t)).ratio()
                    if sc > best[0]:
                        best = (sc, ep.get("slug", slug), t)
        head = f"{r['video_id']}  {r['published_at'][:10]}  {trunc(r['title'], 60)}"
        if best[1] and best[0] >= 0.5:
            print(f"{head}\n    -> {best[1]}  (score {best[0]:.2f}, matched \"{trunc(best[2], 50)}\")\n"
                  f"       python3 pipeline/analytics.py yt map --set {r['video_id']} {best[1]}")
        else:
            near = f"; closest {best[1]} at {best[0]:.2f}" if best[1] else ""
            print(f"{head}\n    -> no match >= 0.5{near}")
    con.close()


# ------------------------------------------------------------------ export
def export_all(con, eps=None, slug_map=None) -> int:
    eps = eps if eps is not None else load_episodes()
    slug_map = slug_map if slug_map is not None else effective_map(eps)
    by_slug: dict[str, list[str]] = {}
    for vid, slug in slug_map.items():
        if slug in eps and con.execute("SELECT 1 FROM videos WHERE video_id=?", (vid,)).fetchone():
            by_slug.setdefault(slug, []).append(vid)
    for slug, vids in by_slug.items():
        out = []
        for vid in vids:
            v = con.execute("SELECT * FROM videos WHERE video_id=?", (vid,)).fetchone()
            s = con.execute("SELECT * FROM snapshots WHERE video_id=? ORDER BY id DESC LIMIT 1", (vid,)).fetchone()
            sa = con.execute("SELECT * FROM snapshots WHERE video_id=? AND an_has_data=1 ORDER BY id DESC LIMIT 1",
                             (vid,)).fetchone()
            ret = traffic = []
            if sa:
                ret = [dict(r) for r in con.execute(
                    "SELECT elapsed_ratio, audience_watch_ratio, relative_performance FROM retention "
                    "WHERE snapshot_id=? ORDER BY elapsed_ratio", (sa["id"],))]
                traffic = [dict(r) for r in con.execute(
                    "SELECT source, views FROM traffic WHERE snapshot_id=? ORDER BY views DESC", (sa["id"],))]
            comments = [dict(r) for r in con.execute(
                "SELECT comment_id, parent_id, author, text, like_count, published_at FROM comments "
                "WHERE video_id=? ORDER BY published_at DESC LIMIT 20", (vid,))]
            out.append({
                "video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": v["title"],
                "published_at": v["published_at"], "is_short": bool(v["is_short"]) if v["is_short"] is not None else None,
                "duration_s": v["duration_s"], "privacy": v["privacy"],
                "latest_data_api": {"views": v["view_count"], "likes": v["like_count"],
                                    "comments": v["comment_count"], "as_of": v["stats_at"]},
                "latest_snapshot": dict(s) if s else None,
                "latest_analytics_snapshot": dict(sa) if sa else None,
                "retention_curve": ret, "traffic_sources": traffic,
                "comment_count_stored": con.execute("SELECT COUNT(*) c FROM comments WHERE video_id=?",
                                                    (vid,)).fetchone()["c"],
                "recent_comments": comments})
        d = EPISODES / slug / "analytics"
        d.mkdir(parents=True, exist_ok=True)
        (d / "youtube.json").write_text(json.dumps(
            {"episode": slug, "exported_at": iso(now_utc()), "videos": out}, indent=1, ensure_ascii=False) + "\n")
    return len(by_slug)


def cmd_export(_):
    con = db()
    print(f"exported {export_all(con)} episode(s)")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    top = ap.add_subparsers(dest="platform", required=True)
    y = top.add_parser("yt", help="YouTube").add_subparsers(dest="cmd", required=True)
    p = y.add_parser("pull")
    p.add_argument("--video")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-comments", action="store_true")
    p.set_defaults(f=cmd_pull)
    p = y.add_parser("status")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(f=cmd_status)
    p = y.add_parser("map")
    p.add_argument("--set", nargs=2, metavar=("VIDEO_ID", "SLUG"))
    p.add_argument("--unset", metavar="VIDEO_ID")
    p.set_defaults(f=cmd_map)
    y.add_parser("export").set_defaults(f=cmd_export)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
