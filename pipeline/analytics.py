#!/usr/bin/env python3
"""YouTube + Instagram analytics collector for the Kathakaar channel (YouTube Data/Analytics APIs, Instagram Graph API). Standard library only.

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
                              Only public videos are snapshotted (private loop previews / unlisted are stored but
                              skipped); when a video turns public or its publishedAt moves, snapshots taken before
                              that time (and their retention/traffic rows) are deleted so the buckets restart.
  yt status [--limit N]       table of videos, newest first, with the latest numbers and the mapped episode
  yt map                      suggest episodes for unmapped public videos (difflib on titles, score >= 0.5);
                              private previews are skipped and --set refuses them until they are public
  yt map --set VIDEO_ID SLUG  / --unset VIDEO_ID: edit cache/analytics/episode_map.json (the user confirms mappings)
  yt export                   write episodes/<slug>/analytics/youtube.json for each mapped episode (also run by pull)

Instagram Reels (same DB; Graph API via the credentials in secrets/instagram.json, read-only):

  ig pull [--media ID] [--force] [--no-comments]
                              list every media item (GET /<ig-user-id>/media, paged), upsert `ig_media`, and for
                              media_product_type REELS take insight snapshots on the same age schedule as YouTube
                              (1h 6h 24h 72h 7d 14d 28d 90d once each + one `daily` per IST day under 90 days;
                              --force = `manual`). FEED/other media are stored without insights. Metrics per snapshot:
                              views, reach, likes, comments, shares, saved, total_interactions,
                              ig_reels_avg_watch_time (ms as returned; also stored in seconds),
                              ig_reels_video_view_total_time, reels_skip_rate, plus the live like/comment counters.
                              Metrics Meta rejects (HTTP 400 naming them) are dropped, retried and remembered in meta
                              `ig_unsupported_metrics`. Comments (and replies) are pulled until a known id is reached.
                              Idempotent; one failing media does not abort the run (exit 1 if any error).
  ig status [--limit N]       media table with the latest insights, the mapped episode and, when that episode also has
                              a YouTube video, its YouTube views next to the Instagram views
  ig map                      suggest episodes for unmapped media (caption first line vs title_en/title_hi, >= 0.5)
  ig map --set MEDIA_ID SLUG  / --unset MEDIA_ID: edit cache/analytics/ig_episode_map.json; episode.json
                              published.instagram.media_id wins over the map file
  ig export                   write episodes/<slug>/analytics/instagram.json (also run by `ig pull`)
  export                      YouTube and Instagram exports together

Instagram insights can lag up to 48 h after posting: an empty result means "no data yet" and is stored as NULL, never 0
(has_data = 0); `ig status` and the review pack show only snapshots with data. Meta rate limits: app/user budgets
surface as error codes 4, 17, 32 and 613 (and HTTP 429); the collector backs off 30 s then 90 s on those (2 s, 4 s on
5xx), retries 3 times, then reports the error for that media. A pull makes 1 list call per 50 media, plus
2-3 calls per snapshotted reel and 1+ per comment pull, far below Meta's per-hour limits.

Data lives in cache/analytics/ (git-ignored): analytics.sqlite (tables videos, snapshots, retention, traffic, daily,
comments, ig_media, ig_snapshots, ig_comments, followers, meta), episode_map.json and ig_episode_map.json. Timestamps are ISO-8601 UTC. Data API statistics are real-time; Analytics API
numbers lag 1-2 days: both are stored side by side on each snapshot (api_* vs an_*), never reconciled.
An episode.json with published.youtube.id maps automatically and wins over episode_map.json.

`followers pull` stores one row per platform per IST day in `followers` (YouTube subscriberCount, Instagram
followers_count); a second run the same day is a no-op.

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
import instagram_publish as igp  # noqa: E402
import youtube_publish as yt  # noqa: E402

LAB = yt.LAB
STORE = LAB / "cache" / "analytics"
DB_PATH = STORE / "analytics.sqlite"
MAP_PATH = STORE / "episode_map.json"
IG_MAP_PATH = STORE / "ig_episode_map.json"
EPISODES = LAB / "episodes"
IST = ZoneInfo("Asia/Kolkata")
SCHEMA_VERSION = 3          # 2 = adds the Instagram tables (ig_media, ig_snapshots, ig_comments); 3 = followers
IG_SECRETS = LAB / "secrets" / "instagram.json"

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

FOLLOWERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS followers (
  day TEXT NOT NULL, platform TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY (day, platform));  -- day = IST date
"""

