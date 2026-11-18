#!/usr/bin/env python3
"""Deterministic helper for the overnight producer (headless Claude follows pipeline/loop/produce_prompt.md).

  produce.py start [--slug-hint WORDS] [--now ISO]   take the next plan row, scaffold the episode, queue it
        prints one of: START <id> <format> <audio> <topic_source>  |  STOP time|buffer|max|plan
  produce.py finish <id>                 check the package, build out/qa/frames.png, upload a PRIVATE YouTube
                                         preview, status preview_ready; prints READY <id> <yt_id>
  produce.py fail <id> --reason "..."    status failed + INBOX failure line
  produce.py fallback <id> --reason ".." switch the video to the 0-credit narrated format (over cap, no song)
  produce.py sweep [--reason "..."]      every video still producing -> failed (run.sh, after the Claude run)
  produce.py clock <id>                  minutes this video has been producing, of its 75-minute budget
  produce.py frames <id>                 only build out/qa/frames.png (1 frame per second contact sheet)
  produce.py voice-timing <id>           voice/review_hi/picks.json -> voice/picks_hi.json + timing_hi.json
  produce.py can-spend <credits>         OK, or NO <reason> (exit 1): loop cap and monthly cap
  produce.py spend <id> <credits> --job J [--what audio]   log a non-hero purchase (generate_audio) in the ledger
  produce.py fetch <id> <https-url> <dest>   download a Higgsfield result into the episode
        dest: out/hero_raw/cNN.mp4 or audio/original*.{mp3,wav,m4a}
  produce.py put <id> <file> <https-upload-url>   PUT an episode still (out/keyframes/*.png, refs/*.png) to the
        upload URL that Higgsfield media_upload returned

Stops: 06:00-12:00 IST (`time`), 4+ videos in preview_ready/approved (`buffer`), $LOOP_MAX_VIDEOS (default 4)
started since $LOOP_RUN_START (`max`), no open plan row (`plan`). Plan: --plan, $PLAN_PATH or ideas/experiment_plan.md.
Never publishes: the upload is always youtube_publish.py publish --preview (private).
"""
import argparse, json, math, os, re, shutil, subprocess, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inbox, plan, vqueue
from vqueue import TZ, one_line

LAB = vqueue.LAB
EPISODES = LAB / "episodes"
NEW_REEL = LAB / "pipeline/new_reel.sh"
YT_PUBLISH = LAB / "pipeline/youtube_publish.py"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

BUFFER_TARGET = 4
BUFFER_STATUSES = ("preview_ready", "approved")
STOP_HOURS = (6, 12)              # [06:00, 12:00) IST: the night run is over
DEFAULT_MAX = 4
UPLOAD_TIMEOUT = 1800
VIDEO_MINUTES = 75             # per-video budget the prompt holds the producer to
FALLBACK_CELL = ("narrated", "bed")
KIND = {"narrated": "narrated_reel", "claim": "claim_reel"}   # music/shloka/dialogue stay music_reel
PACKAGE = ("out/final/reel_with_song.mp4", "out/package/youtube.md", "out/package/caption_instagram.txt")
# the art style is never named in public copy
STYLE_WORDS = ("watercolor", "watercolour", "pattachitra", "ink wash", "ink-wash", "art style", "house style",
               "painting style")
SHEET_COLS, SHEET_W = 8, 240
LEAD_IN, TAIL, DEFAULT_PAUSE = 0.4, 1.5, 0.8
FETCH_MAX = 400 * 1024 * 1024
FETCH_DEST = re.compile(r"^(out/hero_raw/c\d{2}\.mp4|audio/original[a-z0-9_-]*\.(mp3|wav|m4a))$")
PUT_SRC = re.compile(r"^(out/keyframes|refs)/[A-Za-z0-9_-]+\.(png|jpg|jpeg)$")


class ProduceError(Exception):
    pass


def _run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], **kw)


def _can_spend(amount, month):
    from reel import budget
    return budget.can_spend(amount, month, budget.queue_ids())


def _popular_available():
    import audio_pool
    return bool(audio_pool.list_tracks("popular"))


def _ist(now):
    return (now or datetime.now(TZ)).astimezone(TZ)


def _ts(rec, status):
    """Time the record last entered `status`, or None."""
    for t, s in reversed(rec.get("history", [])):
        if s == status:
            return datetime.fromisoformat(t)
    return None


def _ep(record_id) -> Path:
    if not re.fullmatch(r"\d{3}-[a-z0-9-]+", record_id):
        raise ProduceError(f"not a loop episode id: {record_id!r}")
    return Path(EPISODES) / record_id


