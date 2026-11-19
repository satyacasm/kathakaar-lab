#!/usr/bin/env python3
"""Deterministic helper for the overnight producer (headless Claude follows pipeline/loop/produce_prompt.md).
The producer has no ffmpeg, curl or engine/kk.sh of its own: every media, network and voice step it needs is a
fixed-purpose subcommand here, with paths confined to its episode (and music-lab/pool/ for inputs).

Run and video lifecycle
  start [--slug-hint WORDS] [--now ISO]   next plan row -> scaffold + queue; prints START <id> <format> <audio>
                                          <topic_source>, or STOP time|buffer|max|plan
  finish <id>                    package check, needs a fresh out/qa/frames.png (run `frames` first), PRIVATE
                                 YouTube preview, digests of finals/package/episode fields (integrity.py), status
                                 preview_ready; prints READY <id> <yt_id>
  fail <id> --reason "..."       producing -> failed + INBOX failure
  fallback <id> --reason "..."   switch to the 0-credit narrated format (over cap, no popular song)
  sweep [--reason "..."]         every video still producing -> failed (run.sh, after the Claude run)
  clock <id>                     minutes used of the 75-minute per-video budget
  window-seconds [--now ISO]     run.sh: seconds the night run may last (0 outside 00:30-05:30 IST)
  context                        newest trends digest, existing episodes, audio pool counts
  run-start --balance X / run-end --balance Y   Higgsfield balance at both ends; a drop larger than the ledger's
                                 entries for this run (+1) raises an INBOX failure "unrecorded Higgsfield spend"
Credits
  can-spend <credits>            OK, or NO <reason> (exit 1): loop cap and monthly cap
  spend <id> <credits> --job J [--what audio]   record a generate_audio purchase (always recorded; over cap ->
                                 warning + INBOX failure)
Network (https, Higgsfield hosts only; no userinfo, IP literals or private addresses)
  allow-host <id> <url>          record the host of a URL a Higgsfield tool returned (suffix allowlist)
  fetch <id> <url> <dest>        dest: out/hero_raw/cNN.mp4 or audio/original*.{mp3,wav,m4a}
  put <id> <file> <url> [--content-type T]     PUT out/keyframes/* or refs/* to a media_upload URL
Media (ffmpeg/ffprobe with fixed arguments; inputs in the episode or music-lab/pool/, outputs in the episode)
  probe <id> <path>              duration and streams as JSON
  frame <id> <video> <t>         one full-size frame -> out/qa/frame_<t>.png
  frames <id>                    1 frame/s contact sheet of the preview -> out/qa/frames.png
  copy-song <id> <pool file> [--start S] [--dur D] [--name song]   cut + convert -> audio/<name>.wav
  beats <id> <audio>             tempo, beat times and strongest onsets as JSON (estimate; verify by ear-free checks)
Voice (engine/kk.sh with fixed arguments)
  voice <id> hindi_takes [--takes N] [--lines 3,9]
  voice <id> review_takes [--pick 3:2,9:1]      (takes_hi -> review_hi)
  voice-timing <id>              voice/review_hi/picks.json -> voice/picks_hi.json + timing_hi.json

Window: start only between 00:30 and 06:00 IST ($LOOP_WINDOW_OVERRIDE=1 for a supervised daytime rehearsal).
Stops: 4+ videos in preview_ready/approved, $LOOP_MAX_VIDEOS (default 4) started since $LOOP_RUN_START, no open row.
Plan: --plan, $PLAN_PATH or ideas/experiment_plan.md (must lie under ideas/ or the temp dir). Never publishes: the upload is always --preview (private).
"""
import argparse, ipaddress, json, math, os, re, shutil, socket, subprocess, sys
import urllib.error, urllib.parse, urllib.request
from array import array
from datetime import datetime, time, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inbox, integrity, plan, vqueue
from vqueue import TZ, one_line