IG_SCHEMA = """
CREATE TABLE IF NOT EXISTS ig_media (
  media_id TEXT PRIMARY KEY, caption TEXT, media_type TEXT, media_product_type TEXT, permalink TEXT, timestamp TEXT,
  thumbnail_url TEXT, like_count INTEGER, comments_count INTEGER, stats_at TEXT, episode_slug TEXT,
  first_seen TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS ig_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT, media_id TEXT NOT NULL, taken_at TEXT NOT NULL, day_ist TEXT NOT NULL,
  bucket TEXT NOT NULL, age_hours REAL,
  like_count INTEGER, comments_count INTEGER,                                      -- media fields (real time)
  views INTEGER, reach INTEGER, likes INTEGER, comments INTEGER, shares INTEGER, saved INTEGER,
  total_interactions INTEGER, avg_watch_ms REAL, avg_watch_s REAL, total_watch_ms REAL, skip_rate REAL,
  has_data INTEGER DEFAULT 0);                                                     -- insights (can lag 48 h); NULL = no data
CREATE INDEX IF NOT EXISTS ix_igsnap_media ON ig_snapshots(media_id, id);
CREATE TABLE IF NOT EXISTS ig_comments (
  id TEXT PRIMARY KEY, media_id TEXT NOT NULL, parent_id TEXT, username TEXT, text TEXT, like_count INTEGER,
  timestamp TEXT, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_igcom_media ON ig_comments(media_id, timestamp);
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
    con.executescript(SCHEMA + IG_SCHEMA + FOLLOWERS_SCHEMA)
    meta_set(con, "schema_version", str(SCHEMA_VERSION))
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


def preview_ids(eps: dict[str, dict]) -> set[str]:
    """Video ids recorded as the loop's private previews (episode.json published.youtube_preview.id)."""
    out = set()
    for ep in eps.values():
        vid = ((ep.get("published") or {}).get("youtube_preview") or {}).get("id")
        if vid:
            out.add(vid)
    return out


def is_public(row) -> bool:
    return row["privacy"] == "public"


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
    old = con.execute("SELECT is_short, short_method, privacy, published_at FROM videos WHERE video_id=?",
                      (vid,)).fetchone()
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
    privacy, published = v.get("status", {}).get("privacyStatus"), sn.get("publishedAt")
    if old and privacy == "public" and published and (old["privacy"] != "public" or old["published_at"] != published):
        purge_before(con, vid, published)


def purge_before(con, vid: str, published_at: str) -> int:
    """A video just went public (or its publish time moved): drop the snapshots taken before that time, with their
    retention and traffic rows, so the age buckets (1h, 6h, ...) restart from going public."""
    pub = parse_ts(published_at)
    old = [r["id"] for r in con.execute("SELECT id, taken_at FROM snapshots WHERE video_id=?", (vid,))
           if parse_ts(r["taken_at"]) < pub]
    for sid in old:
        con.execute("DELETE FROM retention WHERE snapshot_id=?", (sid,))
        con.execute("DELETE FROM traffic WHERE snapshot_id=?", (sid,))
        con.execute("DELETE FROM snapshots WHERE id=?", (sid,))
    return len(old)


