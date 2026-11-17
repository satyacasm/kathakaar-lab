#!/usr/bin/env python3
"""Tiny helper for ideas/INBOX.md, the place the automation loop leaves items for the user. Standard library only.

  inbox.py add "<text>" [--kind decision|failure|info]   append "- [ ] YYYY-MM-DD HH:MM IST [kind] text" under
                                                         "## Open"; decision/failure also fire a macOS notification
  inbox.py list [--all]                                  print open (unticked) items; --all includes ticked ones

The user ticks an item by changing "[ ]" to "[x]". The file is git-ignored (ideas/).
"""
import argparse, datetime, os, re, subprocess, sys
from zoneinfo import ZoneInfo

LAB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INBOX = os.path.join(LAB, "ideas", "INBOX.md")
HEADER = """# Kathakaar inbox

Items the automation loop (pipeline/loop) leaves for you. Tick one by changing `[ ]` to `[x]`.
Kinds: `decision` = needs your call, `failure` = a job failed (see cache/loop/logs), `info` = FYI.

## Open

## Done
"""


def notify(text, kind):
    msg = text.replace("\\", " ").replace('"', "'")[:200]
    try:
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Kathakaar" subtitle "{kind}"'],
                       timeout=10, capture_output=True)
    except Exception:
        pass


def add(text, kind):
    os.makedirs(os.path.dirname(INBOX), exist_ok=True)
    if not os.path.exists(INBOX):
        with open(INBOX, "w") as f:
            f.write(HEADER)
    now = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M")
    line = f"- [ ] {now} IST [{kind}] {' '.join(text.split())}\n"
    lines = open(INBOX).read().splitlines(keepends=True)
    idx = next((i for i, l in enumerate(lines) if l.strip() == "## Open"), None)
    if idx is None:
        lines.append("\n## Open\n")
        idx = len(lines) - 1
    # insert after the last item of the Open section (before the next heading or end)
    j = idx + 1
    last = idx
    while j < len(lines) and not lines[j].startswith("## "):
        if lines[j].startswith("- ["):
            last = j
        j += 1
    ins = last + 1
    if last == idx:  # no items yet: keep a blank line after heading
        lines.insert(ins, "\n"); ins += 1
    lines.insert(ins, line)
    tmp = INBOX + ".tmp"
    with open(tmp, "w") as f:
        f.write("".join(lines))
    os.replace(tmp, INBOX)
    print(line.rstrip())
    if kind in ("decision", "failure"):
        notify(text, kind)


def list_items(show_all):
    if not os.path.exists(INBOX):
        print("(no inbox yet)"); return
    for l in open(INBOX):
        if re.match(r"- \[ \]", l) or (show_all and re.match(r"- \[[xX]\]", l)):
            print(l.rstrip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("text"); a.add_argument("--kind", choices=["decision", "failure", "info"], default="info")
    l = sub.add_parser("list"); l.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.cmd == "add":
        add(args.text, args.kind)
    else:
        list_items(args.all)


if __name__ == "__main__":
    main()
