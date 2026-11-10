"""Generate Hindi narration takes with Chatterbox Multilingual v3 (mlx-audio), cloning a reference voice.

The reference is the final Hindi narrator, a designed synthetic voice (no real person).

Usage: engine/kk.sh <episode> hindi_takes [--takes 3] [--lines 3,9] [--seed-base 3000]
Clones the final Hindi narrator (brand/voices/narrator_hi_D_ref.wav) by default.
Outputs <episode>/voice/takes_hi/L{nn}_t{take}_s{seed}.wav and log.jsonl.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
from mlx_audio.tts.utils import load_model

from gen_takes import write_wav

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kk  # noqa: E402
MODEL = str(kk.MODELS / "chatterbox-multilingual-v3")

# Same spoken units as the English lines, from the episode's script/lines.json. Pauses are placed in the mix.
LINES_HI = kk.lines("hi") if kk.os.environ.get("KK_EP") else []


def load_ref(path: str, sr: int) -> np.ndarray:
    """Decode any audio file to mono float32 at the model rate with ffmpeg (no extra Python packages)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=str(kk.NARRATOR_HI))
    ap.add_argument("--out-dir", default="takes_hi", help="folder under the episode's voice/")
    ap.add_argument("--lines", default="")
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=3000)
    ap.add_argument("--exaggeration", type=float, default=0.35)
    ap.add_argument("--cfg", type=float, default=0.5)
    ap.add_argument("--temperature", type=float, default=0.8)
    args = ap.parse_args()

    out = kk.ep() / "voice" / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    picks = [int(x) for x in args.lines.split(",") if x] or range(1, len(LINES_HI) + 1)

    t0 = time.time()
    model = load_model(MODEL)
    sr = model.sample_rate
    ref = mx.array(load_ref(args.ref, sr))
    print(f"model loaded in {time.time() - t0:.1f}s, sr {sr}, ref {len(ref) / sr:.1f}s")
    for n in picks:
        for take in range(1, args.takes + 1):
            seed = args.seed_base + n * 100 + take
            mx.random.seed(seed)
            t = time.time()
            audio = np.concatenate([np.array(r.audio) for r in model.generate(
                text=LINES_HI[n - 1], ref_audio=ref, lang_code="hi", exaggeration=args.exaggeration,
                cfg_weight=args.cfg, temperature=args.temperature, verbose=False)])
            dur = len(audio) / sr
            path = out / f"L{n:02d}_t{take}_s{seed}.wav"
            write_wav(path, audio, sr)
            rec = dict(line=n, take=take, seed=seed, file=path.name, audio_s=round(dur, 2),
                       gen_s=round(time.time() - t, 1), ref=args.ref)
            print(rec)
            with open(out / "log.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