LAB = vqueue.LAB
EPISODES = LAB / "episodes"
POOL = LAB / "music-lab/pool"
RUN_FILE = LAB / "cache/loop/producer_run.json"
NEW_REEL = LAB / "pipeline/new_reel.sh"
KK = LAB / "engine/kk.sh"
YT_PUBLISH = LAB / "pipeline/youtube_publish.py"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
LOCAL_ONLY = ["-protocol_whitelist", "file,pipe"]          # input option: no network, no concat/subfile tricks

BUFFER_TARGET = 4
BUFFER_STATUSES = ("preview_ready", "approved")
WINDOW = (time(0, 30), time(6, 0))  # the night run: start only inside [00:30, 06:00) IST
DEFAULT_MAX = 4
UPLOAD_TIMEOUT = 1800
VIDEO_MINUTES = 75                 # per-video budget the prompt holds the producer to
FALLBACK_CELL = ("narrated", "bed")
KIND = {"narrated": "narrated_reel", "claim": "claim_reel"}   # music/shloka/dialogue stay music_reel
PACKAGE = ("out/final/reel_with_song.mp4", "out/package/youtube.md", "out/package/caption_instagram.txt")
# the art style is never named in public copy
STYLE_WORDS = ("watercolor", "watercolour", "pattachitra", "ink wash", "ink-wash", "art style", "house style",
               "painting style")
SHEET_COLS, SHEET_W = 8, 240
LEAD_IN, TAIL, DEFAULT_PAUSE = 0.4, 1.5, 0.8
SPEND_WHAT = ("audio",)
RECONCILE_SLACK = 1.0
# hosts accepted without being recorded, and the suffixes a recorded host (allow-host) must end in
HOSTS_DIRECT = ("higgsfield.ai",)
HOSTS_RECORDABLE = ("higgsfield.ai", "amazonaws.com", "cloudfront.net", "r2.cloudflarestorage.com", "googleapis.com")
FETCH_MAX = 400 * 1024 * 1024
FETCH_DEST = re.compile(r"^(out/hero_raw/c\d{2}\.mp4|audio/original[a-z0-9_-]*\.(mp3|wav|m4a))$")
PUT_SRC = re.compile(r"^(out/keyframes|refs)/[A-Za-z0-9_-]+\.(png|jpg|jpeg)$")
NAME = re.compile(r"^[a-z0-9_-]{1,40}$")
VOICE_TOOLS = ("hindi_takes", "review_takes")


class ProduceError(Exception):
    pass


def _run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], **kw)


def _resolve(host):
    return [ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)]


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
    if not re.fullmatch(r"\d{3}-[a-z0-9-]+", record_id or ""):
        raise ProduceError(f"not a loop episode id: {record_id!r}")
    return Path(EPISODES) / record_id


def _record(record_id):
    for r in vqueue.load():
        if r["id"] == record_id:
            return r
    raise ProduceError(f"no queue record {record_id!r}")


def _producing(record_id):
    rec = _record(record_id)
    if rec["status"] != "producing":
        raise ProduceError(f"{record_id} is {rec['status']}; only a video that is producing can be worked on")
    return rec


def _edit_episode(ep: Path, **fields):
    p = ep / "episode.json"
    d = json.loads(p.read_text())
    d.update(fields)
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def _kind_fields(fmt, audio):
    return {"kind": KIND.get(fmt, "music_reel"), "format": KIND.get(fmt, "music_reel"),
            "narration": fmt in KIND}


def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def _in_path(record_id, rel, pool=True) -> Path:
    """An existing input file inside the episode (or music-lab/pool/), symlinks resolved."""
    if not rel or Path(rel).is_absolute():
        raise ProduceError(f"give a path relative to the episode (or music-lab/pool/...): {rel!r}")
    ep = _ep(record_id).resolve()
    roots = [ep] + ([Path(POOL).resolve()] if pool else [])
    cands = [ep / rel] + ([Path(LAB) / rel, Path(POOL) / rel] if pool else [])
    for c in cands:
        p = c.resolve()
        if p.is_file() and any(_within(p, r) for r in roots):
            return p
    raise ProduceError(f"{rel!r} is not a file inside episodes/{record_id}/" + (" or music-lab/pool/" if pool else ""))