# ------------------------------------------------------------------ snapshot schedule
def due_bucket(con, video_id: str, published_at: str, force: bool, table: str = "snapshots",
               col: str = "video_id") -> tuple[str | None, float]:
    pub = parse_ts(published_at)
    now = now_utc()
    age_h = (now - pub).total_seconds() / 3600
    if force:
        return "manual", age_h
    if age_h < 1:
        return None, age_h
    passed = [b for b in BUCKETS if age_h >= b[1]]
    latest = passed[-1][0]
    have = {r["bucket"] for r in con.execute(f"SELECT bucket FROM {table} WHERE {col}=?", (video_id,))}
    if latest not in have:
        return latest, age_h
    if age_h < DAILY_MAX_AGE_H:
        today = now.astimezone(IST).date().isoformat()
        if not con.execute(f"SELECT 1 FROM {table} WHERE {col}=? AND day_ist=?", (video_id, today)).fetchone():
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
            if not row["published_at"] or not is_public(row):
                continue  # private previews / unlisted: no snapshots, comments or series until public
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
            eps = load_episodes()
            if slug not in eps:
                sys.exit(f"unknown episode slug: {slug}")
            con = db()
            row = con.execute("SELECT privacy FROM videos WHERE video_id=?", (vid,)).fetchone()
            con.close()
            if (row and not is_public(row)) or (not row and vid in preview_ids(eps)):
                sys.exit(f"{vid} is not public yet (private preview or {row['privacy'] if row else 'unknown'}): "
                         f"not mapped; it maps itself once the publisher makes it public")
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
    # private previews (and rejected ones) are never suggested: they map themselves when the publisher makes them public
    hidden = [r for r in rows if r["video_id"] not in eff and not is_public(r)]
    unmapped = [r for r in rows if r["video_id"] not in eff and r not in hidden]
    print(f"{len(rows) - len(unmapped) - len(hidden)} mapped, {len(unmapped)} unmapped"
          + (f", {len(hidden)} not public yet (skipped)" if hidden else "") + "\n")
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


# ================================================================== Instagram
IG_METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
              "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate"]
IG_RATE_CODES = {4, 17, 32, 613}                 # Meta app/user/page/custom rate-limit error codes
IG_MEDIA_FIELDS = "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count,thumbnail_url"


class IgError(Exception):
    def __init__(self, status: int, code: int | None, body: str, url: str = ""):
        self.status, self.code, self.url = status, code, url.split("?")[0]
        self.body = igp.scrub(body or "")
        super().__init__(f"HTTP {status} code={code} {self.url}: {self.body[:300]}")

    @property
    def message(self) -> str:
        try:
            return json.loads(self.body)["error"].get("message", "")
        except Exception:
            return self.body


_ig_creds: dict | None = None


def ig_creds() -> dict:
    global _ig_creds
    if _ig_creds is None:
        _ig_creds = igp.load()               # SystemExit if no credentials; registers token for scrubbing
    return _ig_creds


def ig_get(path: str, params: dict | None = None) -> dict:
    """GET <host>/<ver>/<path> with the saved token. Retries 3x: 429/5xx/network with 2s, 4s backoff; Meta rate-limit
    codes (4, 17, 32, 613) with 30s, 90s. Raises IgError (scrubbed, no token) otherwise."""
    c = ig_creds()
    q = dict(params or {})
    q["access_token"] = c["access_token"]
    url = f"{igp.base(c)}/{igp.VERSION}/{path}"
    last: IgError | None = None
    for attempt in range(3):
        wait = 2 ** (attempt + 1)
        try:
            req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(q)}", method="GET")
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            try:
                code = json.loads(body)["error"].get("code")
            except Exception:
                code = None
            last = IgError(e.code, code, body, url)
            if code in IG_RATE_CODES:
                wait = 30 * 3 ** attempt
            elif e.code != 429 and e.code < 500:
                raise last
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = IgError(0, None, f"network error: {e}", url)
        if attempt < 2:
            time.sleep(wait)
    assert last is not None
    raise last


def parse_ig_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s.replace("Z", "+00:00"))
    return datetime.fromisoformat(s)


def ig_iso(s: str | None) -> str | None:
    d = parse_ig_ts(s)
    return iso(d) if d else None


