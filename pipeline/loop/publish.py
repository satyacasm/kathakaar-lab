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
--dry-run makes no network call and changes no state. --now takes an ISO time (naive = IST) for rehearsals.
Standard library only.
"""
import argparse, json, sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inbox, instagram_publish, vqueue, youtube_publish
from vqueue import LATE_GRACE, TZ, one_line

EPISODES = vqueue.LAB / "episodes"
API_VIDEO = "reel_with_song.mp4"
MANUAL_VIDEO = "reel_SILENT.mp4"


def _fail(rec, reason):
    vqueue.transition(rec["id"], "failed", reason=one_line(reason))
    inbox.add(f"Publish failed for {rec['id']}: {one_line(reason)}", "failure")
    return "failed"


def _read_meta(ep: Path) -> dict:
    return json.loads((ep / "episode.json").read_text())


def _precheck(rec, ep: Path):
    """Return a problem string, or None. Runs before anything becomes public."""
    if not rec.get("yt_id"):
        return "no private YouTube preview id"
    try:
        _read_meta(ep)
    except (OSError, ValueError) as e:
        return f"episode.json unreadable: {e}"
    need = MANUAL_VIDEO if rec.get("ig_mode") == "manual" else API_VIDEO
    if rec.get("ig_mode") not in ("api", "manual"):
        return f"unknown ig_mode {rec.get('ig_mode')!r}"
    if not (ep / "out/final" / need).exists():
        return f"missing {ep / 'out/final' / need}"
    return None


def _log_youtube_public(ep: Path, yt_id: str, now: datetime):
    meta = _read_meta(ep)
    meta.setdefault("published", {})["youtube"] = {
        "id": yt_id, "url": f"https://youtube.com/shorts/{yt_id}", "privacy": "public", "public_at": now.isoformat()}
    (ep / "episode.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")


def _handoff_text(rec, ep: Path, meta: dict) -> str:
    song = meta.get("song") or {}
    start = song.get("instagram_start") or song.get("segment") or "the start"
    return (f"Post on Instagram by hand: {meta.get('title_en') or rec['id']} - file {ep / 'out/final' / MANUAL_VIDEO}, "
            f"song {song.get('title', '?')} from {start}, YouTube https://youtube.com/shorts/{rec['yt_id']}")


def _pick(now):
    """A record already public on YouTube still owing Instagram wins (retry at any time); else the due record."""
    pending = [r for r in vqueue.load() if r["status"] == "approved" and r.get("yt_public") and r.get("slot")]
    if pending:
        return min(pending, key=lambda r: r["slot"])
    return vqueue.due(now)


def _move_late(now, say) -> int:
    moved = 0
    with vqueue._edit() as records:
        for r in sorted(records, key=lambda r: r.get("slot") or ""):
            if (r["status"] == "approved" and r.get("slot") and not r.get("yt_public")
                    and datetime.fromisoformat(r["slot"]) < now - LATE_GRACE):
                new = vqueue.next_free_slot(records, now)
                say(f"late: {r['id']} slot {r['slot']} -> {new.isoformat()}")
                r["slot"] = new.isoformat()
                inbox.add(f"{r['id']} missed its slot by more than 2 h; moved to {new.strftime('%a %d %b %H:%M IST')}", "info")
                moved += 1
    return moved


def run_slot(now: datetime, dry_run: bool = False, say=print) -> str:
    now = now.astimezone(TZ)
    moved = _move_late_dry(now, say) if dry_run else _move_late(now, say)
    rec = _pick(now)
    if rec is None:
        return "moved" if moved else "nothing_due"
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
    now_iso = now.isoformat()
    if not rec.get("yt_public"):
        try:
            youtube_publish.set_privacy(rec["yt_id"], "public")
        except Exception as e:  # nothing became public
            if rec.get("yt_retry"):
                return _fail(rec, f"YouTube switch failed twice: {e}")
            vqueue.update(rec["id"], yt_retry=1)
            inbox.add(f"YouTube switch failed for {rec['id']}, will retry once: {one_line(e)}", "failure")
            return "failed"
        vqueue.update(rec["id"], yt_public=True)
        try:
            _log_youtube_public(ep, rec["yt_id"], now)
        except Exception as e:
            inbox.add(f"{rec['id']} is public on YouTube but episode.json was not updated: {one_line(e)}", "failure")
    if not api:
        meta = _read_meta(ep)
        vqueue.transition(rec["id"], "posted", posted_at=now_iso, ig_manual_pending=True)
        inbox.add(_handoff_text(rec, ep, meta), "decision")
        return "handed_off"
    already = (_read_meta(ep).get("published") or {}).get("instagram")
    try:
        res = {"media_id": already["media_id"]} if already else instagram_publish.publish_reel(ep, API_VIDEO)
    except (Exception, SystemExit) as e:
        msg = one_line(e.code if isinstance(e, SystemExit) else e)
        if rec.get("ig_retry"):
            return _fail(rec, f"Instagram failed twice: {msg}")
        vqueue.update(rec["id"], ig_retry=1)
        inbox.add(f"Instagram post failed for {rec['id']} (YouTube is public); retrying at the next slot: {msg}", "info")
        return "ig_retry_pending"
    vqueue.transition(rec["id"], "posted", posted_at=now_iso, ig_media_id=res["media_id"])
    return "posted"


def _move_late_dry(now, say) -> int:
    n = 0
    for r in vqueue.load():
        if (r["status"] == "approved" and r.get("slot") and not r.get("yt_public")
                and datetime.fromisoformat(r["slot"]) < now - LATE_GRACE):
            say(f"late: {r['id']} slot {r['slot']} would move to {vqueue.next_free_slot(vqueue.load(), now).isoformat()}")
            n += 1
    return n


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
