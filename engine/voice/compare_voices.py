"""Measure and audition voice candidates: median pitch (how deep), pace, loudness-matched comparison reel.

Usage (from voice/):  .venv/bin/python compare_voices.py designed/*.wav --out review/compare_en.wav
Writes the reel (each candidate loudness-matched to -18 LUFS, 1.2 s gaps, a soft tick before each) and
prints a table, also saved next to the reel as .md. Pitch: autocorrelation per 40 ms voiced frame.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 24000


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def median_f0(x, fmin=55, fmax=300):
    n = int(0.04 * SR)
    hop = n // 2
    rms_all = np.sqrt(np.mean(x ** 2)) + 1e-9
    f0s = []
    for i in range(0, len(x) - n, hop):
        fr = x[i:i + n] * np.hanning(n)
        if np.sqrt(np.mean(fr ** 2)) < 0.5 * rms_all:
            continue
        ac = np.correlate(fr, fr, "full")[n - 1:]
        lo, hi = int(SR / fmax), int(SR / fmin)
        k = lo + np.argmax(ac[lo:hi])
        if ac[k] > 0.45 * ac[0]:
            f0s.append(SR / k)
    return float(np.median(f0s)) if f0s else float("nan")


def norm_lufs(path, target=-18):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", f"loudnorm=I={target}:TP=-2:LRA=11",
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--words", type=int, default=0, help="word count of the text, for words/s")
    a = ap.parse_args()
    tick = 0.15 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * SR)) / SR) * np.hanning(int(0.08 * SR))
    gap = np.zeros(int(1.2 * SR), np.float32)
    reel, rows = [], ["| # | file | length s | words/s | median pitch Hz |", "|---|---|---|---|---|"]
    for i, f in enumerate(a.files, 1):
        x = decode(f)
        dur = len(x) / SR
        wps = f"{a.words / dur:.2f}" if a.words else "-"
        rows.append(f"| {i} | {Path(f).name} | {dur:.1f} | {wps} | {median_f0(x):.0f} |")
        reel += [tick, gap[: SR // 3], norm_lufs(f), gap]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(np.concatenate(reel), -1, 1) * 32767).astype("<i2")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", str(out)],
                   input=pcm.tobytes(), check=True)
    out.with_suffix(".md").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    sys.exit(main())