def ig_media_list() -> list[dict]:
    c = ig_creds()
    out, after = [], None
    while True:
        p = {"fields": IG_MEDIA_FIELDS, "limit": 50}
        if after:
            p["after"] = after
        r = ig_get(f"{c['ig_user_id']}/media", p)
        out += r.get("data", [])
        after = ((r.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not (r.get("paging") or {}).get("next"):
            return out


def ig_upsert_media(con, m: dict, slug_map: dict[str, str]) -> None:
    now = iso(now_utc())
    con.execute("""
      INSERT INTO ig_media(media_id,caption,media_type,media_product_type,permalink,timestamp,thumbnail_url,
        like_count,comments_count,stats_at,episode_slug,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(media_id) DO UPDATE SET caption=excluded.caption, media_type=excluded.media_type,
        media_product_type=excluded.media_product_type, permalink=excluded.permalink, timestamp=excluded.timestamp,
        thumbnail_url=excluded.thumbnail_url, like_count=excluded.like_count, comments_count=excluded.comments_count,
        stats_at=excluded.stats_at, episode_slug=excluded.episode_slug, last_seen=excluded.last_seen""",
                (m["id"], m.get("caption"), m.get("media_type"), m.get("media_product_type"), m.get("permalink"),
                 ig_iso(m.get("timestamp")), m.get("thumbnail_url"), m.get("like_count"), m.get("comments_count"),
                 now, slug_map.get(m["id"]), now, now))


def ig_insights(con, media_id: str) -> dict:
    """{metric: value} for one media. A 400 naming metric(s) (by name or `metric[i]` index) drops them, remembers them
    in meta `ig_unsupported_metrics` and retries. Empty -> {} (no data yet; never 0)."""
    unsupported = set(json.loads(meta_get(con, "ig_unsupported_metrics", "[]")))
    wanted = [m for m in IG_METRICS if m not in unsupported]
    for _ in range(len(IG_METRICS) + 1):
        if not wanted:
            return {}
        try:
            r = ig_get(f"{media_id}/insights", {"metric": ",".join(wanted)})
            break
        except IgError as e:
            if e.status != 400:
                raise
            msg = e.message
            named = [m for m in wanted if re.search(rf"(?<![\w]){m}(?![\w])", msg)]
            named += [wanted[int(i)] for i in re.findall(r"metric\[(\d+)\]", msg)
                      if int(i) < len(wanted) and wanted[int(i)] not in named]
            if not named:
                if e.code == 100 and len(wanted) > 1:       # unnamed parameter error: find the culprits one by one
                    named = [m for m in wanted if not _ig_metric_ok(media_id, m)]
                if not named:
                    print(f"  warn: {media_id} insights unavailable: {e}", file=sys.stderr)
                    return {}
            unsupported |= set(named)
            meta_set(con, "ig_unsupported_metrics", json.dumps(sorted(unsupported)))
            print(f"  note: Instagram rejected metric(s) {named}; will stop requesting them", file=sys.stderr)
            wanted = [m for m in wanted if m not in named]
    else:
        return {}
    out = {}
    for d in r.get("data", []):
        v = (d.get("values") or [{}])[0].get("value")
        if v is None:
            v = (d.get("total_value") or {}).get("value")
        if isinstance(v, (int, float)):
            out[d["name"]] = v
    return out


def _ig_metric_ok(media_id: str, metric: str) -> bool:
    try:
        ig_get(f"{media_id}/insights", {"metric": metric})
        return True
    except IgError as e:
        return e.status != 400 or e.code != 100


def ig_take_snapshot(con, m: sqlite3.Row, bucket: str, age_h: float) -> int:
    mid = m["media_id"]
    st = ig_get(mid, {"fields": "like_count,comments_count"})        # real-time counters
    ins = ig_insights(con, mid) if m["media_product_type"] == "REELS" else {}
    taken = now_utc()
    ms = ins.get("ig_reels_avg_watch_time")
    toint = lambda x: int(x) if x is not None else None  # noqa: E731
    cur = con.execute(
        """INSERT INTO ig_snapshots(media_id,taken_at,day_ist,bucket,age_hours,like_count,comments_count,views,reach,
           likes,comments,shares,saved,total_interactions,avg_watch_ms,avg_watch_s,total_watch_ms,skip_rate,has_data)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (mid, iso(taken), taken.astimezone(IST).date().isoformat(), bucket, round(age_h, 2),
         st.get("like_count"), st.get("comments_count"), toint(ins.get("views")), toint(ins.get("reach")),
         toint(ins.get("likes")), toint(ins.get("comments")), toint(ins.get("shares")), toint(ins.get("saved")),
         toint(ins.get("total_interactions")), ms, ms / 1000 if ms is not None else None,
         ins.get("ig_reels_video_view_total_time"), ins.get("reels_skip_rate"), 1 if ins else 0))
    return cur.lastrowid


def ig_pull_comments(con, media_id: str) -> int:
    new, after, fetched = 0, None, iso(now_utc())
    fields = "id,text,username,like_count,timestamp,replies{id,text,username,like_count,timestamp}"
    while True:
        p = {"fields": fields, "limit": 50}
        if after:
            p["after"] = after
        r = ig_get(f"{media_id}/comments", p)
        hit_known = False
        for top in r.get("data", []):
            rows = [(top, None)] + [(c, top["id"]) for c in (top.get("replies") or {}).get("data", [])]
            if con.execute("SELECT 1 FROM ig_comments WHERE id=?", (top["id"],)).fetchone():
                hit_known = True
            for c, parent in rows:
                existed = con.execute("SELECT 1 FROM ig_comments WHERE id=?", (c["id"],)).fetchone()
                con.execute("""INSERT INTO ig_comments VALUES(?,?,?,?,?,?,?,?)
                  ON CONFLICT(id) DO UPDATE SET text=excluded.text, like_count=excluded.like_count,
                  username=excluded.username, fetched_at=excluded.fetched_at""",
                            (c["id"], media_id, parent, c.get("username"), c.get("text"), c.get("like_count", 0),
                             ig_iso(c.get("timestamp")), fetched))
                new += 0 if existed else 1
        after = ((r.get("paging") or {}).get("cursors") or {}).get("after")
        if hit_known or not after or not (r.get("paging") or {}).get("next"):
            return new


# ---- episode mapping
def load_ig_map() -> dict[str, str]:
    try:
        return json.loads(IG_MAP_PATH.read_text())
    except Exception:
        return {}


def effective_ig_map(eps: dict[str, dict]) -> dict[str, str]:
    m = dict(load_ig_map())
    for slug, ep in eps.items():                      # episode.json wins over the map file
        mid = ((ep.get("published") or {}).get("instagram") or {}).get("media_id")
        if mid:
            m[str(mid)] = ep.get("slug", slug)
    return m


def cmd_ig_pull(a):
    con = db()
    eps = load_episodes()
    slug_map = effective_ig_map(eps)
    errors, snaps, new_comments = [], {}, 0
    try:
        media = ig_media_list()
        if a.media:
            media = [m for m in media if m["id"] == a.media]
            if not media:
                sys.exit(f"media {a.media} not found on this account")
    except IgError as e:
        sys.exit(f"discovery failed: {e}")
    for m in media:
        try:
            ig_upsert_media(con, m, slug_map)
        except Exception as e:
            errors.append(f"{m.get('id')}: upsert: {igp.scrub(str(e))}")
    con.commit()
    for row in con.execute("SELECT * FROM ig_media" + (" WHERE media_id=?" if a.media else " ORDER BY timestamp DESC"),
                           (a.media,) if a.media else ()).fetchall():
        mid = row["media_id"]
        try:
            if not row["timestamp"] or row["media_product_type"] != "REELS":
                continue                                     # other media: row stored, no insights snapshot
            bucket, age_h = due_bucket(con, mid, row["timestamp"], a.force, "ig_snapshots", "media_id")
            first_comments = meta_get(con, f"ig_comments_done:{mid}") is None
            if bucket:
                ig_take_snapshot(con, row, bucket, age_h)
                snaps[bucket] = snaps.get(bucket, 0) + 1
            if not a.no_comments and (bucket or first_comments):
                new_comments += ig_pull_comments(con, mid)
                meta_set(con, f"ig_comments_done:{mid}", iso(now_utc()))
            con.commit()
        except Exception as e:
            con.rollback()
            msg = f"{mid}: {igp.scrub(str(e))}"[:300]
            errors.append(msg)
            print(f"  error: {msg}", file=sys.stderr)
    tot = con.execute("SELECT COUNT(*) c, COALESCE(SUM(media_product_type='REELS'),0) r FROM ig_media").fetchone()
    try:
        exported = ig_export_all(con, eps, slug_map)
    except Exception as e:
        exported = 0
        errors.append(f"export: {igp.scrub(str(e))}")
    print(f"instagram media: {len(media)} fetched ({tot['c']} stored, {tot['r']} reels)")
    print("snapshots: " + (", ".join(f"{k}={n}" for k, n in snaps.items()) if snaps else "none due"))
    print(f"new comments: {new_comments}")
    print(f"episodes exported: {exported}")
    print(f"errors: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    con.close()
    sys.exit(1 if errors else 0)


# ------------------------------------------------------------------ follower snapshots
def followers_pull(con, errors: list | None = None) -> dict[str, int]:
    """Record today's (IST) follower counts, one row per platform per day; a platform that already has today's row is
    not fetched again. Returns {platform: count} for every platform that has a row today. Instagram is skipped (with a
    log line) when secrets/instagram.json is missing. A failing platform is appended to `errors` and left out."""
    day = datetime.now(IST).strftime("%Y-%m-%d")
    have = {r["platform"]: r["count"] for r in con.execute("SELECT platform, count FROM followers WHERE day=?", (day,))}

    def yt_count() -> int:
        r = request(f"{yt.API}/channels", {"part": "statistics", "mine": "true"})
        return int(r["items"][0]["statistics"]["subscriberCount"])

    def ig_count() -> int:
        return int(ig_get(ig_creds()["ig_user_id"], {"fields": "followers_count"})["followers_count"])

    for platform, fetch in (("youtube", yt_count), ("instagram", ig_count)):
        if platform in have:
            continue
        if platform == "instagram" and not IG_SECRETS.exists():
            print("secrets/instagram.json missing: skipping Instagram followers")
            continue
        try:
            have[platform] = fetch()
        except (SystemExit, Exception) as e:
            msg = f"{platform} followers: {igp.scrub(str(e))}"[:300]
            if errors is None:
                raise
            errors.append(msg)
            continue
        con.execute("INSERT OR IGNORE INTO followers(day,platform,count) VALUES(?,?,?)", (day, platform, have[platform]))
        con.commit()
    return {p: have[p] for p in ("youtube", "instagram") if p in have}


def cmd_followers_pull(_):
    con = db()
    errors: list[str] = []
    counts = followers_pull(con, errors)
    for p in ("youtube", "instagram"):
        if p in counts:
            print(f"{p} followers: {counts[p]}")
    for e in errors:
        print(f"  error: {e}", file=sys.stderr)
    con.close()
    sys.exit(1 if errors else 0)


def yt_views_for(con, slug: str | None):
    """Latest YouTube view count of the episode's video(s), or None."""
    if not slug:
        return None
    r = con.execute("SELECT SUM(view_count) v, COUNT(*) n FROM videos WHERE episode_slug=?", (slug,)).fetchone()
    return r["v"] if r and r["n"] else None


def cmd_ig_status(a):
    con = db()
    slug_map = effective_ig_map(load_episodes())
    rows = con.execute("SELECT * FROM ig_media ORDER BY timestamp DESC LIMIT ?", (a.limit,)).fetchall()
    if not rows:
        sys.exit("no instagram media stored yet: run `ig pull` first")
    hdr = f"{'published':<10} {'kind':<6} {'age':>4} {'igviews':>7} {'reach':>6} {'avgs':>5} {'skip':>6} {'likes':>5} " \
          f"{'cmts':>4} {'shr':>4} {'sav':>4} {'ytviews':>7}  {'episode':<22} caption"
    print(hdr)
    print("-" * min(len(hdr) + 30, 150))
    now = now_utc()
    for r in rows:
        s = con.execute("SELECT * FROM ig_snapshots WHERE media_id=? AND has_data=1 ORDER BY id DESC LIMIT 1",
                        (r["media_id"],)).fetchone()
        slug = r["episode_slug"] or slug_map.get(r["media_id"])
        age = (now - parse_ts(r["timestamp"])).total_seconds() / 3600 if r["timestamp"] else 0
        kind = {"REELS": "reel", "FEED": "feed", "STORY": "story"}.get(r["media_product_type"], r["media_product_type"] or "?")
        first = (r["caption"] or "").strip().splitlines()[0] if (r["caption"] or "").strip() else ""
        ytv = yt_views_for(con, slug)
        g = (lambda k: s[k] if s else None)  # noqa: E731
        print(f"{(r['timestamp'] or '')[:10]:<10} {kind:<6} {human_age(age):>4} {fmt(g('views')):>7} "
              f"{fmt(g('reach')):>6} {fmt(g('avg_watch_s'), '{:.1f}'):>5} {fmt(g('skip_rate'), '{:.1f}'):>6} "
              f"{fmt(r['like_count']):>5} {fmt(r['comments_count']):>4} {fmt(g('shares')):>4} {fmt(g('saved')):>4} "
              f"{fmt(ytv):>7}  {(slug or '-')[:22]:<22} {trunc(first, 50)}")
    print("\nviews/reach/avgs(avg watch s)/skip/shr/sav come from the latest insights snapshot with data "
          "('-' = none yet; insights can lag up to 48 h); likes/cmts are the live media counters; "
          "ytviews = YouTube views of the same episode.")
    con.close()


def cmd_ig_map(a):
    if a.set or a.unset:
        m = load_ig_map()
        if a.set:
            mid, slug = a.set
            if slug not in load_episodes():
                sys.exit(f"unknown episode slug: {slug}")
            m[mid] = slug
            print(f"mapped {mid} -> {slug}")
        else:
            if m.pop(a.unset, None) is None:
                print(f"{a.unset} was not in the map file")
            else:
                print(f"unmapped {a.unset}")
        STORE.mkdir(parents=True, exist_ok=True)
        IG_MAP_PATH.write_text(json.dumps(dict(sorted(m.items())), indent=1, ensure_ascii=False) + "\n")
        con = db()
        eff = effective_ig_map(load_episodes())
        for mid in set(eff) | set(m):
            con.execute("UPDATE ig_media SET episode_slug=? WHERE media_id=?", (eff.get(mid), mid))
        con.commit()
        return
    con = db()
    eps = load_episodes()
    eff = effective_ig_map(eps)
    rows = con.execute("SELECT * FROM ig_media ORDER BY timestamp DESC").fetchall()
    unmapped = [r for r in rows if r["media_id"] not in eff]
    print(f"{len(rows) - len(unmapped)} mapped, {len(unmapped)} unmapped\n")
    norm = lambda s: " ".join(re.sub(r"#\S+", " ", (s or "").lower()).split())  # noqa: E731
    for r in unmapped:
        cap = (r["caption"] or "").strip()
        first = cap.splitlines()[0] if cap else ""
        best = (0.0, None, "")
        for slug, ep in eps.items():
            for key in ("title_en", "title_hi"):
                t = ep.get(key)
                if t:
                    sc = difflib.SequenceMatcher(None, norm(first), norm(t)).ratio()
                    if sc > best[0]:
                        best = (sc, ep.get("slug", slug), t)
        head = f"{r['media_id']}  {(r['timestamp'] or '')[:10]}  {r['media_product_type'] or '?'}  {trunc(first, 60)}"
        if best[1] and best[0] >= 0.5:
            print(f"{head}\n    -> {best[1]}  (score {best[0]:.2f}, matched \"{trunc(best[2], 50)}\")\n"
                  f"       python3 pipeline/analytics.py ig map --set {r['media_id']} {best[1]}")
        else:
            near = f"; closest {best[1]} at {best[0]:.2f}" if best[1] else ""
            print(f"{head}\n    -> no match >= 0.5{near}")
    con.close()


def ig_export_all(con, eps=None, slug_map=None) -> int:
    eps = eps if eps is not None else load_episodes()
    slug_map = slug_map if slug_map is not None else effective_ig_map(eps)
    by_slug: dict[str, list[str]] = {}
    for mid, slug in slug_map.items():
        if slug in eps and con.execute("SELECT 1 FROM ig_media WHERE media_id=?", (mid,)).fetchone():
            by_slug.setdefault(slug, []).append(mid)
    for slug, mids in by_slug.items():
        out = []
        for mid in mids:
            m = con.execute("SELECT * FROM ig_media WHERE media_id=?", (mid,)).fetchone()
            s = con.execute("SELECT * FROM ig_snapshots WHERE media_id=? ORDER BY id DESC LIMIT 1", (mid,)).fetchone()
            sa = con.execute("SELECT * FROM ig_snapshots WHERE media_id=? AND has_data=1 ORDER BY id DESC LIMIT 1",
                             (mid,)).fetchone()
            comments = [dict(r) for r in con.execute(
                "SELECT id, parent_id, username, text, like_count, timestamp FROM ig_comments "
                "WHERE media_id=? ORDER BY timestamp DESC LIMIT 20", (mid,))]
            out.append({
                "media_id": mid, "permalink": m["permalink"], "caption": m["caption"],
                "media_type": m["media_type"], "media_product_type": m["media_product_type"],
                "published_at": m["timestamp"],
                "latest_counters": {"likes": m["like_count"], "comments": m["comments_count"], "as_of": m["stats_at"]},
                "latest_snapshot": dict(s) if s else None, "latest_insights_snapshot": dict(sa) if sa else None,
                "comment_count_stored": con.execute("SELECT COUNT(*) c FROM ig_comments WHERE media_id=?",
                                                    (mid,)).fetchone()["c"],
                "recent_comments": comments})
        d = EPISODES / slug / "analytics"
        d.mkdir(parents=True, exist_ok=True)
        (d / "instagram.json").write_text(json.dumps(
            {"episode": slug, "exported_at": iso(now_utc()), "media": out}, indent=1, ensure_ascii=False) + "\n")
    return len(by_slug)


def cmd_ig_export(_):
    con = db()
    print(f"exported {ig_export_all(con)} episode(s)")


def cmd_export_all(_):
    con = db()
    print(f"youtube: exported {export_all(con)} episode(s)")
    print(f"instagram: exported {ig_export_all(con)} episode(s)")


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
    i = top.add_parser("ig", help="Instagram Reels").add_subparsers(dest="cmd", required=True)
    p = i.add_parser("pull")
    p.add_argument("--media")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-comments", action="store_true")
    p.set_defaults(f=cmd_ig_pull)
    p = i.add_parser("status")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(f=cmd_ig_status)
    p = i.add_parser("map")
    p.add_argument("--set", nargs=2, metavar=("MEDIA_ID", "SLUG"))
    p.add_argument("--unset", metavar="MEDIA_ID")
    p.set_defaults(f=cmd_ig_map)
    i.add_parser("export").set_defaults(f=cmd_ig_export)
    p = top.add_parser("followers", help="daily follower snapshots").add_subparsers(dest="cmd", required=True)
    p.add_parser("pull").set_defaults(f=cmd_followers_pull)
    top.add_parser("export", help="export YouTube and Instagram").set_defaults(f=cmd_export_all)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
