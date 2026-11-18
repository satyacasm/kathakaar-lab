import json, os, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import plan
import produce
import vqueue
from vqueue import TZ, add, load, transition

NIGHT = datetime(2026, 11, 19, 1, 30, tzinfo=TZ)


def plan_text(rows):
    lines = ["| day | slot | format | audio | topic_source | locked | id |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines) + "\n"


class ProduceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.eps = root / "episodes"
        self.eps.mkdir()
        self.plan = root / "experiment_plan.md"
        for mod, attr, val in ((vqueue, "QUEUE", root / "queue.json"), (produce, "EPISODES", self.eps)):
            old = getattr(mod, attr)
            setattr(mod, attr, val)
            self.addCleanup(setattr, mod, attr, old)
        self.inbox = mock.patch.object(produce.inbox, "add").start()
        self.spend = mock.patch.object(produce, "_can_spend", return_value=(True, "ok")).start()
        self.popular = mock.patch.object(produce, "_popular_available", return_value=True).start()
        self.run = mock.patch.object(produce, "_run", side_effect=self.fake_run).start()
        self.addCleanup(mock.patch.stopall)
        self.calls = []
        self.upload_out = "uploaded: https://youtu.be/YT9\npreview_id=YT9\n"
        self.upload_rc = 0
        self.write_plan([("2026-11-19", "12:30", "music", "library", "trend_gap", "no", "")])

    # a fake subprocess layer: new_reel.sh scaffolds, ffprobe answers, ffmpeg writes the sheet, upload answers
    def fake_run(self, cmd, **kw):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        if cmd[0].endswith("new_reel.sh"):
            d = self.eps / cmd[1]
            (d / "script").mkdir(parents=True)
            (d / "episode.json").write_text(json.dumps(
                {"id": "E" + cmd[1][:3], "slug": cmd[1], "kind": "music_reel", "format": "music_reel",
                 "narration": False, "song": {"add_in_app": True}}))
            return subprocess.CompletedProcess(cmd, 0, "created", "")
        if "ffprobe" in cmd[0]:
            return subprocess.CompletedProcess(cmd, 0, "12.5\n", "")
        if "ffmpeg" in cmd[0]:
            Path(cmd[-1]).write_bytes(b"png")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if any(c.endswith("youtube_publish.py") for c in cmd):
            return subprocess.CompletedProcess(cmd, self.upload_rc, self.upload_out, "boom" if self.upload_rc else "")
        raise AssertionError(f"unexpected command {cmd}")

    def write_plan(self, rows):
        self.plan.write_text(plan_text(rows))

    def start(self, now=NIGHT, **kw):
        kw.setdefault("run_start", now - timedelta(minutes=30))
        return produce.start(now, self.plan, **kw)

    def make(self, rid, status, mode="api"):
        add(rid, {"format": "music", "audio": "library"}, mode)
        chain = {"producing": ["producing"], "preview_ready": ["producing", "preview_ready"],
                 "approved": ["producing", "preview_ready", "approved"]}[status]
        for s in chain:
            transition(rid, s)

    def rec(self, rid):
        return next(r for r in load() if r["id"] == rid)

    def package(self, rid, caption=True, video=True, yt=True, text="Jatayu's last flight"):
        d = self.eps / rid
        (d / "out/final").mkdir(parents=True, exist_ok=True)
        (d / "out/package").mkdir(parents=True, exist_ok=True)
        if video:
            (d / "out/final/reel_with_song.mp4").write_bytes(b"x")
            (d / "out/final/reel_SILENT.mp4").write_bytes(b"x")
        if yt:
            (d / "out/package/youtube.md").write_text(f"## Title\n{text}\n")
        if caption:
            (d / "out/package/caption_instagram.txt").write_text(text)
        return d

    # ---------------------------------------------------------------- start
    def test_start_stops_when_buffer_full(self):
        for i, s in enumerate(("preview_ready", "preview_ready", "approved", "preview_ready")):
            self.make(f"00{i}-x", s)
        self.assertEqual(self.start(), "STOP buffer")
        self.assertFalse(any(c[0].endswith("new_reel.sh") for c in self.calls))

    def test_start_stops_after_six(self):
        self.assertEqual(self.start(datetime(2026, 11, 19, 6, 5, tzinfo=TZ)), "STOP time")
        self.assertEqual(load(), [])

    def test_start_runs_in_the_evening(self):
        out = self.start(datetime(2026, 11, 19, 21, 0, tzinfo=TZ))
        self.assertTrue(out.startswith("START "), out)

    def test_start_time_uses_ist_not_system_tz(self):
        from datetime import timezone
        self.assertEqual(self.start(datetime(2026, 11, 19, 0, 35, tzinfo=timezone.utc)), "STOP time")  # 06:05 IST

    def test_start_sets_manual_for_popular(self):
        self.write_plan([("2026-11-19", "12:30", "music", "popular", "song_story", "no", "")])
        out = self.start(slug_hint="Jatayu Last Flight")
        self.assertEqual(out, "START 001-jatayu-last-flight music popular song_story")
        r = self.rec("001-jatayu-last-flight")
        self.assertEqual((r["ig_mode"], r["status"]), ("manual", "producing"))
        self.assertEqual((r["cell"]["format"], r["cell"]["audio"]), ("music", "popular"))

    def test_start_api_for_library_and_takes_plan_row(self):
        out = self.start()
        rid = out.split()[1]
        self.assertRegex(rid, r"^001-loop-music-20261119-1$")
        self.assertEqual(self.rec(rid)["ig_mode"], "api")
        self.assertEqual(plan.read(self.plan)[0]["id"], rid)
        ep = json.loads((self.eps / rid / "episode.json").read_text())
        self.assertEqual(ep["loop"]["format"], "music")

    def test_start_number_skips_demo_numbers(self):
        for d in ("007-raktabija", "009-kalabhairav", "900-pipeline-demo", "notes"):
            (self.eps / d).mkdir()
        out = self.start(slug_hint="x")
        self.assertEqual(out.split()[1], "010-x")

    def test_start_narrated_is_scaffolded_as_narrated_reel(self):
        self.write_plan([("2026-11-19", "12:30", "narrated", "bed", "untold_detail", "no", "")])
        rid = self.start().split()[1]
        self.assertTrue(any(c[0].endswith("new_reel.sh") and c[1] == rid for c in self.calls))
        ep = json.loads((self.eps / rid / "episode.json").read_text())
        self.assertEqual((ep["kind"], ep["narration"]), ("narrated_reel", True))

    def test_start_claim_kind(self):
        self.write_plan([("2026-11-19", "12:30", "claim", "bed", "untold_detail", "no", "")])
        rid = self.start().split()[1]
        self.assertEqual(json.loads((self.eps / rid / "episode.json").read_text())["kind"], "claim_reel")

    def test_start_falls_back_when_over_budget(self):
        self.spend.return_value = (False, "loop cap: 148 spent + 10 > 150 for 2026-11")
        out = self.start(slug_hint="hanuman")
        self.assertEqual(out, "START 001-hanuman narrated bed trend_gap")
        r = self.rec("001-hanuman")
        self.assertEqual(r["cell"]["planned"], "music/library")
        self.assertEqual(r["ig_mode"], "api")
        self.assertEqual(self.inbox.call_args[0][1], "info")

    def test_start_falls_back_when_no_popular_song(self):
        self.popular.return_value = False
        self.write_plan([("2026-11-19", "12:30", "dialogue", "popular", "dialogue_catalogue", "no", "")])
        out = self.start(slug_hint="karna")
        self.assertEqual(out.split()[2:4], ["narrated", "bed"])
        self.assertEqual(self.rec("001-karna")["ig_mode"], "api")
        self.assertEqual(self.inbox.call_args[0][1], "decision")

    def test_start_stops_at_max_videos(self):
        self.write_plan([("2026-11-19", "12:30", "narrated", "bed", "trend_gap", "no", ""),
                         ("2026-11-19", "19:30", "claim", "bed", "trend_gap", "no", "")])
        rid = self.start(max_videos=1).split()[1]
        produce.fail(rid, "test")
        self.assertEqual(self.start(max_videos=1), "STOP max")

    def test_start_stops_without_open_rows(self):
        self.write_plan([("2026-11-19", "12:30", "music", "library", "trend_gap", "no", "005-done")])
        self.assertEqual(self.start(), "STOP plan")

    def test_start_refuses_while_a_video_is_open(self):
        rid = self.start().split()[1]
        with self.assertRaises(produce.ProduceError) as cm:
            self.start()
        self.assertIn(rid, str(cm.exception))

    def test_start_fails_records_left_producing_by_an_earlier_run(self):
        self.make("004-old", "producing")
        out = self.start(run_start=NIGHT + timedelta(minutes=1))
        self.assertTrue(out.startswith("START"), out)
        self.assertEqual(self.rec("004-old")["status"], "failed")
        self.assertIn("interrupted", self.rec("004-old")["reason"])

    def test_sweep_fails_every_producing_record(self):
        rid = self.start().split()[1]
        self.make("004-done", "preview_ready")
        self.assertEqual(produce.sweep(reason="alarm"), [rid])
        self.assertEqual((self.rec(rid)["status"], self.rec(rid)["reason"]), ("failed", "alarm"))
        self.assertEqual(self.rec("004-done")["status"], "preview_ready")
        self.assertEqual(self.inbox.call_args[0][1], "failure")

    def test_cli_start_prints_stop(self):
        with mock.patch("sys.stdout") as so:
            rc = produce.main(["--plan", str(self.plan), "start", "--now", "2026-11-19T07:00:00+05:30"])
        self.assertEqual(rc, 0)
        self.assertIn("STOP time", "".join(c.args[0] for c in so.write.call_args_list))

    # ---------------------------------------------------------------- finish
    def test_finish_requires_package(self):
        rid = self.start().split()[1]
        self.package(rid, caption=False)
        with self.assertRaises(produce.ProduceError) as cm:
            produce.finish(rid)
        self.assertIn("caption_instagram.txt", str(cm.exception))
        self.assertEqual(self.rec(rid)["status"], "producing")
        self.assertFalse(any(c[-1] == "--preview" for c in self.calls))

    def test_finish_uploads_and_marks_ready(self):
        rid = self.start().split()[1]
        d = self.package(rid)
        self.assertEqual(produce.finish(rid), f"READY {rid} YT9")
        r = self.rec(rid)
        self.assertEqual((r["status"], r["yt_id"]), ("preview_ready", "YT9"))
        self.assertTrue((d / "out/qa/frames.png").exists())
        up = next(c for c in self.calls if any(x.endswith("youtube_publish.py") for x in c))
        self.assertEqual(up[-5:], ["publish", rid, "--video", "reel_with_song.mp4", "--preview"])
        ff = next(c for c in self.calls if "ffmpeg" in c[0])
        self.assertIn("tile=", " ".join(ff))
        self.assertIn("fps=1", " ".join(ff))

    def test_finish_upload_failure_keeps_producing(self):
        rid = self.start().split()[1]
        self.package(rid)
        self.upload_rc, self.upload_out = 1, "quota exceeded\n"
        with self.assertRaises(produce.ProduceError) as cm:
            produce.finish(rid)
        self.assertIn("upload", str(cm.exception))
        self.assertEqual(self.rec(rid)["status"], "producing")

    def test_finish_upload_without_id_is_a_failure(self):
        rid = self.start().split()[1]
        self.package(rid)
        self.upload_out = "uploaded somewhere\n"
        with self.assertRaises(produce.ProduceError):
            produce.finish(rid)
        self.assertEqual(self.rec(rid)["status"], "producing")

    def test_finish_refuses_style_name_in_copy(self):
        rid = self.start().split()[1]
        self.package(rid, text="A Pattachitra tale of Jatayu")
        with self.assertRaises(produce.ProduceError) as cm:
            produce.finish(rid)
        self.assertIn("pattachitra", str(cm.exception).lower())
        self.assertEqual(self.rec(rid)["status"], "producing")

    def test_finish_manual_needs_silent_master(self):
        self.write_plan([("2026-11-19", "12:30", "music", "popular", "song_story", "no", "")])
        rid = self.start().split()[1]
        d = self.package(rid)
        (d / "out/final/reel_SILENT.mp4").unlink()
        with self.assertRaises(produce.ProduceError) as cm:
            produce.finish(rid)
        self.assertIn("reel_SILENT.mp4", str(cm.exception))

    def test_finish_only_from_producing(self):
        self.make("003-x", "preview_ready")
        self.package("003-x")
        with self.assertRaises(produce.ProduceError):
            produce.finish("003-x")

    # ---------------------------------------------------------------- fail / fallback
    def test_fail_marks_failed_and_writes_inbox(self):
        rid = self.start().split()[1]
        produce.fail(rid, "research found no text\nsupport")
        r = self.rec(rid)
        self.assertEqual((r["status"], r["reason"]), ("failed", "research found no text support"))
        text, kind = self.inbox.call_args[0]
        self.assertEqual(kind, "failure")
        self.assertIn(rid, text)

    def test_fallback_switches_cell_and_kind(self):
        self.write_plan([("2026-11-19", "12:30", "music", "popular", "song_story", "no", "")])
        rid = self.start().split()[1]
        produce.fallback(rid, "hero over cap")
        r = self.rec(rid)
        self.assertEqual((r["cell"]["format"], r["cell"]["audio"], r["ig_mode"]), ("narrated", "bed", "api"))
        self.assertEqual(r["cell"]["planned"], "music/popular")
        ep = json.loads((self.eps / rid / "episode.json").read_text())
        self.assertEqual(ep["kind"], "narrated_reel")

    # ---------------------------------------------------------------- helpers
    def test_voice_timing_lays_takes_end_to_end(self):
        rid = self.start().split()[1]
        d = self.eps / rid
        (d / "voice/review_hi").mkdir(parents=True)
        (d / "voice/takes_hi").mkdir(parents=True)
        (d / "voice/review_hi/picks.json").write_text(json.dumps({"1": "L01_t2.wav", "2": "L02_t1.wav"}))
        for f in ("L01_t2.wav", "L02_t1.wav"):
            (d / "voice/takes_hi" / f).write_bytes(b"w")
        (d / "script/lines.json").write_text(json.dumps({"en": ["a", "b"], "hi": ["क", "ख"],
                                                         "pause_after": {"1": 0.5}}))
        produce.voice_timing(rid)  # ffprobe says 12.5 s per take
        t = json.loads((d / "timing_hi.json").read_text())
        self.assertEqual([(l["line"], l["start"], l["end"]) for l in t["lines"]], [(1, 0.4, 12.9), (2, 13.4, 25.9)])
        picks = json.loads((d / "voice/picks_hi.json").read_text())
        self.assertEqual(picks, {"takes_dir": "voice/takes_hi", "picks": {"1": "L01_t2.wav", "2": "L02_t1.wav"}})

    def test_fetch_destination_is_restricted(self):
        rid = self.start().split()[1]
        for dest in ("../x.mp4", "out/final/reel_with_song.mp4", "audio/song.mp3", "/tmp/a.mp4"):
            with self.assertRaises(produce.ProduceError):
                produce.check_fetch(rid, "https://cdn.example.com/a.mp4", dest)
        with self.assertRaises(produce.ProduceError):
            produce.check_fetch(rid, "http://cdn.example.com/a.mp4", "out/hero_raw/c02.mp4")
        self.assertEqual(produce.check_fetch(rid, "https://cdn.example.com/a.mp4", "out/hero_raw/c02.mp4"),
                         self.eps / rid / "out/hero_raw/c02.mp4")
        produce.check_fetch(rid, "https://cdn.example.com/a.wav", "audio/original_bed.wav")

    def test_put_only_episode_stills(self):
        rid = self.start().split()[1]
        (self.eps / rid / "out/keyframes").mkdir(parents=True)
        (self.eps / rid / "out/keyframes/s02.png").write_bytes(b"p")
        self.assertEqual(produce.check_put(rid, "out/keyframes/s02.png", "https://up.example.com/x"),
                         self.eps / rid / "out/keyframes/s02.png")
        for f in ("../../secrets/youtube.json", "episode.json"):
            with self.assertRaises(produce.ProduceError):
                produce.check_put(rid, f, "https://up.example.com/x")

    def test_clock_reports_minutes_left(self):
        rid = self.start().split()[1]
        t0 = datetime.fromisoformat(self.rec(rid)["history"][-1][0])
        out = produce.clock(rid, t0 + timedelta(minutes=50))
        self.assertIn("for 50 min of 75 (25 left)", out)

    def test_spend_refuses_over_cap(self):
        rid = self.start().split()[1]
        self.spend.return_value = (False, "loop cap")
        with self.assertRaises(produce.ProduceError):
            produce.spend(rid, 3, "job1", NIGHT)


if __name__ == "__main__":
    unittest.main()
