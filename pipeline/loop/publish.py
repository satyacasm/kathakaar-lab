#!/usr/bin/env python3
"""Slot publisher: the ONLY code in the loop that makes a video public. Runs at 12:30 and 19:30 IST.

  publish.py slot [--dry-run] [--now ISO]   post the approved video whose slot is due

Only records in status `approved` with a slot are ever touched. For the due record:
  1. YouTube: the private preview is switched to public (never again once `yt_public` is set), and
     episode.json gets published.youtube so the analytics collector maps it.
  2. Instagram, ig_mode "api": publish_reel(ep, "reel_with_song.mp4"). One failure -> ig_retry=1, record stays
     approved and is retried at the next slot run (YouTube is not touched again); a second failure -> failed + INBOX.
  3. Instagram, ig_mode "manual" (popular songs): record goes to posted with ig_manual_pending=True and an INBOX
     decision tells Satyam which file, song and start time to use in the app.
Approved records more than LATE_GRACE past their slot (and not yet public) move to the next free slot.
Pending Instagram retries are handled first, then the record due now, in the same run. A non-blocking file lock makes a
second concurrent run return "locked".
--dry-run makes no network call and changes no state. --now takes an ISO time (naive = IST) for rehearsals.
Standard library only.
"""
import argparse, contextlib, fcntl, hashlib, json, sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inbox, instagram_publish, vqueue, youtube_publish
from vqueue import TZ, one_line

EPISODES = vqueue.LAB / "episodes"
LOCKFILE = vqueue.LAB / "cache" / "loop" / "locks" / "publish.flock"
API_VIDEO = "reel_with_song.mp4"
MANUAL_VIDEO = "reel_SILENT.mp4"


