import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import narration

# shots.validate lazily imports reel modules that need cv2/numpy (reel venv only); the song checks
# never use them, so stub whatever is missing.
from unittest import mock
for _m in ("cv2", "numpy", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "PIL.ImageFilter"):
    try:
        __import__(_m)
    except ImportError:
        sys.modules[_m] = mock.MagicMock()
from reel import shots

FFMPEG = "/opt/homebrew/bin/ffmpeg"


def sine(path, dur, freq=440):
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
                    "-ar", "44100", str(path)], check=True)


def make_episode(root, lines=((0.5, 3.0, 4.0), (4.5, 10.0, 0.0)), take_len=None):
    """lines: (start, end, pause_after). Each take is a sine of (end - start) s unless take_len given."""
    ep = Path(root) / "ep"
    (ep / "voice/clean_hi").mkdir(parents=True)
    (ep / "script").mkdir()
    (ep / "audio").mkdir()
    picks = {}
    tl = []
    for i, (s, e, pa) in enumerate(lines, 1):
        name = f"L{i:02d}.wav"
        sine(ep / "voice/clean_hi" / name, take_len or (e - s), 300 + 100 * i)
        picks[str(i)] = name
        tl.append({"line": i, "start": s, "end": e, "pause_after": pa})
    (ep / "voice/picks_hi.json").write_text(json.dumps({"takes_dir": "voice/clean_hi", "picks": picks}))
    (ep / "timing_hi.json").write_text(json.dumps({"lead_in": 0.5, "total": lines[-1][1], "lines": tl}))
    (ep / "script/lines.json").write_text(json.dumps(
        {"en": [f"English {i}" for i in range(1, len(lines) + 1)], "hi": [f"hindi {i}" for i in range(1, len(lines) + 1)]}))
    (ep / "script/edit.json").write_text(json.dumps({
        "song": "audio/song.wav", "song_in": 0.0, "song_out": 60.0, "fade_out": 1.6,
        "size": [1080, 1920], "fps": 30, "layout": "full", "bars": [0.0, 2.5],
        "shots": [{"n": 1, "clip": "out/clips/c01.mp4", "from_bar": 0, "to_bar": 1, "in": 0.0}],
        "captions": [], "transitions": [], "grade": {}}))
    (ep / "script/shots.json").write_text(json.dumps({"style": "watercolor_ink", "characters": {}, "shots": [
        {"n": 1, "prompt": "", "characters": [], "seed": 101, "source": "local",
         "motion": {"type": "drift"}, "fx": []}]}))
    return ep


class TestNarration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_mix_length_is_voice_plus_tail(self):
        ep = make_episode(self.tmp.name)  # voice ends at 4.5 + 5.5 = 10.0
        out = narration.build_mix(ep, None)
        self.assertEqual(out, ep / "audio/narration_mix.wav")
        self.assertAlmostEqual(narration.duration(out), 11.5, delta=0.05)

    def test_mix_with_bed_is_trimmed_to_same_length(self):
        ep = make_episode(self.tmp.name)
        bed = Path(self.tmp.name) / "bed.wav"
        sine(bed, 3.0, 110)  # shorter than the voice: must loop
        out = narration.build_mix(ep, bed)
        self.assertAlmostEqual(narration.duration(out), 11.5, delta=0.05)

    def test_captions_follow_timing(self):
        ep = make_episode(self.tmp.name)
        caps = narration.captions_from_timing(ep)
        self.assertEqual(caps, [{"text": "English 1", "t0": 0.5, "t1": 3.3},
                                {"text": "English 2", "t0": 4.5, "t1": 10.0}])
        self.assertEqual(narration.captions_from_timing(ep, "hi")[0]["text"], "hindi 1")

    def test_wire_edit_passes_check(self):
        ep = make_episode(self.tmp.name)
        narration.build_mix(ep, None)
        narration.wire_edit(ep)
        edit = json.loads((ep / "script/edit.json").read_text())
        self.assertEqual(edit["song"], "audio/narration_mix.wav")
        self.assertEqual(edit["song_in"], 0)
        self.assertAlmostEqual(edit["song_out"], 11.5, delta=0.05)
        self.assertLessEqual(edit["bars"][-1], edit["song_out"])
        self.assertEqual(len(edit["captions"]), 2)
        rep = shots.validate(ep)
        self.assertEqual([e for e in rep.errors + rep.warnings if "song" in e], [])

    def test_wire_edit_clamps_long_bars(self):
        ep = make_episode(self.tmp.name)
        narration.build_mix(ep, None)
        p = ep / "script/edit.json"
        e = json.loads(p.read_text())
        e["bars"] = [0.0, 5.0, 20.0]
        p.write_text(json.dumps(e))
        narration.wire_edit(ep)
        e = json.loads(p.read_text())
        self.assertLessEqual(e["bars"][-1], e["song_out"])
        self.assertGreater(e["bars"][-1], e["bars"][-2])


if __name__ == "__main__":
    unittest.main()