def _out_path(record_id, rel) -> Path:
    """An output path inside the episode's out/qa/ or audio/ (no traversal, no symlink escape)."""
    ep = _ep(record_id).resolve()
    p = (ep / rel).resolve()
    if not (_within(p, ep / "out/qa") or _within(p, ep / "audio")):
        raise ProduceError(f"outputs go under out/qa/ or audio/ of the episode, got {rel!r}")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


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


def in_window(now) -> bool:
    if os.environ.get("LOOP_WINDOW_OVERRIDE") == "1":
        return True
    return WINDOW[0] <= _ist(now).time() < WINDOW[1]


RUN_START_WINDOW = (time(0, 30), time(5, 30))   # run.sh starts the night run only inside this
RUN_CAP_S = 5 * 3600


def window_seconds(now=None) -> int:
    """How long run.sh may let the producer run from `now`: 0 outside 00:30-05:30 IST, else min(5 h, until 06:00).
    $LOOP_WINDOW_OVERRIDE=1 (supervised rehearsal) gives 5 h at any time."""
    now = _ist(now)
    if os.environ.get("LOOP_WINDOW_OVERRIDE") == "1":
        return RUN_CAP_S
    if not RUN_START_WINDOW[0] <= now.time() < RUN_START_WINDOW[1]:
        return 0
    end = now.replace(hour=WINDOW[1].hour, minute=WINDOW[1].minute, second=0, microsecond=0)
    return int(min(RUN_CAP_S, (end - now).total_seconds()))


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
    if not in_window(now):
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
    # A requeued video (failed -> planned, folder kept) is finished before any new plan row is started.
    for rec in records:
        if rec["status"] == "planned" and (Path(EPISODES) / rec["id"] / "episode.json").exists():
            vqueue.transition(rec["id"], "producing")
            c = rec.get("cell") or {}
            return (f"RESUME {rec['id']} {c.get('format')} {c.get('audio')} {c.get('topic_source')}\n"
                    "Its folder is kept: reuse the research, script, stills and voice already there; redo only missing steps")
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


def clock(record_id, now=None) -> str:
    now = _ist(now)
    rec = _record(record_id)
    t0 = _ts(rec, "producing")
    mins = int((now - t0).total_seconds() // 60) if t0 else 0
    return (f"now {now:%H:%M} IST; {record_id} {rec['status']} for {mins} min of {VIDEO_MINUTES}"
            f" ({max(0, VIDEO_MINUTES - mins)} left)")


def context() -> str:
    ideas = LAB / "ideas"
    trends = sorted(ideas.glob("trends-*.md"))
    eps = sorted(p.name for p in Path(EPISODES).iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))
    pool = {k: len([f for f in (Path(POOL) / k).glob("*") if f.is_file()]) if (Path(POOL) / k).is_dir() else 0
            for k in ("popular", "library", "original")}
    return "\n".join([f"newest trends digest: {trends[-1].relative_to(LAB) if trends else '(none)'}",
                      "episodes: " + ", ".join(eps),
                      "audio pool: " + ", ".join(f"{k} {n}" for k, n in pool.items())])


# ---------------------------------------------------------------- media (fixed ffmpeg/ffprobe templates)

