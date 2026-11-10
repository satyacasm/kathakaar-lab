"""Pick, per line, a take that fits the video's existing timing slot (timing.json), so the picture needn't change.

A slot runs from the line's start to the next line's start (the last one to the end of the story). Among
takes whose trimmed length fits the slot minus a small margin, pick the one closest to the target pace;
if none fits, report it so it can be regenerated or time-stretched.

Usage: engine/kk.sh <episode> fit_takes takes_en --out picks_en.json [--pick 7:L07_t5]
"""

import argparse
import json
from pathlib import Path

import review_takes as R

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402

MARGIN = 0.1      # s of air kept before the next line starts
PAD = 0.17        # build_sound trims to speech + 0.05 s before and 0.12 s after


def main():
    TIMING = json.loads((kk.ep() / "timing.json").read_text())
    ap = argparse.ArgumentParser()
    ap.add_argument("takes_dir")
    ap.add_argument("--out", default="picks_en.json", help="relative paths go under the episode's voice/")
    ap.add_argument("--pick", default="", help="manual overrides line:file-prefix,...")
    a = ap.parse_args()
    d = kk.ep() / "voice" / a.takes_dir
    recs = [json.loads(x) for x in (d / "log.jsonl").read_text().splitlines() if x.strip()]
    lines = TIMING["lines"]
    manual = dict(x.split(":") for x in a.pick.split(",") if x)
    picks, rows = {}, ["| Line | Slot s | Pick | Length s | Words/s | Note |", "|---|---|---|---|---|---|"]
    for i, ln in enumerate(lines):
        n = ln["line"]
        slot = (lines[i + 1]["start"] if i + 1 < len(lines) else TIMING["total"]) - ln["start"]
        cands = []
        for r in recs:
            if r["line"] != n:
                continue
            x = R.read(d / r["file"])
            s, e = R.speech_bounds(x)
            speech = (e - s) / R.SR
            cands.append((r["file"], speech + PAD, len(r["text"].split()) / speech))
        if str(n) in manual:
            best = next(c for c in cands if c[0].startswith(manual[str(n)]))
            note = "manual"
        else:
            fit = [c for c in cands if c[1] <= slot - MARGIN]
            best = min(fit or cands, key=lambda c: abs(c[2] - R.TARGET_WPS) if fit else c[1])
            note = "" if fit else "NO TAKE FITS"
        picks[str(n)] = best[0]
        rows.append(f"| {n} | {slot:.2f} | {best[0]} | {best[1]:.2f} | {best[2]:.2f} | {note} |")
    out = Path(a.out)
    out = out if out.is_absolute() else kk.ep() / "voice" / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"takes_dir": f"voice/{a.takes_dir}", "picks": picks}, indent=1) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
