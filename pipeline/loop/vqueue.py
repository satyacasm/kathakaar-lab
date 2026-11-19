#!/usr/bin/env python3
"""Approval queue for the content loop: the single source of truth for every video's state. Standard library only.
(Named vqueue, not queue, so it never shadows the stdlib `queue` module.)

  vqueue.py list [--all]                 open records (posted/rejected hidden unless --all)
  vqueue.py show <id>                    full record as JSON
  vqueue.py approve <id>...              preview_ready -> approved, each gets the next free IST slot
                                         (refused unless the private YouTube preview still exists)
  vqueue.py rejections --since YYYY-MM-DD  rejected on/after the date: date | id | format / audio | reason
  vqueue.py reject <id> --reason "..."   preview_ready -> rejected, reason stored on one line; then the private
                                         YouTube preview is deleted (best effort; yt_deleted: true when done)
  vqueue.py reseal <id>                  failed -> preview_ready for a record whose private preview still exists,
                                         is not public, and whose video/youtube.md/titles are unchanged (Instagram
                                         caption or song may differ): re-records the digests; approve again after
  vqueue.py requeue <id>                 failed -> planned, only for records with no YouTube preview (else: reseal)

Status flow: planned -> producing -> preview_ready -> approved -> posted (rejected / failed on the side).
Slots are 12:30 and 19:30 Asia/Kolkata. Nothing is public without an approve. The file is cache/loop/queue.json
(git-ignored); writes are atomic and serialised by an flock on queue.json.lock.
"""
import argparse, contextlib, fcntl, json, os, re, sys, tempfile, urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

LAB = Path(__file__).resolve().parents[2]
QUEUE = LAB / "cache" / "loop" / "queue.json"
EPISODES = LAB / "episodes"
RESEAL_CLEAR = ("slot", "yt_retry", "ig_retry", "ig_container", "reason")

STATUSES = ("planned", "producing", "preview_ready", "approved", "posted", "rejected", "failed")
ALLOWED = {
    "planned": {"producing", "failed"},
    "producing": {"preview_ready", "failed"},
    "preview_ready": {"approved", "rejected"},
    "approved": {"posted", "failed"},
    "failed": {"planned", "preview_ready"},
}
SLOTS = ("12:30", "19:30")
TZ = ZoneInfo("Asia/Kolkata")
LATE_GRACE = timedelta(hours=2)
HELD = ("approved", "posted")  # statuses that occupy a slot


class QueueError(Exception):
    pass


def _path(path):
    return Path(path) if path is not None else Path(QUEUE)


def _now():
    return datetime.now(TZ)


def load(path=None) -> list[dict]:
    p = _path(path)
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return []


