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

    def test_start_only_inside_the_night_window(self):
        for h, m in ((0, 29), (12, 0), (21, 0), (23, 59)):
            self.assertEqual(self.start(datetime(2026, 11, 19, h, m, tzinfo=TZ)), "STOP time", (h, m))
        self.assertTrue(self.start(datetime(2026, 11, 19, 0, 30, tzinfo=TZ)).startswith("START "))

    def test_run_window_seconds(self):
        at = lambda h, m: datetime(2026, 11, 19, h, m, tzinfo=TZ)
        self.assertEqual(produce.window_seconds(at(1, 0)), 5 * 3600)
        self.assertEqual(produce.window_seconds(at(5, 0)), 3600)
        self.assertEqual(produce.window_seconds(at(0, 30)), 5 * 3600)
        for h, m in ((0, 29), (5, 30), (6, 0), (13, 0), (23, 0)):
            self.assertEqual(produce.window_seconds(at(h, m)), 0, (h, m))
        with mock.patch.dict(os.environ, {"LOOP_WINDOW_OVERRIDE": "1"}):
            self.assertEqual(produce.window_seconds(at(13, 0)), 5 * 3600)

    def test_window_override_for_a_rehearsal(self):
        with mock.patch.dict(os.environ, {"LOOP_WINDOW_OVERRIDE": "1"}):
            self.assertTrue(self.start(datetime(2026, 11, 19, 15, 0, tzinfo=TZ)).startswith("START "))

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
        self.assertEqual(r["final_sha256"]["reel_with_song.mp4"], produce.sha256(d / "out/final/reel_with_song.mp4"))
        self.assertIn("reel_SILENT.mp4", r["final_sha256"])
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
        ok = "https://cdn.higgsfield.ai/a.mp4"
        for dest in ("../x.mp4", "out/final/reel_with_song.mp4", "audio/song.mp3", "/tmp/a.mp4"):
            with self.assertRaises(produce.ProduceError):
                produce.check_fetch(rid, ok, dest)
        self.assertEqual(produce.check_fetch(rid, ok, "out/hero_raw/c02.mp4"), self.eps / rid / "out/hero_raw/c02.mp4")
        produce.check_fetch(rid, "https://higgsfield.ai/a.wav", "audio/original_bed.wav")

    def test_url_hosts_are_pinned(self):
        rid = self.start().split()[1]
        bad = ("http://cdn.higgsfield.ai/a.mp4", "https://user:pw@cdn.higgsfield.ai/a.mp4",
               "https://cdn.higgsfield.ai:8443/a.mp4", "https://93.184.216.34/a.mp4", "https://[::1]/a.mp4",
               "https://localhost/a.mp4", "https://cdn.example.com/a.mp4", "https://higgsfield.ai.evil.com/a.mp4",
               "https://bucket.s3.amazonaws.com/a.mp4", "file:///etc/passwd")
        for url in bad:
            with self.assertRaises(produce.ProduceError, msg=url):
                produce.check_url(rid, url)
        self.assertEqual(produce.check_url(rid, "https://d8j0.cloudfront.net.higgsfield.ai/x"),
                         "d8j0.cloudfront.net.higgsfield.ai")

    def test_allow_host_records_only_recordable_suffixes(self):
        rid = self.start().split()[1]
        with self.assertRaises(produce.ProduceError):
            produce.allow_host(rid, "https://evil.example.com/x")
        with self.assertRaises(produce.ProduceError):
            produce.allow_host(rid, "https://10.0.0.1/x")
        produce.allow_host(rid, "https://hf-out.s3.us-east-1.amazonaws.com/abc?sig=1")
        self.assertEqual(self.rec(rid)["fetch_hosts"], ["hf-out.s3.us-east-1.amazonaws.com"])
        produce.check_url(rid, "https://hf-out.s3.us-east-1.amazonaws.com/other")
        with self.assertRaises(produce.ProduceError):
            produce.check_url(rid, "https://other.s3.us-east-1.amazonaws.com/x")

    def test_fetch_refuses_private_resolution(self):
        rid = self.start().split()[1]
        with mock.patch.object(produce, "_resolve", return_value=["127.0.0.1"]):
            with self.assertRaises(produce.ProduceError) as cm:
                produce.fetch(rid, "https://cdn.higgsfield.ai/a.mp4", "out/hero_raw/c02.mp4")
        self.assertIn("non-public", str(cm.exception))
        with mock.patch.object(produce, "_resolve", return_value=["192.168.1.4"]):
            (self.eps / rid / "out/keyframes").mkdir(parents=True)
            (self.eps / rid / "out/keyframes/s02.png").write_bytes(b"p")
            with self.assertRaises(produce.ProduceError):
                produce.put(rid, "out/keyframes/s02.png", "https://up.higgsfield.ai/x")

    def test_put_only_episode_stills(self):
        rid = self.start().split()[1]
        (self.eps / rid / "out/keyframes").mkdir(parents=True)
        (self.eps / rid / "out/keyframes/s02.png").write_bytes(b"p")
        self.assertEqual(produce.check_put(rid, "out/keyframes/s02.png", "https://up.higgsfield.ai/x"),
                         (self.eps / rid / "out/keyframes/s02.png").resolve())
        for f in ("../../secrets/youtube.json", "episode.json"):
            with self.assertRaises(produce.ProduceError):
                produce.check_put(rid, f, "https://up.higgsfield.ai/x")
        with self.assertRaises(produce.ProduceError):
            produce.check_put(rid, "out/keyframes/s02.png", "https://up.example.com/x")

    def test_clock_reports_minutes_left(self):
        rid = self.start().split()[1]
        t0 = datetime.fromisoformat(self.rec(rid)["history"][-1][0])
        out = produce.clock(rid, t0 + timedelta(minutes=50))
        self.assertIn("for 50 min of 75 (25 left)", out)

    def test_spend_over_cap_still_records_and_reports(self):
        rid = self.start().split()[1]
        self.spend.return_value = (False, "loop cap")
        out = produce.spend(rid, 3, "job1", NIGHT)
        self.assertIn("warning: over cap", out)
        ledger = json.loads((self.eps / "credits.json").read_text())
        self.assertEqual([(e["episode"], e["credits"], e["n"]) for e in ledger["entries"]], [(rid, 3.0, "audio")])
        self.assertEqual(self.inbox.call_args[0][1], "failure")

    def test_spend_only_known_purchases(self):
        rid = self.start().split()[1]
        with self.assertRaises(produce.ProduceError):
            produce.spend(rid, 3, "job1", NIGHT, what="hero")
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                produce.main(["spend", rid, "3", "--job", "j", "--what", "video"])

    def test_balance_reconciliation_flags_unrecorded_spend(self):
        root = Path(self.tmp.name)
        with mock.patch.object(produce, "RUN_FILE", root / "run.json"), \
                mock.patch.dict(os.environ, {"LOOP_RUN_START": (NIGHT - timedelta(minutes=30)).isoformat()}):
            produce.run_start_balance(100, NIGHT)
            rid = self.start().split()[1]
            produce.spend(rid, 3, "job1", NIGHT)
            self.inbox.reset_mock()
            self.assertIn("(ok)", produce.run_end_balance(96.5, NIGHT))      # 3.5 drop vs 3 logged: within 1
            self.inbox.assert_not_called()
        with mock.patch.object(produce, "RUN_FILE", root / "run2.json"), \
                mock.patch.dict(os.environ, {"LOOP_RUN_START": (NIGHT - timedelta(minutes=30)).isoformat()}):
            produce.run_start_balance(100, NIGHT)
            out = produce.run_end_balance(90, NIGHT)                        # 10 drop vs 3 logged
            self.assertIn("unrecorded Higgsfield spend", out)
            self.assertEqual(self.inbox.call_args[0][1], "failure")

    def test_unreconciled_run_is_reported(self):
        root = Path(self.tmp.name)
        with mock.patch.object(produce, "RUN_FILE", root / "run.json"):
            self.assertIsNotNone(produce.check_reconciled("2026-11-19T01:00:00+05:30"))
            with mock.patch.dict(os.environ, {"LOOP_RUN_START": "2026-11-19T01:00:00+05:30"}):
                produce.run_start_balance(50, NIGHT)
            self.assertIn("no run-end", produce.check_reconciled("2026-11-19T01:00:00+05:30"))
            self.assertIsNone(produce.check_reconciled(None))

    def test_voice_runs_kk_with_fixed_arguments(self):
        rid = self.start().split()[1]
        calls = []
        self.run.side_effect = lambda cmd, **kw: (calls.append([str(c) for c in cmd]),
                                                  subprocess.CompletedProcess(cmd, 0, "ok", ""))[1]
        produce.voice(rid, "hindi_takes", takes=3, lines="3,9")
        produce.voice(rid, "review_takes", pick="3:2")
        ep = str((self.eps / rid).resolve())
        self.assertEqual(calls[0][1:], [ep, "hindi_takes", "--takes", "3", "--lines", "3,9"])
        self.assertEqual(calls[1][1:], [ep, "review_takes", "--takes-dir", "takes_hi", "--out-dir", "review_hi",
                                        "--pick", "3:2"])
        self.assertTrue(calls[0][0].endswith("engine/kk.sh"))
        for bad in (dict(tool="../../x"), dict(tool="gen_takes"), dict(tool="hindi_takes", lines="1;rm"),
                    dict(tool="hindi_takes", takes=9), dict(tool="review_takes", pick="3:2 --out-dir /tmp")):
            with self.assertRaises(produce.ProduceError, msg=bad):
                produce.voice(rid, **bad)


