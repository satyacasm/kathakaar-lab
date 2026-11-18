"""Narration track for narrated Kathakaar Shorts.

Builds one audio file (Hindi voice-over at each line's timing_hi.json start, plus an optional ducked music
bed) and wires it into script/edit.json as the "song", so the music-reel assembler renders the narrated
reel unchanged. Captions come from the same timing, so audio and captions share one timeline.

The engine's build_sound_hi retimes an English master with warping, music and SFX; that is a different
job, so this module has its own small ffmpeg builder.

  narration.py mix <episode dir> [--bed FILE]
  narration.py wire <episode dir>
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TAIL = 1.5
FADE = 0.4
MIX_REL = "audio/narration_mix.wav"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
LOCAL_ONLY = ["-protocol_whitelist", "file,pipe"]   # input option: local files only
LAB = Path(__file__).resolve().parents[2]
EPISODES = LAB / "episodes"
POOL = LAB / "music-lab/pool"


class NarrationError(Exception):
    pass


def _inside(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def check_episode(ep) -> Path:
    """CLI guard: the episode must be a folder directly inside <lab>/episodes (symlinks resolved)."""
    p = Path(ep).resolve()
    if not p.is_dir() or p.parent != Path(EPISODES).resolve():
        raise NarrationError(f"episode must be a folder directly inside episodes/: {ep}")
    return p


def check_bed(bed, ep: Path) -> Path:
    """CLI guard: the bed must be an existing file inside music-lab/pool/ or the episode."""
    p = Path(bed).resolve()
    if not p.is_file() or not (_inside(p, Path(POOL).resolve()) or _inside(p, ep)):
        raise NarrationError(f"bed must be a file in music-lab/pool/ or the episode: {bed}")
    return p


def _json(path: Path):
    return json.loads(Path(path).read_text())


def duration(path) -> float:
    out = subprocess.run([FFPROBE, *LOCAL_ONLY, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def _placed_takes(ep: Path):
    """[(start_s, take_path)] for every timed line, from picks_hi.json and timing_hi.json."""
    picks = _json(ep / "voice/picks_hi.json")
    takes_dir = ep / picks["takes_dir"]
    out = []
    for ln in _json(ep / "timing_hi.json")["lines"]:
        name = picks["picks"].get(str(ln["line"]))
        if name is None:
            raise ValueError(f"no picked take for line {ln['line']}")
        take = takes_dir / name
        if not take.exists():
            raise FileNotFoundError(take)
        if not _inside(take.resolve(), ep.resolve()):
            raise NarrationError(f"take {take} is outside the episode")
        out.append((float(ln["start"]), take))
    if not out:
        raise ValueError("timing_hi.json has no lines")
    return out


def build_mix(ep: Path, bed: Path | None, bed_db: float = -18.0) -> Path:
    ep = Path(ep)
    placed = _placed_takes(ep)
    voice_len = max(s + duration(t) for s, t in placed)
    total = voice_len + TAIL
    cmd = [FFMPEG, "-y", "-v", "error"]
    for _, t in placed:
        cmd += [*LOCAL_ONLY, "-i", str(t)]
    parts = []
    for i, (s, _) in enumerate(placed):
        ms = int(round(s * 1000))
        parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
    n = len(placed)
    labels = "".join(f"[v{i}]" for i in range(n))
    parts.append(f"{labels}amix=inputs={n}:normalize=0:duration=longest,apad=whole_dur={total:.3f}[voice]")
    if bed is not None:
        cmd += ["-stream_loop", "-1", *LOCAL_ONLY, "-i", str(bed)]
        parts.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={bed_db}dB,"
                     f"atrim=0:{total:.3f}[bed]")
        parts.append("[voice][bed]amix=inputs=2:normalize=0:duration=first[m]")
    else:
        parts.append("[voice]anull[m]")
    parts.append(f"[m]atrim=0:{total:.3f},afade=t=out:st={total - FADE:.3f}:d={FADE}[out]")
    out = ep / MIX_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", ";".join(parts), "-map", "[out]", "-ar", "44100", "-ac", "2", str(out)]
    subprocess.run(cmd, check=True)
    return out


def captions_from_timing(ep: Path, lang: str = "en") -> list[dict]:
    ep = Path(ep)
    texts = _json(ep / "script/lines.json")[lang]
    caps = []
    for ln in _json(ep / "timing_hi.json")["lines"]:
        t1 = float(ln["end"]) + min(float(ln.get("pause_after", 0) or 0), 0.3)
        caps.append({"text": texts[int(ln["line"]) - 1], "t0": round(float(ln["start"]), 3), "t1": round(t1, 3)})
    return caps


def wire_edit(ep: Path) -> None:
    ep = Path(ep)
    mix = ep / MIX_REL
    dur = round(duration(mix), 3)
    path = ep / "script/edit.json"
    edit = _json(path)
    edit["song"] = MIX_REL
    edit["song_in"] = 0
    edit["song_out"] = dur
    edit["captions"] = captions_from_timing(ep, "en")
    bars = edit.get("bars") or [0.0]
    if bars[-1] < dur - (TAIL + 0.1) or bars[-1] > dur:
        raise NarrationError(f"bars end at {bars[-1]} s but the narration mix is {dur} s: "
                             "author bars/shots to cover it")
    path.write_text(json.dumps(edit, indent=1, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mix")
    m.add_argument("ep", type=Path)
    m.add_argument("--bed", type=Path)
    w = sub.add_parser("wire")
    w.add_argument("ep", type=Path)
    a = ap.parse_args(argv)
    try:
        ep = check_episode(a.ep)
        if a.cmd == "mix":
            print(build_mix(ep, check_bed(a.bed, ep) if a.bed else None))
        else:
            wire_edit(ep)
    except NarrationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