def _write(records, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def _locked(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p.with_name(p.name + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def save(records: list[dict], path=None) -> None:
    p = _path(path)
    with _locked(p):
        _write(records, p)


@contextlib.contextmanager
def _edit(path=None):
    """Read-modify-write under the lock: yields the records list; saved on clean exit."""
    p = _path(path)
    with _locked(p):
        records = load(p)
        yield records
        _write(records, p)


def _find(records, record_id):
    for r in records:
        if r["id"] == record_id:
            return r
    raise QueueError(f"no record {record_id!r}")


def _set_status(r, new_status, now, **fields):
    if new_status not in ALLOWED.get(r["status"], ()):
        raise QueueError(f"{r['id']}: cannot go {r['status']} -> {new_status}")
    r.update(fields)
    r["status"] = new_status
    r["history"].append([now.isoformat(), new_status])


def one_line(text: str) -> str:
    s = " ".join(str(text).split()).replace("|", "\\|")
    return s.lstrip("#-[ ")[:300]


def add(record_id: str, cell: dict, ig_mode: str) -> dict:
    if ig_mode not in ("api", "manual"):
        raise QueueError(f"ig_mode must be api or manual, got {ig_mode!r}")
    with _edit() as records:
        if any(r["id"] == record_id for r in records):
            raise QueueError(f"{record_id!r} already queued")
        rec = {"id": record_id, "status": "planned", "cell": cell, "slot": None, "yt_id": None,
               "ig_media_id": None, "ig_mode": ig_mode, "credits": 0.0, "reason": None,
               "posted_at": None, "history": [[_now().isoformat(), "planned"]]}
        records.append(rec)
        return rec


def transition(record_id: str, new_status: str, **fields) -> dict:
    with _edit() as records:
        r = _find(records, record_id)
        _set_status(r, new_status, _now(), **fields)
        return r


def update(record_id: str, **fields) -> dict:
    """Set fields on a record without changing its status (status itself must go through transition)."""
    if "status" in fields:
        raise QueueError("use transition() to change status")
    with _edit() as records:
        r = _find(records, record_id)
        r.update(fields)
        return r


def next_free_slot(records: list[dict], now: datetime, only: str | None = None) -> datetime:
    """Earliest free IST slot at or after now; `only` ("12:30" or "19:30") restricts it to that slot (a record's
    cell.slot_pref, e.g. a series that always goes out in the evening)."""
    now = now.astimezone(TZ)
    held = {datetime.fromisoformat(r["slot"]).astimezone(TZ) for r in records
            if r.get("slot") and r["status"] in HELD}
    day = now.date()
    while True:
        for hhmm in SLOTS:
            if only and hhmm != only:
                continue
            h, m = map(int, hhmm.split(":"))
            cand = datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            if cand >= now and cand not in held:
                return cand
        day += timedelta(days=1)


def _pref(r: dict):
    p = (r.get("cell") or {}).get("slot_pref")
    return p if p in SLOTS else None


def move_late(now: datetime) -> list[tuple[str, str, str]]:
    """Approved, not-yet-public records more than LATE_GRACE past their slot move to the next free slot.
    Returns [(id, old_slot, new_slot)]."""
    moved = []
    with _edit() as records:
        for r in sorted(records, key=lambda r: r.get("slot") or ""):
            if (r["status"] == "approved" and r.get("slot") and not r.get("yt_public")
                    and datetime.fromisoformat(r["slot"]) < now - LATE_GRACE):
                new = next_free_slot(records, now, _pref(r)).isoformat()
                moved.append((r["id"], r["slot"], new))
                r["slot"] = new
    return moved


def approve(ids: list[str], now: datetime, exists: Callable[[str], bool]) -> list[dict]:
    """All-or-nothing: every id must be preview_ready with a still-existing private preview."""
    with _edit() as records:
        recs = [_find(records, i) for i in ids]
        for r in recs:
            if r["status"] != "preview_ready":
                raise QueueError(f"{r['id']}: status is {r['status']}, only preview_ready can be approved")
            if not r.get("yt_id") or not exists(r["yt_id"]):
                raise QueueError(f"{r['id']}: private preview {r.get('yt_id')!r} not found on YouTube")
        for r in recs:
            slot = next_free_slot(records, now, _pref(r))
            _set_status(r, "approved", now, slot=slot.isoformat())
        return recs


def reject(record_id: str, reason: str) -> dict:
    return transition(record_id, "rejected", reason=one_line(reason))


def delete_rejected_preview(record_id: str, delete: Callable[[str], None], notify: Callable[[str], None],
                            privacy: Callable[[str], str | None]) -> bool:
    """After reject() (outside the queue lock): delete the record's private YouTube preview, best effort, and only
    while it is still private: never when the record says yt_public, and only if the live privacyStatus (privacy())
    is "private" (None = already gone). Success -> yt_deleted: true; anything else -> notify(...) and no delete."""
    r = _find(load(), record_id)
    yt_id = r.get("yt_id")
    if r["status"] != "rejected" or not yt_id or r.get("yt_deleted"):
        return False
    if r.get("yt_public"):
        notify(f"refused to delete {yt_id} of rejected {record_id}: not private (the record says it is public)")
        return False
    try:
        live = privacy(yt_id)
        if live is None:  # already gone
            update(record_id, yt_deleted=True)
            return True
        if live != "private":
            notify(f"refused to delete {yt_id} of rejected {record_id}: not private (YouTube says {live})")
            return False
        delete(yt_id)
    except (Exception, SystemExit) as e:
        notify(f"could not delete private preview {yt_id} of rejected {record_id}: {one_line(e)}")
        return False
    update(record_id, yt_deleted=True)
    return True


def requeue(record_id: str) -> dict:
    """failed -> planned; only when nothing was uploaded (a record with a private preview is resealed instead)."""
    with _edit() as records:
        r = _find(records, record_id)
        if r.get("yt_id"):
            raise QueueError(f"{record_id}: has private preview {r['yt_id']}; use reseal (then approve again)")
        _set_status(r, "planned", _now())
        return r


def reseal(record_id: str, exists: Callable[[str], bool], digests: Callable[[str], dict],
           yt_change: Callable[[dict, dict], str | None]) -> dict:
    """failed -> preview_ready for a record whose private preview still exists and is still what would go public:
    only Instagram-side changes (caption_instagram.txt, song fields) may be resealed; a changed video file, youtube.md
    or title needs a new preview (yt_change(old, new) names it). Clears the slot and retry state; needs a fresh approve."""
    r = _find(load(), record_id)
    if r["status"] != "failed":
        raise QueueError(f"{record_id}: status is {r['status']}, only failed records can be resealed")
    if r.get("yt_public"):
        raise QueueError(f"{record_id}: already public on YouTube: use the Instagram retry path; not resealable")
    if not r.get("yt_id"):
        raise QueueError(f"{record_id}: no private preview to reseal; use requeue")
    fields = digests(record_id)
    changed = yt_change(r, fields)
    if changed:
        raise QueueError(f"{record_id}: video or YouTube text changed since the preview was uploaded ({changed}): "
                         f"needs a new preview: re-run finish")
    if not exists(r["yt_id"]):  # network, outside the lock
        raise QueueError(f"{record_id}: private preview {r['yt_id']!r} not found on YouTube; nothing to reseal "
                         f"(the record stays failed)")
    with _edit() as records:
        r = _find(records, record_id)
        if r["status"] != "failed" or r.get("yt_public"):
            raise QueueError(f"{record_id}: changed meanwhile (status {r['status']})")
        for k in RESEAL_CLEAR:
            if r.get("yt_public") and k in ("ig_container", "ig_retry"):
                continue  # Instagram state of a public video is never reset
            r[k] = None
        _set_status(r, "preview_ready", _now(), **fields)
        return r


def due(now: datetime) -> dict | None:
    """Oldest approved record whose slot is within [now - LATE_GRACE, now]."""
    ok = [r for r in load() if r["status"] == "approved" and r.get("slot")
          and now - LATE_GRACE <= datetime.fromisoformat(r["slot"]) <= now]
    return min(ok, key=lambda r: r["slot"]) if ok else None


def rejections_since(day: date) -> list[dict]:
    """Rejected records whose (last) rejection happened on or after `day` (IST), oldest first,
    each a copy with `rejected_on` (YYYY-MM-DD) added."""
    out = []
    for r in load():
        if r["status"] != "rejected":
            continue
        stamps = [h[0] for h in r["history"] if h[1] == "rejected"]
        if not stamps:
            continue
        when = datetime.fromisoformat(stamps[-1]).astimezone(TZ).date()
        if when >= day:
            out.append({**r, "rejected_on": when.isoformat()})
    return sorted(out, key=lambda r: r["rejected_on"])


def _ist(iso):
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%a %d %b %H:%M IST") if iso else "-"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("--all", action="store_true")
    sub.add_parser("show").add_argument("id")
    sub.add_parser("approve").add_argument("ids", nargs="+", metavar="id")
    r = sub.add_parser("reject"); r.add_argument("id"); r.add_argument("--reason", required=True)
    rj = sub.add_parser("rejections"); rj.add_argument("--since", required=True, metavar="YYYY-MM-DD")
    sub.add_parser("requeue").add_argument("id")
    sub.add_parser("reseal").add_argument("id")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "list":
            for rec in load():
                if args.all or rec["status"] not in ("posted", "rejected"):
                    print(f"{rec['id']:40} {rec['status']:14} {_ist(rec['slot'])}")
        elif args.cmd == "show":
            print(json.dumps(_find(load(), args.id), indent=2, ensure_ascii=False))
        elif args.cmd == "approve":
            exists = _video_exists()
            for rec in approve(args.ids, _now(), exists):
                print(f"approved {rec['id']} -> {_ist(rec['slot'])}")
        elif args.cmd == "rejections":
            for rec in rejections_since(date.fromisoformat(args.since)):
                c = rec["cell"]
                print(f"{rec['rejected_on']} | {rec['id']} | {c.get('format') or '-'} / {c.get('audio') or '-'} | {rec['reason']}")
        elif args.cmd == "reject":
            print(f"rejected {reject(args.id, args.reason)['id']}")
            _delete_preview_cli(args.id)  # after the queue lock is released
        elif args.cmd == "reseal":
            import integrity
            rec = reseal(args.id, _video_exists(), lambda rid: integrity.record(EPISODES / rid),
                         integrity.youtube_side_change)
            print(f"resealed {rec['id']} -> preview_ready; approve it again to schedule it")
        else:
            print(f"requeued {requeue(args.id)['id']}")
    except QueueError as e:
        sys.exit(f"error: {e}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:  # URLError is an OSError; listed for clarity
        sys.exit(f"error: could not reach YouTube to check the private preview ({one_line(e)}); nothing changed, try again")


def _video_exists():
    import youtube_publish  # lazy: needs network/secrets
    exists = getattr(youtube_publish, "video_exists", None)
    if exists is None:
        raise QueueError("youtube_publish.video_exists is not available yet; cannot verify the private preview")
    return exists


def _delete_preview_cli(record_id):
    import inbox

    def delete(yt_id):
        import youtube_publish  # lazy: needs network/secrets
        youtube_publish.delete_video(yt_id)

    def privacy(yt_id):
        import youtube_publish
        return youtube_publish.video_privacy(yt_id)

    def notify(msg):
        print(msg, file=sys.stderr)
        inbox.add(msg, "failure")

    if delete_rejected_preview(record_id, delete, notify, privacy):
        print(f"deleted private preview of {record_id}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # for youtube_publish
    sys.path.insert(0, str(Path(__file__).resolve().parent))      # for inbox, integrity
    main()
