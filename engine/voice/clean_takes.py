"""Clean the picked narration takes: remove the small pops and hiss the TTS leaves in pauses and at the ends of
takes (they are 40-60 dB under the voice, but the voice chain's compression makes them audible ticks).

Method: 10 ms frames; speech = runs above (peak - 40 dB) lasting at least 90 ms, plus shorter sounds that lead into a
word within 100 ms (consonant releases, e.g. the final t of "bharat"), widened by 40 ms each side. Dropped: lone short
sounds (pops) and loud short fragments right before a syllable (stutters). Everything else fades (15 ms) to silence.

Usage: engine/kk.sh <episode> clean_takes --lang hi [--pick 2:takes_hi_b/L02_t1_s5201.wav,...]
Reads voice/review_<lang>/picks.json (the provisional picks), applies --pick overrides (paths under voice/),
writes voice/clean_<lang>/L??.wav, a log.jsonl (so review_takes can preview them) and voice/picks_<lang>.json.
"""

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402

FR = 0.01


def read(p):
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768, w.getframerate()


def write(p, a, sr):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def clean(a, sr, floor_db=40, min_run=0.09, pad=0.04, ramp=0.015):
    h = int(FR * sr)
    n = len(a) // h + 1
    x = np.pad(a, (0, n * h - len(a)))
    db = 20 * np.log10(np.sqrt((x.reshape(n, h) ** 2).mean(1) + 1e-12))
    loud = db > db.max() - floor_db
    runs, i = [], 0
    while i < n:
        if loud[i]:
            j = i
            while j + 1 < n and loud[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    keep = np.zeros(n, bool)
    p = int(pad / FR)
    for k, (i, j) in enumerate(runs):
        dur = (j - i + 1) * FR
        gap_next = (runs[k + 1][0] - j) * FR if k + 1 < len(runs) else 9.0
        if dur < min_run:
            # a short sound just before a word is a consonant release (keep it), unless it is loud and long:
            # then it's a stutter, a false start of the next syllable (drop it). Lone short sounds are pops.
            stutter = db[i:j + 1].max() > db.max() - 10 and dur >= 0.05
            if gap_next >= 0.1 or stutter:
                continue
        keep[max(0, i - p): j + p + 1] = True
    g = np.repeat(keep.astype(float), h)[: len(a)]
    k = int(ramp * sr)
    g = np.convolve(g, np.ones(k) / k, "same")          # soft edges
    removed = float(np.sqrt(((a * (1 - g)) ** 2).sum() / max(1, ((1 - g) > 0.5).sum())))
    return a * g, removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="hi")
    ap.add_argument("--pick", default="", help="line:path-under-voice/,...")
    args = ap.parse_args()
    V = kk.ep() / "voice"
    picks = json.loads((V / f"review_{args.lang}/picks.json").read_text())
    picks = {int(k): f"takes_{args.lang}/{v}" for k, v in picks.get("picks", picks).items()}
    for item in filter(None, args.pick.split(",")):
        k, v = item.split(":")
        picks[int(k)] = v
    out = V / f"clean_{args.lang}"
    out.mkdir(exist_ok=True)
    log, final = [], {}
    for n in sorted(picks):
        a, sr = read(V / picks[n])
        c, removed = clean(a, sr)
        name = f"L{n:02d}_{Path(picks[n]).stem.split('_', 1)[1]}.wav"
        write(out / name, c, sr)
        final[str(n)] = name
        log.append(json.dumps({"line": n, "take": 1, "file": name, "source": picks[n]}))
        print(f"line {n:2}: {picks[n]:28} -> clean_{args.lang}/{name}  (removed noise rms {20 * np.log10(removed + 1e-9):.0f} dBFS)")
    (out / "log.jsonl").write_text("\n".join(log) + "\n")
    pf = V / f"picks_{args.lang}.json"
    old = json.loads(pf.read_text()) if pf.exists() else {}
    old.update(takes_dir=f"voice/clean_{args.lang}", picks=final)
    pf.write_text(json.dumps(old, indent=1) + "\n")
    print(f"wrote {pf.relative_to(kk.ep())}")


if __name__ == "__main__":
    main()
