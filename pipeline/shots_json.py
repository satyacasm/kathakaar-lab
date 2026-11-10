#!/usr/bin/env python3
"""Write an episode's shots.json (English timeline) and shots_hi.json (Hindi timeline) for the QA step.

  pipeline/shots_json.py <episode>
Reads <episode>/shots_spec.json: {"scenes": [[id, line, offset, transition_frames], ...], "fade": 60}. The scene starts
at the given local line's start plus offset (line 0 = frame 0), the same rule Story.tsx uses. Frames come from the
episode's lines.ts; the Hindi frames go through warp_hi.ts. Transitions become "xfade" ranges and the closing fade a
"planned" range, so QA doesn't flag them.
"""
import json
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ep = Path(sys.argv[1]) if Path(sys.argv[1]).is_dir() else LAB / "episodes" / sys.argv[1]
info = json.loads((ep / "episode.json").read_text())
app = LAB / "engine/app/src/episodes" / info["app_dir"]
ts = (app / "lines.ts").read_text()
lines = [(int(a), int(b)) for a, b in re.findall(r"\{s: (\d+), e: (\d+)\}", ts)]
frames = int(re.search(r"FRAMES = (\d+)", ts).group(1))
w = (app / "warp_hi.ts").read_text()
hi_frames = int(re.search(r"HI_FRAMES = (\d+)", w).group(1))
arr = lambda k: [float(x) for x in re.search(k + r": \[([^\]]*)\]", w).group(1).split(",") if x.strip()]  # noqa: E731
WH, WE = arr("hi"), arr("en")


def to_hi(e: float) -> int:
    for i in range(1, len(WE)):
        if e <= WE[i]:
            k = (e - WE[i - 1]) / max(1e-9, WE[i] - WE[i - 1])
            return round(WH[i - 1] + k * (WH[i] - WH[i - 1]))
    return hi_frames


spec = json.loads((ep / "shots_spec.json").read_text())
starts = [(sid, (lines[ln - 1][0] if ln else 0) + off, d) for sid, ln, off, d in spec["scenes"]]
for name, conv, total in (("shots.json", lambda x: round(x), frames), ("shots_hi.json", to_hi, hi_frames)):
    st = [(sid, conv(a), conv(a + d) if d else conv(a)) for sid, a, d in starts]
    shots = [{"id": sid, "a": a, "b": (st[i + 1][1] if i + 1 < len(st) else total)} for i, (sid, a, _) in enumerate(st)]
    xfade = [[a, b] for _, a, b in st[1:] if b > a]
    out = {"shots": shots, "xfade": xfade, "planned": [[total - spec.get("fade", 60) - 15, total]]}
    (ep / name).write_text(json.dumps(out, indent=1))
    print(f"{name}: {len(shots)} shots, {total} frames")
