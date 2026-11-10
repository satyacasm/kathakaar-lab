"""Scan narration takes for defects the ear catches but the pace scorer doesn't: clicks and noise spikes, sudden
level dropouts inside words (voice breaks) and pitch cracks.

Usage: engine/kk.sh <episode> scan_takes [--takes-dir takes_hi] [--only picks]   (default: every take in the folder)
Prints one line per take: the count of each defect and their times (s), so clean takes can be preferred and the rest
repaired (clicks) or regenerated (breaks). Standard numpy/scipy only.
"""

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402

HOP = 0.005


def read(p):
    with wave.open(str(p)) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(1)
    return a, sr


def frames(x, n, h):
    k = 1 + max(0, (len(x) - n) // h)
    idx = np.arange(n)[None, :] + h * np.arange(k)[:, None]
    return x[np.minimum(idx, len(x) - 1)]


def f0(fr, sr, lo=70, hi=400):
    """Autocorrelation pitch per frame; 0 where unvoiced."""
    out = np.zeros(len(fr))
    for i, x in enumerate(fr):
        x = x - x.mean()
        e = np.dot(x, x)
        if e < 1e-6:
            continue
        ac = np.correlate(x, x, "full")[len(x) - 1:]
        a, b = int(sr / hi), int(sr / lo)
        k = a + int(np.argmax(ac[a:b]))
        if ac[k] / e > 0.45:
            out[i] = sr / k
    return out


def scan(p):
    a, sr = read(p)
    h, n = int(HOP * sr), int(0.03 * sr)
    rms = np.sqrt((frames(a, n, h) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    speech = db > db.max() - 35
    on = np.flatnonzero(speech)
    if not len(on):
        return {}
    s0, s1 = on[0], on[-1]
    # 1. noise spikes: a short burst (< 70 ms) of sound standing alone in silence (>= 120 ms quiet on both sides)
    loud = db > db.max() - 58
    runs, i = [], 0
    while i < len(loud):
        if loud[i]:
            j = i
            while j + 1 < len(loud) and loud[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    clicks = []
    for k, (a0, a1) in enumerate(runs):
        dur = (a1 - a0 + 1) * HOP
        q0 = (a0 - runs[k - 1][1]) * HOP if k else a0 * HOP
        q1 = (runs[k + 1][0] - a1) * HOP if k + 1 < len(runs) else (len(loud) - a1) * HOP
        if dur < 0.07 and q0 >= 0.12 and q1 >= 0.12:
            clicks.append(round(a0 * HOP, 2))
    # 2. voice breaks: inside speech, a sudden drop of > 20 dB below both neighbours, lasting 10-70 ms
    breaks = []
    sm = db
    for i in range(s0 + 4, s1 - 4):
        if sm[i] < min(sm[i - 4], sm[i + 4]) - 20 and sm[i - 4] > db.max() - 28 and sm[i + 4] > db.max() - 28:
            w = 1
            while i + w < s1 and sm[i + w] < min(sm[i - 4], sm[i + w + 4]) - 20:
                w += 1
            if w * HOP <= 0.07:
                breaks.append(round(i * HOP, 2))
    # 3. pitch cracks: a voiced frame jumping by more than 1.7x (or under 0.6x) from its voiced neighbour
    pf = f0(frames(a, int(0.04 * sr), int(0.01 * sr)), sr)
    cracks = []
    for k in range(1, len(pf) - 1):
        if pf[k] and pf[k - 1] and pf[k + 1]:
            r1, r2 = pf[k] / pf[k - 1], pf[k + 1] / pf[k]
            if (r1 > 1.7 and r2 < 0.65) or (r1 < 0.6 and r2 > 1.6):   # a one-frame excursion that comes back
                cracks.append(round(k * 0.01, 2))
    return dict(clicks=clicks, breaks=breaks, cracks=cracks, len=round(len(a) / sr, 2))


def merge(ts, gap=0.06):
    out = []
    for t in ts:
        if not out or t - out[-1] > gap:
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes-dir", default="takes_hi")
    ap.add_argument("--only", choices=["picks", "all"], default="all")
    ap.add_argument("--json", help="also write the results to this file (under the episode's voice/)")
    args = ap.parse_args()
    td = kk.ep() / "voice" / args.takes_dir
    files = sorted(td.glob("L*.wav"))
    if args.only == "picks":
        rv = kk.ep() / "voice" / args.takes_dir.replace("takes", "review") / "picks.json"
        picks = json.loads(rv.read_text())
        picks = picks.get("picks", picks)
        files = [td / f for _, f in sorted(picks.items(), key=lambda x: int(x[0]))]
    res = {}
    for p in files:
        r = scan(p)
        r = {k: merge(v) if isinstance(v, list) else v for k, v in r.items()}
        res[p.name] = r
        bad = len(r["clicks"]) + 3 * len(r["breaks"]) + 2 * len(r["cracks"])
        print(f"{p.name:22} score {bad:3}  clicks {r['clicks']}  breaks {r['breaks']}  cracks {r['cracks']}")
    if args.json:
        (kk.ep() / "voice" / args.json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