def _duration(path) -> float:
    r = _run([FFPROBE, *LOCAL_ONLY, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
             capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise ProduceError(f"ffprobe could not read {path}: {(r.stderr or '').strip()[-200:]}")


def probe(record_id, rel) -> str:
    p = _in_path(record_id, rel)
    r = _run([FFPROBE, *LOCAL_ONLY, "-v", "error", "-show_entries",
              "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
              "-of", "json", p], capture_output=True, text=True)
    if r.returncode != 0:
        raise ProduceError(f"ffprobe failed: {(r.stderr or '').strip()[-200:]}")
    return r.stdout.strip()


def frame(record_id, rel, t) -> Path:
    t = float(t)
    if not 0 <= t < 3600:
        raise ProduceError("t must be seconds within the video")
    src = _in_path(record_id, rel, pool=False)
    out = _out_path(record_id, f"out/qa/frame_{t:07.2f}.png")
    r = _run([FFMPEG, "-y", "-v", "error", *LOCAL_ONLY, "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", out],
             capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise ProduceError(f"ffmpeg frame failed: {(r.stderr or '').strip()[-300:]}")
    return out


def frames(record_id) -> Path:
    """out/qa/frames.png: one frame per second of the preview, 8 per row, for Claude to inspect."""
    ep = _ep(record_id)
    video = ep / PACKAGE[0]
    if not video.exists():
        raise ProduceError(f"missing {PACKAGE[0]}")
    n = max(1, math.ceil(_duration(video)))
    out = _out_path(record_id, "out/qa/frames.png")
    cols = min(SHEET_COLS, n)
    vf = f"fps=1,scale={SHEET_W}:-2,tile={cols}x{math.ceil(n / cols)}:padding=4:color=white"
    r = _run([FFMPEG, "-y", "-v", "error", *LOCAL_ONLY, "-i", video, "-vf", vf, "-frames:v", "1", out],
             capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise ProduceError(f"ffmpeg contact sheet failed: {(r.stderr or '').strip()[-300:]}")
    return out


def copy_song(record_id, pool_rel, start=0.0, dur=None, name="song") -> Path:
    """Cut and convert a pool track into the episode: audio/<name>.wav, 44.1 kHz stereo."""
    if not NAME.match(name or ""):
        raise ProduceError(f"--name must be lowercase letters, digits, - or _: {name!r}")
    src = Path(pool_rel)
    src = src if src.parts[:2] == ("music-lab", "pool") else Path("music-lab/pool") / src
    p = (Path(LAB) / src).resolve()
    if not (p.is_file() and _within(p, Path(POOL).resolve())):
        raise ProduceError(f"{pool_rel!r} is not a track in music-lab/pool/")
    out = _out_path(record_id, f"audio/{name}.wav")
    cmd = [FFMPEG, "-y", "-v", "error", *LOCAL_ONLY, "-ss", f"{float(start):.3f}"]
    if dur is not None:
        cmd += ["-t", f"{float(dur):.3f}"]
    cmd += ["-i", p, "-vn", "-ar", "44100", "-ac", "2", out]
    r = _run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise ProduceError(f"ffmpeg copy failed: {(r.stderr or '').strip()[-300:]}")
    return out


BEAT_SR, BEAT_HOP = 11025, 256


def beats(record_id, rel) -> dict:
    """Rough tempo/beat grid from an energy-flux onset curve (stdlib only). An estimate to start bars from."""
    src = _in_path(record_id, rel)
    r = _run([FFMPEG, "-v", "error", *LOCAL_ONLY, "-i", src, "-ac", "1", "-ar", str(BEAT_SR), "-f", "s16le", "-"],
             capture_output=True)
    if r.returncode != 0:
        raise ProduceError(f"ffmpeg decode failed: {(r.stderr or b'').decode(errors='replace').strip()[-300:]}")
    pcm = array("h")
    pcm.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        pcm.byteswap()
    return beat_grid(pcm, BEAT_SR, BEAT_HOP)


def beat_grid(pcm, sr, hop) -> dict:
    n = len(pcm) // hop
    if n < 8:
        raise ProduceError("audio too short for beat analysis")
    energy = [math.log1p(sum(x * x for x in pcm[i * hop:(i + 1) * hop]) / hop) for i in range(n)]
    flux = [0.0] + [max(0.0, energy[i] - energy[i - 1]) for i in range(1, n)]
    fps = sr / hop
    best = (0.0, 0)
    for bpm in range(70, 181):                       # autocorrelation over plausible tempi
        lag = round(fps * 60 / bpm)
        if lag >= n:
            continue
        score = sum(flux[i] * flux[i - lag] for i in range(lag, n)) / (n - lag)
        if score > best[0]:
            best = (score, lag)
    lag = best[1] or round(fps * 0.5)

    def comb(period, phase):                         # flux summed on a (fractional) beat grid
        return sum(flux[int(round(phase + k * period))] for k in range(int((n - 1 - phase) / period) + 1))

    period = max((lag + d / 20 for d in range(-20, 21)), key=lambda q: max(comb(q, p) for p in range(lag)))
    phase = max(range(lag), key=lambda p: comb(period, p))
    beat_times = [round((phase + k * period) / fps, 3) for k in range(int((n - 1 - phase) / period) + 1)]
    order = sorted(range(n), key=lambda i: -flux[i])
    onsets = []
    for i in order:
        if len(onsets) >= 12:
            break
        if all(abs(i - j) > fps for j in onsets):
            onsets.append(i)
    return {"bpm": round(60 * fps / period, 1), "beats": beat_times,
            "strongest_onsets": sorted(round(i / fps, 3) for i in onsets)}


# ---------------------------------------------------------------- voice (engine/kk.sh with fixed arguments)

def voice(record_id, tool, takes=None, lines=None, pick=None) -> str:
    _producing(record_id)
    if tool not in VOICE_TOOLS:
        raise ProduceError(f"voice tool must be one of {', '.join(VOICE_TOOLS)}")
    ep = _ep(record_id).resolve()
    if tool == "hindi_takes":
        args = ["--takes", str(int(takes or 3))]
        if not 1 <= int(args[1]) <= 5:
            raise ProduceError("--takes must be 1-5")
        if lines:
            if not re.fullmatch(r"\d{1,2}(,\d{1,2})*", lines):
                raise ProduceError("--lines like 3,9")
            args += ["--lines", lines]
    else:
        args = ["--takes-dir", "takes_hi", "--out-dir", "review_hi"]
        if pick:
            if not re.fullmatch(r"\d{1,2}:\d(,\d{1,2}:\d)*", pick):
                raise ProduceError("--pick like 3:2,9:1")
            args += ["--pick", pick]
    r = _run([KK, ep, tool, *args], capture_output=True, text=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0:
        raise ProduceError(f"{tool} failed (exit {r.returncode}): {out[-600:]}")
    return out[-3000:]


def voice_timing(record_id) -> str:
    """Lay the picked Hindi takes end to end (lead-in 0.4 s, each line's pause_after, default 0.8 s) and write
    voice/picks_hi.json and timing_hi.json in the shape narration.py reads."""
    ep = _ep(record_id)
    picks = {str(k): v for k, v in json.loads((ep / "voice/review_hi/picks.json").read_text()).items()}
    pause = {str(k): float(v) for k, v in
             json.loads((ep / "script/lines.json").read_text()).get("pause_after", {}).items()}
    t, lines = LEAD_IN, []
    for n in sorted(picks, key=int):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.wav", picks[n]):
            raise ProduceError(f"bad take name {picks[n]!r}")
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


# ---------------------------------------------------------------- finish / fail / fallback

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
    """Runs unsandboxed (it needs secrets/ and the YouTube API), so it starts no ffmpeg: the contact sheet comes from
    `produce.py frames` (sandboxed) and must be newer than the preview it shows."""
    rec = _producing(record_id)
    ep = _ep(record_id)
    need = list(PACKAGE) + (["out/final/reel_SILENT.mp4"] if rec.get("ig_mode") == "manual" else [])
    missing = [p for p in need if not (ep / p).is_file()]
    if missing:
        raise ProduceError(f"{record_id}: missing {', '.join(missing)}")
    check_copy(ep)
    sheet = ep / "out/qa/frames.png"
    if not sheet.is_file() or sheet.stat().st_mtime < (ep / PACKAGE[0]).stat().st_mtime:
        raise ProduceError(f"{record_id}: out/qa/frames.png is missing or older than the preview: run "
                           f"`python3 pipeline/loop/produce.py frames {record_id}` and check it first")
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
    vqueue.transition(record_id, "preview_ready", yt_id=yt_id, credits=_credits(ep), **integrity.record(ep))
    return f"READY {record_id} {yt_id}"


def _ledger():
    from reel import budget
    return budget.load_ledger(Path(EPISODES) / "x")


def _credits(ep: Path) -> float:
    try:
        from reel import budget
        return float(budget.episode_spent(_ledger(), ep.name))
    except Exception:
        return 0.0


def fail(record_id, reason) -> str:
    rec = _producing(record_id)
    reason = one_line(reason)
    vqueue.transition(record_id, "failed", reason=reason)
    inbox.add(f"Producer failed {record_id} ({rec['cell'].get('format')}/{rec['cell'].get('audio')}): {reason}",
              "failure")
    return f"FAILED {record_id}"


def fallback(record_id, reason) -> str:
    rec = _producing(record_id)
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
    inbox.add(f"Producer {record_id}: {cell.get('planned', 'cell')} -> narrated Short ({one_line(reason)})", "info")
    return f"FALLBACK {record_id} {FALLBACK_CELL[0]} {FALLBACK_CELL[1]}"


# ---------------------------------------------------------------- credits

def can_spend(amount, now=None) -> tuple:
    return _can_spend(float(amount), _ist(now).strftime("%Y-%m"))


def spend(record_id, amount, job, now=None, what="audio") -> str:
    """Record a purchase that already happened (generate_audio) in episodes/credits.json. Always recorded; if it
    crossed a cap, the line says so and an INBOX failure is added."""
    amount = float(amount)
    if amount < 0:
        raise ProduceError("credits must be >= 0")
    if what not in SPEND_WHAT:
        raise ProduceError(f"--what must be one of {', '.join(SPEND_WHAT)} (hero clips use reel.py hero-log)")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", job or ""):
        raise ProduceError("--job must be the Higgsfield job id")
    _record(record_id)
    ok, why = can_spend(amount, now)
    from reel import budget
    ep = _ep(record_id)
    ledger = budget.load_ledger(ep)
    ledger["entries"].append({"date": _ist(now).date().isoformat(), "episode": ep.name, "n": what,
                              "model": "generate_audio", "seconds": 0, "credits": amount, "job": job})
    budget._save(ep, ledger)
    line = f"logged {amount:g} credits ({what}, job {job}) for {ep.name}"
    if not ok:
        inbox.add(f"Producer {record_id}: a {amount:g}-credit {what} purchase went over the cap ({why})", "failure")
        line += f"\nwarning: over cap ({why}); recorded anyway and reported. Buy nothing more tonight."
    return line


def _run_ids(run_start) -> set:
    return {r["id"] for r in vqueue.load() if (_ts(r, "producing") or datetime.min.replace(tzinfo=TZ)) >= run_start}


def run_start_balance(balance, now=None) -> str:
    now = _ist(now)
    start_iso = os.environ.get("LOOP_RUN_START") or now.isoformat(timespec="seconds")
    p = Path(RUN_FILE)
    try:
        if json.loads(p.read_text()).get("run_start") == start_iso:
            raise ProduceError(f"the run-start balance for this run ({start_iso}) is already recorded")
    except (OSError, ValueError):
        pass
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"run_start": start_iso, "balance_start": float(balance), "recorded": now.isoformat()}) + "\n")
    return f"run start balance {float(balance):g} recorded"


def run_end_balance(balance, now=None) -> str:
    p = Path(RUN_FILE)
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        raise ProduceError("no run-start balance recorded for this run")
    if d.get("balance_end") is not None:
        return "run end balance already recorded"
    rs = datetime.fromisoformat(d["run_start"])
    ids = _run_ids(rs)
    logged = sum(e.get("credits", 0) for e in _ledger()["entries"] if e.get("episode") in ids)
    drop = d["balance_start"] - float(balance)
    d.update(balance_end=float(balance), ledger_credits=logged, drop=drop)
    p.write_text(json.dumps(d) + "\n")
    msg = f"Higgsfield balance fell {drop:g}; ledger has {logged:g} for this run's videos"
    if drop > logged + RECONCILE_SLACK:
        inbox.add(f"Producer: unrecorded Higgsfield spend: {msg} ({', '.join(sorted(ids)) or 'no videos'})", "failure")
        return msg + " -> INBOX failure (unrecorded Higgsfield spend)"
    return msg + " (ok)"


def check_reconciled(run_start) -> str | None:
    """After the run (run.sh sweep): a run without both balances means its spend was not reconciled."""
    if not run_start:
        return None
    try:
        d = json.loads(Path(RUN_FILE).read_text())
    except (OSError, ValueError):
        d = {}
    if d.get("run_start") != run_start:
        return _note_unreconciled("no run-start balance was recorded")
    if d.get("balance_end") is None:
        return _note_unreconciled("no run-end balance was recorded")
    return None


def _note_unreconciled(why):
    msg = f"Producer: Higgsfield spend not reconciled this run ({why}); compare the balance with episodes/credits.json"
    inbox.add(msg, "info")
    return msg


# ---------------------------------------------------------------- network (Higgsfield only)

def _host(url, extra=()) -> str:
    u = urllib.parse.urlparse(url or "")
    if u.scheme != "https" or not u.hostname:
        raise ProduceError(f"only https URLs: {url!r}")
    if u.username or u.password or "@" in u.netloc:
        raise ProduceError("URLs with user info are refused")
    try:
        port = u.port
    except ValueError:
        raise ProduceError("bad port")
    if port not in (None, 443):
        raise ProduceError("only the default https port")
    host = u.hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        raise ProduceError("IP-address URLs are refused")
    except ValueError:
        pass
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ProduceError("local hosts are refused")
    return host


def _suffix(host, suffixes) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


def check_url(record_id, url) -> str:
    host = _host(url)
    known = set(_record(record_id).get("fetch_hosts") or [])
    if not (_suffix(host, HOSTS_DIRECT) or host in known):
        raise ProduceError(f"host {host} is not a Higgsfield host: if a Higgsfield tool returned this URL, "
                           f"run `produce.py allow-host {record_id} <url>` first")
    return host


def _public_ip(host):
    for ip in _resolve(host):
        a = ipaddress.ip_address(ip.split("%")[0])
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified:
            raise ProduceError(f"{host} resolves to a non-public address")


def allow_host(record_id, url) -> str:
    _producing(record_id)
    host = _host(url)
    if not _suffix(host, HOSTS_RECORDABLE):
        raise ProduceError(f"{host} is not under {', '.join(HOSTS_RECORDABLE)}")
    rec = _record(record_id)
    hosts = sorted(set(rec.get("fetch_hosts") or []) | {host})
    vqueue.update(record_id, fetch_hosts=hosts)
    return f"allowed {host} for {record_id}"


def check_fetch(record_id, url, dest) -> Path:
    check_url(record_id, url)
    if not FETCH_DEST.match(dest or ""):
        raise ProduceError(f"fetch destination must be out/hero_raw/cNN.mp4 or audio/original*.mp3|wav|m4a, got {dest!r}")
    return _ep(record_id) / dest


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def fetch(record_id, url, dest) -> str:
    _producing(record_id)
    out = check_fetch(record_id, url, dest)
    want = "video/" if dest.endswith(".mp4") else "audio/"
    tmp = out.with_name(out.name + ".part")
    out.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(_NoRedirect)
    n = 0
    try:
        for _ in range(4):                         # follow redirects ourselves, re-checking every hop
            _public_ip(urllib.parse.urlparse(url).hostname)
            try:
                r = opener.open(urllib.request.Request(url, headers={"User-Agent": "kathakaar-loop/1"}), timeout=60)
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                    url = urllib.parse.urljoin(url, e.headers["Location"])
                    check_url(record_id, url)
                    continue
                raise
            break
        else:
            raise ProduceError("too many redirects")
        with r:
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not (ctype.startswith(want) or ctype in ("application/octet-stream", "binary/octet-stream")):
                raise ProduceError(f"unexpected content type {ctype!r} for {dest}")
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
    check_url(record_id, url)
    if not PUT_SRC.match(src or ""):
        raise ProduceError(f"put source must be out/keyframes/*.png|jpg or refs/*.png|jpg, got {src!r}")
    ep = _ep(record_id).resolve()
    p = (ep / src).resolve()
    if not (p.is_file() and _within(p, ep)):
        raise ProduceError(f"missing {src}")
    return p


def put(record_id, src, url, content_type=None) -> str:
    _producing(record_id)
    p = check_put(record_id, src, url)
    if content_type and content_type not in ("image/png", "image/jpeg"):
        raise ProduceError("--content-type must be image/png or image/jpeg")
    ctype = content_type or ("image/png" if p.suffix == ".png" else "image/jpeg")
    data = p.read_bytes()
    _public_ip(urllib.parse.urlparse(url).hostname)
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": ctype})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=120) as r:
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
    sub.add_parser("context")
    sub.add_parser("window-seconds").add_argument("--now", type=datetime.fromisoformat)
    sub.add_parser("run-start").add_argument("--balance", type=float, required=True)
    sub.add_parser("run-end").add_argument("--balance", type=float, required=True)
    sub.add_parser("can-spend").add_argument("credits", type=float)
    s = sub.add_parser("spend"); s.add_argument("id"); s.add_argument("credits", type=float)
    s.add_argument("--job", required=True); s.add_argument("--what", default="audio", choices=SPEND_WHAT)
    s = sub.add_parser("allow-host"); s.add_argument("id"); s.add_argument("url")
    s = sub.add_parser("fetch"); s.add_argument("id"); s.add_argument("url"); s.add_argument("dest")
    s = sub.add_parser("put"); s.add_argument("id"); s.add_argument("file"); s.add_argument("url")
    s.add_argument("--content-type", choices=("image/png", "image/jpeg"))
    s = sub.add_parser("probe"); s.add_argument("id"); s.add_argument("path")
    s = sub.add_parser("frame"); s.add_argument("id"); s.add_argument("video"); s.add_argument("t", type=float)
    sub.add_parser("frames").add_argument("id")
    s = sub.add_parser("copy-song"); s.add_argument("id"); s.add_argument("pool_file")
    s.add_argument("--start", type=float, default=0.0); s.add_argument("--dur", type=float)
    s.add_argument("--name", default="song")
    s = sub.add_parser("beats"); s.add_argument("id"); s.add_argument("audio")
    s = sub.add_parser("voice"); s.add_argument("id"); s.add_argument("tool", choices=VOICE_TOOLS)
    s.add_argument("--takes", type=int); s.add_argument("--lines"); s.add_argument("--pick")
    sub.add_parser("voice-timing").add_argument("id")
    a = ap.parse_args(argv)
    if a.plan or os.environ.get("PLAN_PATH"):  # start rewrites the plan: only under ideas/ or the temp dir
        import tempfile
        a.plan = str(plan._confine(a.plan or os.environ["PLAN_PATH"], LAB / "ideas", tempfile.gettempdir()))
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
            note = check_reconciled(os.environ.get("LOOP_RUN_START"))
            if note:
                print(note)
        elif a.cmd == "window-seconds":
            print(window_seconds(a.now))
        elif a.cmd == "context":
            print(context())
        elif a.cmd == "run-start":
            print(run_start_balance(a.balance))
        elif a.cmd == "run-end":
            print(run_end_balance(a.balance))
        elif a.cmd == "can-spend":
            ok, why = can_spend(a.credits)
            print("OK" if ok else f"NO {why}")
            return 0 if ok else 1
        elif a.cmd == "spend":
            print(spend(a.id, a.credits, a.job, what=a.what))
        elif a.cmd == "allow-host":
            print(allow_host(a.id, a.url))
        elif a.cmd == "fetch":
            print(fetch(a.id, a.url, a.dest))
        elif a.cmd == "put":
            print(put(a.id, a.file, a.url, a.content_type))
        elif a.cmd == "probe":
            print(probe(a.id, a.path))
        elif a.cmd == "frame":
            print(frame(a.id, a.video, a.t))
        elif a.cmd == "frames":
            print(frames(a.id))
        elif a.cmd == "copy-song":
            print(copy_song(a.id, a.pool_file, a.start, a.dur, a.name))
        elif a.cmd == "beats":
            print(json.dumps(beats(a.id, a.audio)))
        elif a.cmd == "voice":
            print(voice(a.id, a.tool, a.takes, a.lines, a.pick))
        elif a.cmd == "voice-timing":
            print(voice_timing(a.id))
    except (ProduceError, vqueue.QueueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
