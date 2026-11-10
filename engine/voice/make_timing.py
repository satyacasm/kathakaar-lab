"""Lay the picked English takes out on a timeline and write the episode's timing.json (voice-first episodes).

Each line starts after the previous line's trimmed take plus its script pause (lines.json pause_after);
trims follow build_sound (speech + 0.05 s before, 0.12 s after). The Hindi timeline is derived later from this one
by build_sound_hi. Episode 001 was picture-first and keeps its hand-made timing.json; don't run this there.

Usage: engine/kk.sh <episode> make_timing [--lead-in 0.4] [--tail 2.0]
"""

import argparse
import json
import sys
from pathlib import Path

import review_takes as R

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-in", type=float, default=0.4)
    ap.add_argument("--tail", type=float, default=2.0, help="s after the last line's pause, for the closing image")
    a = ap.parse_args()
    ep = kk.ep()
    picks = json.loads((ep / "voice/picks_en.json").read_text())
    pause = kk.pause_after()
    t, lines = a.lead_in, []
    for n in sorted(map(int, picks["picks"])):
        x = R.read(ep / picks["takes_dir"] / picks["picks"][str(n)])
        s, e = R.speech_bounds(x)
        length = (min(len(x), e + int(0.12 * R.SR)) - max(0, s - int(0.05 * R.SR))) / R.SR
        p = pause.get(n, 0.8)
        lines.append(dict(line=n, start=round(t, 3), end=round(t + length - 0.12, 3), pause_after=p))
        t += length + p
    total = round(t + a.tail, 3)
    (ep / "timing.json").write_text(json.dumps(dict(lead_in=a.lead_in, total=total, lines=lines), indent=1) + "\n")
    print(f"timing.json: {len(lines)} lines, {total} s")


if __name__ == "__main__":
    main()
