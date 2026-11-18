#!/usr/bin/env python3
"""Daily approval request (09:00 IST): tells the owner which privately uploaded videos await approval.
Standard library only.

  ask.py            add one INBOX decision (macOS notification) listing the preview_ready videos, with their
                    private YouTube links and the approve/reject commands; once per IST day per set of ids
  ask.py --print    print the multi-line message and change nothing

A changed set (a new video became ready) asks again the same day. State: cache/loop/ask_state.json.
"""
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inbox, vqueue

LAB = Path(HERE).resolve().parents[1]
STATE = LAB / "cache" / "loop" / "ask_state.json"
EPISODES = LAB / "episodes"
TZ = ZoneInfo("Asia/Kolkata")
APPROVE = "python3 pipeline/loop/vqueue.py approve <id> …"
REJECT = 'python3 pipeline/loop/vqueue.py reject <id> --reason "…"'


def _title(rid):
    """Title from the episode's youtube.md, else the id (a missing or odd package never fails the ask)."""
    try:
        import youtube_publish
        sec = youtube_publish.sections((EPISODES / rid / "out/package/youtube.md").read_text())
        return " ".join(youtube_publish.pick(sec, "title").split()) or rid
    except (Exception, SystemExit):
        return rid


def _ready(records):
    return [r for r in records if r.get("status") == "preview_ready"]


def _item(r):
    cell = r.get("cell") or {}
    ig = "by hand" if r.get("ig_mode") == "manual" else "api"
    link = f"https://youtu.be/{r['yt_id']} (private)" if r.get("yt_id") else "no YouTube link"
    return (f"{r['id']} · {cell.get('format', '?')}/{cell.get('audio', '?')} · {_title(r['id'])} · {link}"
            f" · IG: {ig} · {r.get('credits', 0)} credits")


def compose(records, multiline=True):
    ready = _ready(records)
    if not ready:
        return None
    items = [_item(r) for r in ready]
    head = f"{len(ready)} video{'s' if len(ready) != 1 else ''} await your approval"
    if multiline:
        return "\n".join([head + ":", *items, "", "Approve: " + APPROVE, "Reject: " + REJECT])
    return f"{head}: " + " ‖ ".join(items) + f" ‖ Approve: {APPROVE} · Reject: {REJECT}"


def _load_state():
    try:
        return json.loads(Path(STATE).read_text())
    except (OSError, ValueError):
        return {}


def run(now):
    """Add the INBOX decision unless this set of ids was already asked today (IST). Returns True if asked."""
    ready = _ready(vqueue.load())
    text = compose(ready, multiline=False)
    if text is None:
        return False
    ids, day = sorted(r["id"] for r in ready), now.astimezone(TZ).date().isoformat()
    if _load_state() == {"ids": ids, "date": day}:
        return False
    inbox.add(text, "decision")
    Path(STATE).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(STATE) + ".tmp")
    tmp.write_text(json.dumps({"ids": ids, "date": day}))
    os.replace(tmp, STATE)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", dest="show", action="store_true", help="print the message only")
    args = ap.parse_args(argv)
    if args.show:
        print(compose(vqueue.load()) or "(nothing awaiting approval)")
    else:
        print("asked" if run(datetime.now(TZ)) else "nothing new to ask")


if __name__ == "__main__":
    main()