def _record(record_id):
    for r in vqueue.load():
        if r["id"] == record_id:
            return r
    raise ProduceError(f"no queue record {record_id!r}")


def _edit_episode(ep: Path, **fields):
    p = ep / "episode.json"
    d = json.loads(p.read_text())
    d.update(fields)
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def _kind_fields(fmt, audio):
    return {"kind": KIND.get(fmt, "music_reel"), "format": KIND.get(fmt, "music_reel"),
            "narration": fmt in KIND}


# ---------------------------------------------------------------- start

def next_number(episodes=None) -> int:
    nums = [int(p.name[:3]) for p in Path(episodes or EPISODES).iterdir()
            if p.is_dir() and re.match(r"^\d{3}-", p.name) and int(p.name[:3]) < 900]
    return max(nums, default=0) + 1


def slugify(words) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (words or "").lower()).strip("-")
    return s[:40].strip("-")


def _topic(fmt, now, hint) -> str:
    s = slugify(hint)
    if s:
        return s
    stem = f"loop-{fmt}-{now:%Y%m%d}"
    taken = [p.name for p in Path(EPISODES).iterdir()] + [r["id"] for r in vqueue.load()]
    k = 1
    while any(t.endswith(f"-{stem}-{k}") for t in taken):
        k += 1
    return f"{stem}-{k}"


def sweep(before=None, reason="interrupted: the producer run ended before finish") -> list:
    """Records still producing (all, or those that started producing before `before`) become failed + INBOX line.
    run.sh calls it after the Claude run ends (06:00 alarm, crash); start() calls it for earlier runs' leftovers."""
    done = []
    for r in vqueue.load():
        ts = _ts(r, "producing")
        if r["status"] == "producing" and (before is None or ts is None or ts < before):
            vqueue.transition(r["id"], "failed", reason=one_line(reason))
            inbox.add(f"Producer: {r['id']} failed: {one_line(reason)} (see cache/loop/logs/produce-*.log)", "failure")
            done.append(r["id"])
    return done


def start(now=None, plan_path=None, slug_hint=None, max_videos=None, run_start=None) -> str:
    now = _ist(now)
    if STOP_HOURS[0] <= now.hour < STOP_HOURS[1]:
        return "STOP time"
    run_start = run_start or now - timedelta(hours=12)
    sweep(before=run_start)
    records = vqueue.load()
    open_ = [r["id"] for r in records if r["status"] == "producing"]
    if open_:
        raise ProduceError(f"{', '.join(open_)} is still producing: run `produce.py finish` or `produce.py fail` first")
    if sum(r["status"] in BUFFER_STATUSES for r in records) >= BUFFER_TARGET:
        return "STOP buffer"
    max_videos = DEFAULT_MAX if max_videos is None else max_videos
    started = sum(1 for r in records if (_ts(r, "producing") or datetime.min.replace(tzinfo=TZ)) >= run_start)
    if started >= max_videos:
        return "STOP max"
    plan_path = Path(plan_path or os.environ.get("PLAN_PATH") or plan.PLAN_PATH)
    rows = plan.read(plan_path)
    row = plan.next_row(rows, records)
    if row is None:
        return "STOP plan"

    fmt, audio, topic = row["format"], row["audio"], row["topic_source"]
    cell = {"format": fmt, "audio": audio, "topic_source": topic, "day": row["day"], "slot": row["slot"]}
    note = None
    cost = plan.row_cost(row)
    if audio == "popular" and not _popular_available():
        note = ("decision", f"no popular song in music-lab/pool/popular/ for a {fmt} reel: supply one; "
                            "this video was made as a narrated Short instead")
    elif cost > 0:
        ok, why = _can_spend(cost, now.strftime("%Y-%m"))
        if not ok:
            note = ("info", f"{fmt}/{audio} needs ~{cost:g} credits ({why}); made as a narrated Short instead")
    if note:
        cell.update(planned=f"{fmt}/{audio}", format=FALLBACK_CELL[0], audio=FALLBACK_CELL[1])

    rid = f"{next_number():03d}-{_topic(cell['format'], now, slug_hint)}"
    ep = Path(EPISODES) / rid
    r = _run([NEW_REEL, rid], capture_output=True, text=True)
    if r.returncode != 0 or not (ep / "episode.json").exists():
        raise ProduceError(f"new_reel.sh {rid} failed: {(r.stderr or r.stdout or '').strip()[-300:]}")
    song = json.loads((ep / "episode.json").read_text()).get("song") or {}
    song["add_in_app"] = cell["audio"] == "popular"
    _edit_episode(ep, song=song, platforms=["instagram", "youtube"], loop=dict(cell),
                  **_kind_fields(cell["format"], cell["audio"]))
    ig_mode = "manual" if cell["audio"] == "popular" else "api"
    vqueue.add(rid, cell, ig_mode)
    vqueue.transition(rid, "producing")
    for x in rows:
        if x["day"] == row["day"] and x["slot"] == row["slot"]:
            x["id"] = rid
    plan.write(rows, plan_path)
    if note:
        inbox.add(f"Producer {rid}: {note[1]}", note[0])
    return f"START {rid} {cell['format']} {cell['audio']} {topic}"


