"""Generate narration takes, line by line, with Qwen3-TTS voice cloning (mlx-audio).

Usage: engine/kk.sh <episode> gen_takes [--takes 3] [--lines 3,9 --take-start 4] [--text 7="punctuation override"]
Clones the final English narrator (brand/voices/narrator_en_A2.wav) by default.

Outputs <episode>/voice/takes_en/L{line:02d}_t{take}_s{seed}.wav (24 kHz mono) and appends to log.jsonl.
Each take uses a fixed seed, so any take can be regenerated exactly.
"""

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import wave
from mlx_audio.tts.utils import load_model

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402
# Local copy of mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16 (fetched by models/fetch_qwen3_tts.sh).
MODEL = str(kk.MODELS / "qwen3-tts-1.7b-base")

# One entry per spoken unit, from the episode's script/lines.json. Pauses are placed in the mix, not here.
LINES = kk.lines("en") if kk.os.environ.get("KK_EP") else []


def write_wav(path, audio, sr):
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=str(kk.NARRATOR_EN))
    ap.add_argument("--ref-text", default=str(kk.NARRATOR_EN_TEXT))
    ap.add_argument("--lines", default="", help="1-based, comma separated; default all")
    ap.add_argument("--takes", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--take-start", type=int, default=1, help="number new takes from here")
    ap.add_argument("--text", action="append", default=[],
                    help='punctuation-only override, e.g. 11="The child... had swallowed the flood."')
    ap.add_argument("--out-dir", default="takes_en", help="folder under the episode's voice/")
    args = ap.parse_args()

    ref_text = Path(args.ref_text).read_text().strip()
    picks = [int(x) for x in args.lines.split(",") if x] or range(1, len(LINES) + 1)
    out = kk.ep() / "voice" / args.out_dir
    out.mkdir(exist_ok=True)
    overrides = {int(k): v for k, v in (t.split("=", 1) for t in args.text)}

    t0 = time.time()
    model = load_model(MODEL)
    print(f"model loaded in {time.time() - t0:.1f}s")

    for n in picks:
        text = overrides.get(n, LINES[n - 1])
        for take in range(args.take_start, args.take_start + args.takes):
            seed = args.seed_base + n * 100 + take
            mx.random.seed(seed)
            t = time.time()
            chunks = [
                np.array(r.audio)
                for r in model.generate(
                    text=text,
                    ref_audio=args.ref,
                    ref_text=ref_text,
                    lang_code="english",
                    temperature=args.temperature,
                )
            ]
            audio = np.concatenate(chunks)
            gen_s = time.time() - t
            dur = len(audio) / model.sample_rate
            path = out / f"L{n:02d}_t{take}_s{seed}.wav"
            write_wav(path, audio, model.sample_rate)
            rec = dict(line=n, take=take, seed=seed, temperature=args.temperature,
                       text=text, file=path.name, audio_s=round(dur, 2),
                       gen_s=round(gen_s, 2), rtf=round(gen_s / dur, 2))
            print(rec)
            with open(out / "log.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")

    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
