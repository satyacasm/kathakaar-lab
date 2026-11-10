#!/usr/bin/env python3
"""Write soft caption files for an episode, timed to the narration (never burned into the picture).

  pipeline/captions.py <episode>
writes out/package/captions_hi.srt (Hindi text on the Hindi audio's timing, timing_hi.json) and captions_en.srt
(English text on the same Hindi timing: the translation track for the Hindi video), plus captions_en_track.srt on the
English timing (timing.json) for the English audio version. Long lines are split at punctuation into chunks of about
42 characters; each chunk gets time in proportion to its length.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
MAX = 42


def chunks(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[,।.?!…])\s+", text.replace('"', '"')) if p.strip()]
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) + 1 + len(p) <= MAX:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(lines: list[str], timing: list[dict]) -> str:
    out, k = [], 1
    for text, tm in zip(lines, timing):
        cs = chunks(text)
        a, b = tm["start"], tm["end"] + 0.25
        total = sum(len(c) for c in cs)
        t = a
        for c in cs:
            d = (b - a) * len(c) / total
            out.append(f"{k}\n{ts(t)} --> {ts(t + d)}\n{c}\n")
            k += 1
            t += d
    return "\n".join(out)


def main():
    ep = LAB / "episodes" / sys.argv[1]
    lj = json.loads((ep / "script/lines.json").read_text())
    hi_t = json.loads((ep / "timing_hi.json").read_text())["lines"]
    en_t = json.loads((ep / "timing.json").read_text())["lines"]
    out = ep / "out/package"
    out.mkdir(parents=True, exist_ok=True)
    (out / "captions_hi.srt").write_text(srt(lj["hi"], hi_t))
    (out / "captions_en.srt").write_text(srt(lj["en"], hi_t))
    (out / "captions_en_track.srt").write_text(srt(lj["en"], en_t))
    print((out / "captions_hi.srt").read_text()[:700])


if __name__ == "__main__":
    main()
