"""Shared helpers for the motion and finish stages: episode JSON, clip timing, ffmpeg pipe writer, tool paths.

Kept free of other agents' modules so motion/finish work even while shots.py is changing.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

LAB = Path(__file__).resolve().parents[2]
FFMPEG = "/opt/homebrew/bin/ffmpeg" if Path("/opt/homebrew/bin/ffmpeg").exists() else (shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = str(Path(FFMPEG).with_name("ffprobe"))
TOOLS = LAB / "tools"
MODELS = LAB / "models"
RIFE_DIR = TOOLS / "rife" / "rife-ncnn-vulkan-20221029-macos"
RIFE_BIN = RIFE_DIR / "rife-ncnn-vulkan"
RIFE_MODEL = RIFE_DIR / "rife-v4.6"
ESRGAN_DIR = TOOLS / "esrgan"
ESRGAN_BIN = ESRGAN_DIR / "realesrgan-ncnn-vulkan"
DEPTH_ONNX = MODELS / "depth-anything-v2-small" / "model.onnx"

HANDLE = 0.5  # seconds of extra footage after the bar span


def load_cfg() -> dict:
    p = Path(__file__).resolve().parent / "config.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def clip_spec() -> tuple[int, int, int]:
    c = load_cfg().get("clip", {})
    return int(c.get("width", 1920)), int(c.get("height", 1080)), int(c.get("fps", 30))


def load_episode(ep_dir) -> tuple[Path, dict, dict]:
    ep = Path(ep_dir).resolve()
    shots = json.loads((ep / "script" / "shots.json").read_text())
    edit = json.loads((ep / "script" / "edit.json").read_text())
    return ep, shots, edit


def shot_span(edit: dict, n: int) -> tuple[float, float]:
    """(bar span seconds, seconds per beat assuming 4 beats per bar) for shot n."""
    bars = edit["bars"]
    for e in edit.get("shots", []):
        if int(e["n"]) == int(n):
            a, b = int(e["from_bar"]), int(e["to_bar"])
            span = float(bars[b]) - float(bars[a])
            beat = span / max(1, 4 * (b - a))
            return span, beat
    raise KeyError(f"shot {n} is not in edit.json")


def clip_seconds(edit: dict, n: int) -> float:
    return shot_span(edit, n)[0] + HANDLE


def kf(ep: Path, n: int, pose: str | None = None) -> Path:
    name = f"s{int(n):02d}.png" if not pose else f"s{int(n):02d}_{pose}.png"
    return ep / "out" / "keyframes" / name


def clip_out(ep: Path, n: int) -> Path:
    return ep / "out" / "clips" / f"c{int(n):02d}.mp4"


def want(n, only) -> bool:
    return only is None or int(n) in {int(x) for x in only}


class FrameWriter:
    """Pipe RGB uint8 frames to ffmpeg -> H.264 yuv420p mp4, no audio. Writes to a temp name, renames on close."""

    def __init__(self, path: Path, w: int, h: int, fps: int, crf: int = 16, preset: str = "medium"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tmp = self.path.with_name(self.path.stem + ".part.mp4")
        self.w, self.h, self.n = w, h, 0
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
               "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-tune", "film",
               "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
               "-movflags", "+faststart", str(self.tmp)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, rgb: np.ndarray):
        assert rgb.shape == (self.h, self.w, 3) and rgb.dtype == np.uint8, rgb.shape
        self.proc.stdin.write(np.ascontiguousarray(rgb).tobytes())
        self.n += 1

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {self.path}")
        self.tmp.replace(self.path)

    def abort(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.kill()
        self.tmp.unlink(missing_ok=True)


def probe(path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
                          "-show_entries", "stream=width,height,r_frame_rate,pix_fmt,nb_read_frames,codec_name:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"w": s["width"], "h": s["height"], "fps": float(num) / float(den), "pix_fmt": s["pix_fmt"],
            "codec": s["codec_name"], "frames": int(s.get("nb_read_frames", 0)),
            "duration": float(d["format"]["duration"])}


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
