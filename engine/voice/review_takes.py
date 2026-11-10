"""Score generated takes on objective signals and build a listening preview.

Can't judge emotion. It only flags takes that are measurably off (too fast or slow,
clipped, long dead air or trailing garbage), and picks a provisional best per line.
Satyam's ears make the final pick.

Usage: engine/kk.sh <episode> review_takes [--takes-dir takes_en --out-dir review_en] [--pick 3:2,9:1]
Writes <out-dir>/takes_report.md, preview_best.wav (48 kHz, with script pauses),
and line_LL_all_takes.wav (each line's takes back to back, 1 s apart).
"""

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402
TAKES = OUT = Path()
SR = 24000

# Silence (seconds) after each line, from the script's emotional beats.
PAUSE_AFTER: dict = {}   # silence after each line, from the episode's script/lines.json
TARGET_WPS = 2.3  # calm, deliberate narration (English; Hindi narration runs about 2.6 words/s)
LINE_TEXT: dict = {}   # line -> script text, for take logs that don't record it (Hindi)


def read(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


def write(path, audio, sr=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def speech_bounds(a, thresh_db=-40, win=480):
    """First/last 20 ms window above threshold (relative to the take's peak)."""
    n = len(a) // win
    rms = np.sqrt(np.mean(a[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-12))
    on = np.where(db > thresh_db)[0]
    return (on[0] * win, (on[-1] + 1) * win) if len(on) else (0, len(a))


def score(rec, a):
    s, e = speech_bounds(a)
    words = len((rec.get("text") or LINE_TEXT[rec["line"]]).replace('"', "").split())
    speech_s = (e - s) / SR
    wps = words / max(speech_s, 0.1)
    flags = []
    if np.abs(a).max() > 0.99:
        flags.append("clipped")
    if wps > TARGET_WPS * 1.45:
        flags.append("rushed")
    if wps < TARGET_WPS * 0.55:
        flags.append("too slow / possible dead air or babble")
    if (len(a) - e) / SR > 1.0:
        flags.append("long tail (check for trailing noise)")
    # Penalise distance from target pace; flags dominate.
    pen = abs(np.log(wps / TARGET_WPS)) + 2 * len(flags)
    return dict(speech_s=round(speech_s, 2), wps=round(wps, 2), flags=flags, penalty=round(pen, 3),
                trim=(max(0, s - int(0.05 * SR)), min(len(a), e + int(0.12 * SR))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", default="", help="manual overrides line:take,...")
    ap.add_argument("--takes-dir", default="takes_en", help="folder under the episode's voice/")
    ap.add_argument("--out-dir", default="review_en", help="folder under the episode's voice/")
    args = ap.parse_args()
    global TAKES, OUT, PAUSE_AFTER, LINE_TEXT, TARGET_WPS
    TAKES, OUT = kk.ep() / "voice" / args.takes_dir, kk.ep() / "voice" / args.out_dir
    PAUSE_AFTER = kk.pause_after()
    lang = "hi" if "hi" in args.takes_dir else "en"
    LINE_TEXT = {i + 1: x for i, x in enumerate(kk.lines(lang))}
    if lang == "hi":
        TARGET_WPS = 2.6
    OUT.mkdir(exist_ok=True)
    manual = {int(k): int(v) for k, v in (p.split(":") for p in args.pick.split(",") if p)}

    recs = {}
    for line in (TAKES / "log.jsonl").read_text().splitlines():
        r = json.loads(line)
        recs[(r["line"], r["take"])] = r  # last write wins
    OUT.mkdir(exist_ok=True)

    report = ["# Take review (objective signals only)", "",
              f"Target pace about {TARGET_WPS} words/s. ★ marks the provisional pick.", "",
              "| Line | Take | Speech s | Words/s | Gen s | Flags |", "|---|---|---|---|---|---|"]
    best, preview = {}, []
    for n in sorted({k[0] for k in recs}):
        scored = []
        for (ln, t), r in sorted(recs.items()):
            if ln != n:
                continue
            a = read(TAKES / r["file"])
            scored.append((t, r, a, score(r, a)))
        pick = manual.get(n) or min(scored, key=lambda x: x[3]["penalty"])[0]
        gap = np.zeros(SR)
        line_all = []
        for t, r, a, sc in scored:
            s, e = sc["trim"]
            line_all += [a[s:e], gap]
            if t == pick:
                best[n] = r["file"]
                preview += [a[s:e], np.zeros(int(PAUSE_AFTER.get(n, 0.8) * SR))]
            mark = "★" if t == pick else ""
            report.append(f"| {n} | {t}{mark} | {sc['speech_s']} | {sc['wps']} | {r.get('gen_s', '-')} | "
                          f"{', '.join(sc['flags']) or '-'} |")
        write(OUT / f"line_{n:02d}_all_takes.wav", np.concatenate(line_all))

    tmp = OUT / "_preview_24k.wav"
    audio = np.concatenate([np.zeros(int(0.5 * SR))] + preview)
    write(tmp, audio)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp),
                    "-af", "aresample=48000:filter_size=64:cutoff=0.97", "-ac", "2",
                    str(OUT / "preview_best.wav")], check=True)
    tmp.unlink()

    gen = sum(r.get("gen_s", 0) for r in recs.values())
    aud = sum(r.get("audio_s", 0) for r in recs.values())
    report += ["", f"Preview length: {len(audio) / SR:.1f} s (with planned pauses).",
               f"Generation: {len(recs)} takes, {aud:.0f} s of audio in {gen:.0f} s "
               f"(about {gen / max(aud, 1e-9):.1f}× real time).", "", "Picks: " + json.dumps(best)]
    (OUT / "takes_report.md").write_text("\n".join(report) + "\n")
    (OUT / "picks.json").write_text(json.dumps(best, indent=1))
    print("\n".join(report))


if __name__ == "__main__":
    main()