@contextlib.contextmanager
def _run_lock():
    """Non-blocking exclusive lock; yields False when another run holds it."""
    Path(LOCKFILE).parent.mkdir(parents=True, exist_ok=True)
    with open(LOCKFILE, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True


def _fail(rec, reason):
    vqueue.transition(rec["id"], "failed", reason=one_line(reason))
    inbox.add(f"Publish failed for {rec['id']}: {one_line(reason)}", "failure")
    return "failed"


def _read_meta(ep: Path) -> dict:
    return json.loads((ep / "episode.json").read_text())


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _precheck(rec, ep: Path):
    """Return a problem string, or None. Runs before anything becomes public."""
    if not rec.get("yt_id"):
        return "no private YouTube preview id"
    try:
        _read_meta(ep)
    except (OSError, ValueError) as e:
        return f"episode.json unreadable: {e}"
    for name, digest in (rec.get("final_sha256") or {}).items():   # recorded by produce.py finish
        f = ep / "out/final" / name
        if not f.is_file() or _sha256(f) != digest:
            return f"final file changed since approval: {name}"
    if rec.get("ig_mode") == "manual":
        if not (ep / "out/final" / MANUAL_VIDEO).exists():
            return f"missing {ep / 'out/final' / MANUAL_VIDEO}"
    elif rec.get("ig_mode") == "api":
        try:
            instagram_publish._prepare(ep, API_VIDEO)  # video, caption, size; "already on Instagram" is adopted later
        except SystemExit as e:
            if not str(e.code).startswith("already on Instagram"):
                return str(e.code)
    else:
        return f"unknown ig_mode {rec.get('ig_mode')!r}"
    return None


def _log_youtube_public(ep: Path, yt_id: str, now: datetime):
    meta = _read_meta(ep)
    yt = meta.setdefault("published", {}).setdefault("youtube", {})
    yt.update({"id": yt_id, "url": f"https://youtube.com/shorts/{yt_id}", "privacy": "public", "public_at": now.isoformat()})
    (ep / "episode.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")


def _handoff_text(rec, ep: Path, meta: dict) -> str:
    song = meta.get("song") or {}
    start = song.get("instagram_start") or song.get("segment") or "the start"
    return (f"Post on Instagram by hand: {meta.get('title_en') or rec['id']} - file {ep / 'out/final' / MANUAL_VIDEO}, "
            f"song {song.get('title', '?')} from {start}, YouTube https://youtube.com/shorts/{rec['yt_id']}")


def _process(rec, now: datetime, dry_run: bool, say) -> str:
    """Publish one approved record (YouTube unless already public, then Instagram)."""
    ep = EPISODES / rec["id"]
    problem = _precheck(rec, ep)
    if problem:
        say(f"{rec['id']}: cannot publish: {problem}")
        return "failed" if dry_run else _fail(rec, problem)
    api = rec["ig_mode"] == "api"
    if dry_run:
        say(f"{rec['id']} (slot {rec['slot']}): would " + ("" if rec.get("yt_public") else
            f"set YouTube {rec['yt_id']} public, then ") +
            (f"publish {API_VIDEO} to Instagram via the API" if api else
             f"hand off to Satyam: {_handoff_text(rec, ep, _read_meta(ep))}"))
        return "posted" if api else "handed_off"
    if not rec.get("yt_public"):
        try:
            youtube_publish.set_privacy(rec["yt_id"], "public")
        except Exception as e:  # nothing became public
            if getattr(e, "code", None) == 404:
                return _fail(rec, "private preview missing on YouTube (404)")
            if rec.get("yt_retry"):
                return _fail(rec, f"YouTube switch failed twice: {e}")
            vqueue.update(rec["id"], yt_retry=1)
            inbox.add(f"YouTube switch failed for {rec['id']}, will retry once: {one_line(e)}", "failure")
            return "yt_retry_pending"
        vqueue.update(rec["id"], yt_public=True)
        try:
            _log_youtube_public(ep, rec["yt_id"], now)
        except Exception as e:
            inbox.add(f"{rec['id']} is public on YouTube but episode.json was not updated: {one_line(e)}", "failure")
    if not api:
        meta = _read_meta(ep)
        inbox.add(_handoff_text(rec, ep, meta), "decision")  # tell Satyam first; the record follows
        vqueue.transition(rec["id"], "posted", posted_at=now.isoformat(), ig_manual_pending=True)
        return "handed_off"
    already = (_read_meta(ep).get("published") or {}).get("instagram")
    try:
        if already:
            res = {"media_id": already["media_id"]}
        elif rec.get("ig_container") and instagram_publish.container_published(rec["ig_container"]):
            inbox.add(f"{rec['id']}: Instagram reports the earlier upload as published; check the post and its link", "info")
            res = {"media_id": None}
        else:
            res = instagram_publish.publish_reel(
                ep, API_VIDEO, on_container=lambda cid: vqueue.update(rec["id"], ig_container=cid))
    except (Exception, SystemExit) as e:
        msg = one_line(e.code if isinstance(e, SystemExit) else e)
        if rec.get("ig_retry"):
            return _fail(rec, f"Instagram failed twice: {msg}")
        vqueue.update(rec["id"], ig_retry=1)
        inbox.add(f"Instagram post failed for {rec['id']} (YouTube is public); retrying at the next slot: {msg}", "info")
        return "ig_retry_pending"
    vqueue.transition(rec["id"], "posted", posted_at=now.isoformat(), ig_media_id=res["media_id"])
    return "posted"


def _pending_ig():
    """Approved records already public on YouTube that still owe Instagram (never touch YouTube again)."""
    return sorted((r for r in vqueue.load() if r["status"] == "approved" and r.get("yt_public") and r.get("slot")),
                  key=lambda r: r["slot"])


def _run(now: datetime, dry_run: bool, say) -> str:
    if dry_run:
        moved = []
        for r in vqueue.load():
            if (r["status"] == "approved" and r.get("slot") and not r.get("yt_public")
                    and datetime.fromisoformat(r["slot"]) < now - vqueue.LATE_GRACE):
                moved.append(r["id"])
                say(f"late: {r['id']} slot {r['slot']} would move to the next free slot")
    else:
        moved = vqueue.move_late(now)
        for rid, _old, new in moved:  # after the queue lock is released
            say(f"late: {rid} -> {new}")
            inbox.add(f"{rid} missed its slot by more than 2 h; moved to "
                      f"{datetime.fromisoformat(new).strftime('%a %d %b %H:%M IST')}", "info")
    results, handled = [], set()
    for rec in _pending_ig():
        handled.add(rec["id"])
        results.append(_process(rec, now, dry_run, say))
    due = vqueue.due(now)
    if due and due["id"] not in handled:
        return _process(due, now, dry_run, say)
    if results:
        return results[0]
    return "moved" if moved else "nothing_due"


def run_slot(now: datetime, dry_run: bool = False, say=print) -> str:
    now = now.astimezone(TZ)
    if dry_run:
        return _run(now, True, say)
    with _run_lock() as got:
        if not got:
            say("another publish run holds the lock; skipping")
            return "locked"
        return _run(now, False, say)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("slot")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--now", help="ISO time (naive = IST) instead of the clock")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    print(run_slot(now, dry_run=a.dry_run))


if __name__ == "__main__":
    main()