# ---------------------------------------------------------------- finish

def _duration(path) -> float:
    r = _run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
             capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise ProduceError(f"ffprobe could not read {path}: {(r.stderr or '').strip()[-200:]}")


def frames(record_id) -> Path:
    """out/qa/frames.png: one frame per second of the preview, 8 per row, for Claude to inspect."""
    ep = _ep(record_id)
    video = ep / PACKAGE[0]
    if not video.exists():
        raise ProduceError(f"missing {PACKAGE[0]}")
    n = max(1, math.ceil(_duration(video)))
    out = ep / "out/qa/frames.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = min(SHEET_COLS, n)
    vf = f"fps=1,scale={SHEET_W}:-2,tile={cols}x{math.ceil(n / cols)}:padding=4:color=white"
    r = _run([FFMPEG, "-y", "-v", "error", "-i", video, "-vf", vf, "-frames:v", "1", out],
             capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise ProduceError(f"ffmpeg contact sheet failed: {(r.stderr or '').strip()[-300:]}")
    return out


def check_copy(ep: Path):
    words = list(STYLE_WORDS)
    try:
        style = json.loads((ep / "script/shots.json").read_text()).get("style") or ""
        if style:
            words.append(style.replace("_", " ").lower())
    except (OSError, ValueError):
        pass
    for rel in PACKAGE[1:]:
        text = (ep / rel).read_text(encoding="utf-8").lower()
        hits = sorted({w for w in words if w in text})
        if hits:
            raise ProduceError(f"{rel} names the art style ({', '.join(hits)}): public copy never names it")


def finish(record_id) -> str:
    rec = _record(record_id)
    if rec["status"] != "producing":
        raise ProduceError(f"{record_id} is {rec['status']}; only a producing video can be finished")
    ep = _ep(record_id)
    need = list(PACKAGE) + (["out/final/reel_SILENT.mp4"] if rec.get("ig_mode") == "manual" else [])
    missing = [p for p in need if not (ep / p).is_file()]
    if missing:
        raise ProduceError(f"{record_id}: missing {', '.join(missing)}")
    check_copy(ep)
    frames(record_id)
    try:
        r = _run([sys.executable, YT_PUBLISH, "publish", record_id, "--video", "reel_with_song.mp4", "--preview"],
                 capture_output=True, text=True, timeout=UPLOAD_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise ProduceError(f"{record_id}: private YouTube upload timed out after {UPLOAD_TIMEOUT} s")
    ids = [l.split("=", 1)[1].strip() for l in (r.stdout or "").splitlines() if l.startswith("preview_id=")]
    if r.returncode != 0 or not ids or not ids[-1]:
        tail = ((r.stderr or "") + (r.stdout or "")).strip()[-400:]
        raise ProduceError(f"{record_id}: private YouTube upload failed (exit {r.returncode}): {tail}")
    yt_id = ids[-1]
    vqueue.transition(record_id, "preview_ready", yt_id=yt_id, credits=_credits(ep))
    return f"READY {record_id} {yt_id}"


def _credits(ep: Path) -> float:
    try:
        from reel import budget
        return float(budget.episode_spent(budget.load_ledger(ep), ep.name))
    except Exception:
        return 0.0


# ---------------------------------------------------------------- fail / fallback

def fail(record_id, reason) -> str:
    rec = _record(record_id)
    reason = one_line(reason)
    if rec["status"] != "failed":
        vqueue.transition(record_id, "failed", reason=reason)
    inbox.add(f"Producer failed {record_id} ({rec['cell'].get('format')}/{rec['cell'].get('audio')}): {reason}",
              "failure")
    return f"FAILED {record_id}"


def fallback(record_id, reason) -> str:
    rec = _record(record_id)
    if rec["status"] != "producing":
        raise ProduceError(f"{record_id} is {rec['status']}; only a producing video can change format")
    cell = dict(rec["cell"])
    if (cell.get("format"), cell.get("audio")) != FALLBACK_CELL:
        cell.setdefault("planned", f"{cell.get('format')}/{cell.get('audio')}")
        cell.update(format=FALLBACK_CELL[0], audio=FALLBACK_CELL[1])
    vqueue.update(record_id, cell=cell, ig_mode="api")
    ep = _ep(record_id)
    d = json.loads((ep / "episode.json").read_text())
    song = d.get("song") or {}
    song["add_in_app"] = False
    _edit_episode(ep, song=song, loop=cell, **_kind_fields(*FALLBACK_CELL))
    inbox.add(f"Producer {record_id}: {cell['planned']} -> narrated Short ({one_line(reason)})", "info")
    return f"FALLBACK {record_id} {FALLBACK_CELL[0]} {FALLBACK_CELL[1]}"


# ---------------------------------------------------------------- helpers for the creative steps

def voice_timing(record_id) -> str:
    """Lay the picked Hindi takes end to end (lead-in 0.4 s, each line's pause_after, default 0.8 s) and write
    voice/picks_hi.json and timing_hi.json in the shape narration.py reads."""
    ep = _ep(record_id)
    picks = {str(k): v for k, v in json.loads((ep / "voice/review_hi/picks.json").read_text()).items()}
    pause = {str(k): float(v) for k, v in
             json.loads((ep / "script/lines.json").read_text()).get("pause_after", {}).items()}
    t, lines = LEAD_IN, []
    for n in sorted(picks, key=int):
        take = ep / "voice/takes_hi" / picks[n]
        if not take.is_file():
            raise ProduceError(f"missing take {take.relative_to(ep)}")
        d = _duration(take)
        p = pause.get(n, DEFAULT_PAUSE)
        lines.append({"line": int(n), "start": round(t, 3), "end": round(t + d, 3), "pause_after": p})
        t += d + p
    if not lines:
        raise ProduceError("voice/review_hi/picks.json has no picks")
    total = round(lines[-1]["end"] + TAIL, 3)
    (ep / "voice/picks_hi.json").write_text(json.dumps({"takes_dir": "voice/takes_hi", "picks": picks}, indent=1) + "\n")
    (ep / "timing_hi.json").write_text(json.dumps({"lead_in": LEAD_IN, "total": total, "lines": lines}, indent=1) + "\n")
    return f"timing_hi.json: {len(lines)} lines, voice ends at {lines[-1]['end']} s (mix will be ~{total} s)"


def clock(record_id, now=None) -> str:
    now = _ist(now)
    rec = _record(record_id)
    t0 = _ts(rec, "producing")
    mins = int((now - t0).total_seconds() // 60) if t0 else 0
    return (f"now {now:%H:%M} IST; {record_id} {rec['status']} for {mins} min of {VIDEO_MINUTES}"
            f" ({max(0, VIDEO_MINUTES - mins)} left)")


def can_spend(amount, now=None) -> tuple:
    return _can_spend(float(amount), _ist(now).strftime("%Y-%m"))


def spend(record_id, amount, job, now=None, what="audio") -> str:
    """Record a non-hero purchase (e.g. generate_audio) in episodes/credits.json, after checking the caps."""
    amount = float(amount)
    if amount < 0:
        raise ProduceError("credits must be >= 0")
    ok, why = can_spend(amount, now)
    if not ok:
        raise ProduceError(f"over cap, not recorded: {why}")
    from reel import budget
    ep = _ep(record_id)
    ledger = budget.load_ledger(ep)
    ledger["entries"].append({"date": _ist(now).date().isoformat(), "episode": ep.name, "n": what,
                              "model": "generate_audio" if what == "audio" else what, "seconds": 0,
                              "credits": amount, "job": job})
    budget._save(ep, ledger)
    return f"logged {amount:g} credits ({what}, job {job}) for {ep.name}"


def _https(url):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise ProduceError(f"only https URLs: {url!r}")
    return u


def check_fetch(record_id, url, dest) -> Path:
    _https(url)
    if not FETCH_DEST.match(dest or ""):
        raise ProduceError(f"fetch destination must be out/hero_raw/cNN.mp4 or audio/original*.mp3|wav|m4a, got {dest!r}")
    return _ep(record_id) / dest


def fetch(record_id, url, dest) -> str:
    out = check_fetch(record_id, url, dest)
    want = "video/" if dest.endswith(".mp4") else "audio/"
    req = urllib.request.Request(url, headers={"User-Agent": "kathakaar-loop/1"})
    tmp = out.with_name(out.name + ".part")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            _https(r.geturl())
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not (ctype.startswith(want) or ctype in ("application/octet-stream", "binary/octet-stream")):
                raise ProduceError(f"unexpected content type {ctype!r} for {dest}")
            n = 0
            with open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    n += len(chunk)
                    if n > FETCH_MAX:
                        raise ProduceError("download too large")
                    f.write(chunk)
        if n == 0:
            raise ProduceError("empty download")
        os.replace(tmp, out)
    except ProduceError:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise ProduceError(f"download failed: {type(e).__name__}: {e}")
    log = _ep(record_id) / "out/qa/fetch_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as f:
        f.write(json.dumps({"at": _ist(None).isoformat(timespec="seconds"), "host": urllib.parse.urlparse(url).hostname,
                            "dest": dest, "bytes": n}) + "\n")
    return f"saved {dest} ({n / 1e6:.1f} MB)"


def check_put(record_id, src, url) -> Path:
    _https(url)
    if not PUT_SRC.match(src or ""):
        raise ProduceError(f"put source must be out/keyframes/*.png|jpg or refs/*.png|jpg, got {src!r}")
    p = _ep(record_id) / src
    if not p.is_file():
        raise ProduceError(f"missing {src}")
    return p


def put(record_id, src, url, content_type=None) -> str:
    p = check_put(record_id, src, url)
    ctype = content_type or ("image/png" if p.suffix == ".png" else "image/jpeg")
    data = p.read_bytes()
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            code = r.status
    except Exception as e:
        raise ProduceError(f"upload failed: {type(e).__name__}: {e}")
    if not 200 <= code < 300:
        raise ProduceError(f"upload failed: HTTP {code}")
    return f"uploaded {src} ({len(data) / 1e6:.1f} MB, HTTP {code})"


# ---------------------------------------------------------------- CLI

def _run_start():
    v = os.environ.get("LOOP_RUN_START")
    return datetime.fromisoformat(v) if v else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="produce.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", help="plan file (default $PLAN_PATH or ideas/experiment_plan.md)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--slug-hint"); s.add_argument("--now", type=datetime.fromisoformat)
    sub.add_parser("finish").add_argument("id")
    s = sub.add_parser("fail"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("fallback"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("clock"); s.add_argument("id"); s.add_argument("--now", type=datetime.fromisoformat)
    sub.add_parser("sweep").add_argument("--reason", default="the producer run ended before finish")
    sub.add_parser("frames").add_argument("id")
    sub.add_parser("voice-timing").add_argument("id")
    sub.add_parser("can-spend").add_argument("credits", type=float)
    s = sub.add_parser("spend"); s.add_argument("id"); s.add_argument("credits", type=float)
    s.add_argument("--job", required=True); s.add_argument("--what", default="audio")
    s = sub.add_parser("fetch"); s.add_argument("id"); s.add_argument("url"); s.add_argument("dest")
    s = sub.add_parser("put"); s.add_argument("id"); s.add_argument("file"); s.add_argument("url")
    s.add_argument("--content-type")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "start":
            mx = int(os.environ.get("LOOP_MAX_VIDEOS") or DEFAULT_MAX)
            print(start(a.now, a.plan, a.slug_hint, mx, _run_start()))
        elif a.cmd == "finish":
            print(finish(a.id))
        elif a.cmd == "fail":
            print(fail(a.id, a.reason))
        elif a.cmd == "fallback":
            print(fallback(a.id, a.reason))
        elif a.cmd == "clock":
            print(clock(a.id, a.now))
        elif a.cmd == "sweep":
            for rid in sweep(reason=a.reason):
                print(f"FAILED {rid}")
        elif a.cmd == "frames":
            print(frames(a.id))
        elif a.cmd == "voice-timing":
            print(voice_timing(a.id))
        elif a.cmd == "can-spend":
            ok, why = can_spend(a.credits)
            print("OK" if ok else f"NO {why}")
            return 0 if ok else 1
        elif a.cmd == "spend":
            print(spend(a.id, a.credits, a.job, what=a.what))
        elif a.cmd == "fetch":
            print(fetch(a.id, a.url, a.dest))
        elif a.cmd == "put":
            print(put(a.id, a.file, a.url, a.content_type))
    except (ProduceError, vqueue.QueueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
