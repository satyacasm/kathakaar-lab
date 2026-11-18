#!/usr/bin/env python3
"""Approval queue for the content loop: the single source of truth for every video's state. Standard library only.
(Named vqueue, not queue, so it never shadows the stdlib `queue` module.)

  vqueue.py list [--all]                 open records (posted/rejected hidden unless --all)
  vqueue.py show <id>                    full record as JSON
  vqueue.py approve <id>...              preview_ready -> approved, each gets the next free IST slot
                                         (refused unless the private YouTube preview still exists)
  vqueue.py reject <id> --reason "..."   preview_ready -> rejected, reason stored on one line
  vqueue.py requeue <id>                 failed -> planned

Status flow: planned -> producing -> preview_ready -> approved -> posted (rejected / failed on the side).
Slots are 12:30 and 19:30 Asia/Kolkata. Nothing is public without an approve. The file is cache/loop/queue.json
(git-ignored); writes are atomic and serialised by an flock on queue.json.lock.
"""
import argparse, contextlib, fcntl, json, os, re, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

LAB = Path(__file__).resolve().parents[2]
QUEUE = LAB / "cache" / "loop" / "queue.json"

STATUSES = ("planned", "producing", "preview_ready", "approved", "posted", "rejected", "failed")
ALLOWED = {
    "planned": {"producing", "failed"},
    "producing": {"preview_ready", "failed"},
    "preview_ready": {"approved", "rejected"},
    "approved": {"posted", "failed"},
    "failed": {"planned"},
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


def next_free_slot(records: list[dict], now: datetime) -> datetime:
    now = now.astimezone(TZ)
    held = {datetime.fromisoformat(r["slot"]).astimezone(TZ) for r in records
            if r.get("slot") and r["status"] in HELD}
    day = now.date()
    while True:
        for hhmm in SLOTS:
            h, m = map(int, hhmm.split(":"))
            cand = datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            if cand >= now and cand not in held:
                return cand
        day += timedelta(days=1)


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
            slot = next_free_slot(records, now)
            _set_status(r, "approved", now, slot=slot.isoformat())
        return recs


def reject(record_id: str, reason: str) -> dict:
    return transition(record_id, "rejected", reason=one_line(reason))


def due(now: datetime) -> dict | None:
    """Oldest approved record whose slot is within [now - LATE_GRACE, now]."""
    ok = [r for r in load() if r["status"] == "approved" and r.get("slot")
          and now - LATE_GRACE <= datetime.fromisoformat(r["slot"]) <= now]
    return min(ok, key=lambda r: r["slot"]) if ok else None


def _ist(iso):
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%a %d %b %H:%M IST") if iso else "-"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("--all", action="store_true")
    sub.add_parser("show").add_argument("id")
    sub.add_parser("approve").add_argument("ids", nargs="+", metavar="id")
    r = sub.add_parser("reject"); r.add_argument("id"); r.add_argument("--reason", required=True)
    sub.add_parser("requeue").add_argument("id")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "list":
            for rec in load():
                if args.all or rec["status"] not in ("posted", "rejected"):
                    print(f"{rec['id']:40} {rec['status']:14} {_ist(rec['slot'])}")
        elif args.cmd == "show":
            print(json.dumps(_find(load(), args.id), indent=2, ensure_ascii=False))
        elif args.cmd == "approve":
            import youtube_publish  # lazy: needs network/secrets
            exists = getattr(youtube_publish, "video_exists", None)
            if exists is None:
                raise QueueError("youtube_publish.video_exists is not available yet; cannot verify the private preview")
            for rec in approve(args.ids, _now(), exists):
                print(f"approved {rec['id']} -> {_ist(rec['slot'])}")
        elif args.cmd == "reject":
            print(f"rejected {reject(args.id, args.reason)['id']}")
        else:
            print(f"requeued {transition(args.id, 'planned')['id']}")
    except QueueError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # for youtube_publish
    main()