FFMPEG_OK = os.path.exists(produce.FFMPEG) and os.path.exists(produce.FFPROBE)


@unittest.skipUnless(FFMPEG_OK, "ffmpeg not installed")
class MediaTest(unittest.TestCase):
    """The fixed-template ffmpeg wrappers, run for real on generated sources in a temp lab."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.eps, self.pool = root / "episodes", root / "music-lab/pool"
        for mod, attr, val in ((vqueue, "QUEUE", root / "queue.json"), (produce, "EPISODES", self.eps),
                               (produce, "POOL", self.pool), (produce, "LAB", root)):
            old = getattr(mod, attr)
            setattr(mod, attr, val)
            self.addCleanup(setattr, mod, attr, old)
        self.rid = "001-test"
        self.ep = self.eps / self.rid
        (self.ep / "out/final").mkdir(parents=True)
        (self.pool / "popular").mkdir(parents=True)
        add(self.rid, {"format": "music", "audio": "popular"}, "manual")
        transition(self.rid, "producing")
        ff = lambda *a: subprocess.run([produce.FFMPEG, "-y", "-v", "error", *a], check=True)
        ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "3.2", "-pix_fmt", "yuv420p",
           str(self.ep / "out/final/reel_with_song.mp4"))
        ff("-f", "lavfi", "-i", "aevalsrc=if(lt(mod(t\\,0.5)\\,0.03)\\,sin(2*PI*1000*t)\\,0):s=22050",
           "-t", "12", str(self.pool / "popular/click120.wav"))

    def test_probe(self):
        d = json.loads(produce.probe(self.rid, "out/final/reel_with_song.mp4"))
        self.assertAlmostEqual(float(d["format"]["duration"]), 3.2, places=1)
        self.assertEqual(d["streams"][0]["width"], 320)

    def test_frame_and_sheet(self):
        out = produce.frame(self.rid, "out/final/reel_with_song.mp4", 1.5)
        self.assertEqual(out, self.ep / "out/qa/frame_0001.50.png")
        self.assertTrue(out.exists())
        self.assertTrue(produce.frames(self.rid).exists())

    def test_inputs_and_outputs_are_confined(self):
        (self.eps / "002-other/out/final").mkdir(parents=True)
        (self.eps / "002-other/out/final/x.mp4").write_bytes(b"x")
        secret = Path(self.tmp.name) / "secret.txt"
        secret.write_text("token")
        (self.ep / "out/link.mp4").symlink_to(secret)
        for rel in ("../002-other/out/final/x.mp4", str(secret), "out/link.mp4", "https://x.higgsfield.ai/a.mp4"):
            with self.assertRaises(produce.ProduceError, msg=rel):
                produce.probe(self.rid, rel)
        with self.assertRaises(produce.ProduceError):
            produce.frame(self.rid, "../../music-lab/pool/popular/click120.wav", 0)
        with self.assertRaises(produce.ProduceError):
            produce._out_path(self.rid, "../002-other/out/final/x.mp4")
        with self.assertRaises(produce.ProduceError):
            produce._out_path(self.rid, "out/final/reel_with_song.mp4")

    def test_copy_song_cuts_from_the_pool_only(self):
        out = produce.copy_song(self.rid, "popular/click120.wav", start=2, dur=4)
        self.assertEqual(out, self.ep / "audio/song.wav")
        self.assertAlmostEqual(produce._duration(out), 4.0, places=1)
        produce.copy_song(self.rid, "music-lab/pool/popular/click120.wav", name="bed")
        for bad in ("../../episodes/001-test/out/final/reel_with_song.mp4", "/etc/hosts"):
            with self.assertRaises(produce.ProduceError, msg=bad):
                produce.copy_song(self.rid, bad)
        with self.assertRaises(produce.ProduceError):
            produce.copy_song(self.rid, "popular/click120.wav", name="../../../pipeline/x")

    def test_beats_finds_the_tempo(self):
        produce.copy_song(self.rid, "popular/click120.wav")
        g = produce.beats(self.rid, "audio/song.wav")
        self.assertAlmostEqual(g["bpm"], 120, delta=3)
        self.assertTrue(all(abs((b - g["beats"][0]) % 0.5) < 0.05 or abs((b - g["beats"][0]) % 0.5 - 0.5) < 0.05
                            for b in g["beats"]))


class KkShTest(unittest.TestCase):
    """engine/kk.sh validates the tool name and keeps the episode inside episodes/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Path(self.tmp.name).resolve()
        eng = self.lab / "engine"
        (eng / "voice/.venv/bin").mkdir(parents=True)
        (eng / "audio").mkdir()
        (eng / "kk.sh").write_text((Path(PIPELINE).parent / "engine/kk.sh").read_text())
        (eng / "kk.sh").chmod(0o755)
        py = eng / "voice/.venv/bin/python"
        py.write_text('#!/bin/sh\necho "RAN $1 KK_EP=$KK_EP"\n')
        py.chmod(0o755)
        (eng / "voice/hindi_takes.py").write_text("")
        (eng / "audio/dsp.py").write_text("")
        (self.lab / "episodes/001-a").mkdir(parents=True)
        (self.lab / "episodes/001-a/x.py").write_text("")
        (self.lab / "elsewhere").mkdir()

    def kk(self, *args):
        return subprocess.run(["bash", str(self.lab / "engine/kk.sh"), *args], capture_output=True, text=True)

    def test_known_tool_runs(self):
        r = self.kk("001-a", "hindi_takes", "--takes", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("voice/hindi_takes.py", r.stdout)
        self.assertIn("KK_EP=" + str(self.lab / "episodes/001-a"), r.stdout)

    def test_rejects_paths_and_unknown_tools(self):
        for tool in ("../../episodes/001-a/x", "dsp", "x", "hindi_takes.py", "HINDI_TAKES"):
            r = self.kk("001-a", tool)
            self.assertNotEqual(r.returncode, 0, tool)
            self.assertNotIn("RAN", r.stdout, tool)

    def test_rejects_episode_outside_episodes(self):
        for ep in (str(self.lab / "elsewhere"), "../elsewhere", str(self.lab / "episodes"), "/tmp"):
            r = self.kk(ep, "hindi_takes")
            self.assertNotEqual(r.returncode, 0, ep)
            self.assertNotIn("RAN", r.stdout, ep)


if __name__ == "__main__":
    unittest.main()
