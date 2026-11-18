import json, os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import vqueue
import publish
from vqueue import TZ, add, load, transition


def at(h, m, day=18):
    return datetime(2026, 11, day, h, m, tzinfo=TZ)


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for mod, attr, val in ((vqueue, "QUEUE", root / "queue.json"), (publish, "EPISODES", root / "episodes"),
                               (publish, "LOCKFILE", root / "locks" / "publish.flock")):
            old = getattr(mod, attr)
            setattr(mod, attr, val)
            self.addCleanup(setattr, mod, attr, old)
        self.eps = root / "episodes"
        self.yt = mock.patch.object(publish.youtube_publish, "set_privacy", return_value="public").start()
        self.ig = mock.patch.object(publish.instagram_publish, "publish_reel",
                                    return_value={"media_id": "M1", "permalink": "https://ig/p"}).start()
        self.inbox = mock.patch.object(publish.inbox, "add").start()
        mock.patch("subprocess.run").start()  # nothing may ever fire an osascript
        self.addCleanup(mock.patch.stopall)

    def make(self, rid="ep1", mode="api", slot="2026-11-18T12:30:00+05:30", yt_id="YT1", song=None):
        d = self.eps / rid
        (d / "out/final").mkdir(parents=True)
        (d / "out/package").mkdir(parents=True)
        (d / "out/package/caption_instagram.txt").write_text("caption")
        (d / "out/final/reel_with_song.mp4").write_bytes(b"x")
        (d / "out/final/reel_SILENT.mp4").write_bytes(b"x")
        (d / "episode.json").write_text(json.dumps({
            "id": rid, "title_en": "Vishwaroop", "song": song or {"title": "Hare Krishna", "instagram_start": "0:42"},
            "published": {"youtube_preview": {"id": yt_id}}}))
        add(rid, {"format": "f", "audio": "a", "slot_pref": "any"}, mode)
        for s in ("producing", "preview_ready"):
            transition(rid, s, yt_id=yt_id)
        transition(rid, "approved", slot=slot)
        return d

    def rec(self, rid="ep1"):
        return next(r for r in load() if r["id"] == rid)

    def test_posts_due_api_record(self):
        d = self.make()
        self.assertEqual(publish.run_slot(at(12, 31)), "posted")
        self.yt.assert_called_once_with("YT1", "public")
        self.ig.assert_called_once_with(d, "reel_with_song.mp4", on_container=mock.ANY)
        r = self.rec()
        self.assertEqual((r["status"], r["ig_media_id"], r["yt_public"]), ("posted", "M1", True))
        self.assertTrue(r["posted_at"])
        yt = json.loads((d / "episode.json").read_text())["published"]
        self.assertEqual(yt["youtube"]["url"], "https://youtube.com/shorts/YT1")
        self.assertEqual(yt["youtube"]["privacy"], "public")
        self.assertIn("youtube_preview", yt)

    def test_ig_failure_then_retry_without_youtube_again(self):
        self.make()
        self.ig.side_effect = SystemExit("Instagram API error 500")
        self.assertEqual(publish.run_slot(at(12, 31)), "ig_retry_pending")
        r = self.rec()
        self.assertEqual((r["status"], r["ig_retry"], r["yt_public"]), ("approved", 1, True))
        self.ig.side_effect = None
        self.assertEqual(publish.run_slot(at(19, 31)), "posted")  # next slot run: slot is stale but retry still happens
        self.yt.assert_called_once_with("YT1", "public")
        self.assertEqual(self.rec()["status"], "posted")

    def test_second_ig_failure_marks_failed_and_inbox(self):
        self.make()
        self.ig.side_effect = SystemExit("boom")
        publish.run_slot(at(12, 31))
        self.assertEqual(publish.run_slot(at(19, 31)), "failed")
        self.assertEqual(self.rec()["status"], "failed")
        self.assertTrue(any(c.args[1] == "failure" for c in self.inbox.call_args_list))
        self.assertEqual(self.ig.call_count, 2)
        self.assertEqual(publish.run_slot(at(21, 0)), "nothing_due")  # never a third try

    def test_late_by_more_than_grace_moves_to_next_slot(self):
        self.make()
        self.assertEqual(publish.run_slot(at(15, 10)), "moved")
        self.assertEqual(datetime.fromisoformat(self.rec()["slot"]), at(19, 30))
        self.yt.assert_not_called()
        self.ig.assert_not_called()
        self.assertEqual(self.inbox.call_args.args[1], "info")

    def test_manual_mode_hands_off(self):
        d = self.make(mode="manual")
        self.assertEqual(publish.run_slot(at(12, 30)), "handed_off")
        self.yt.assert_called_once_with("YT1", "public")
        self.ig.assert_not_called()
        r = self.rec()
        self.assertEqual((r["status"], r["ig_manual_pending"]), ("posted", True))
        text, kind = self.inbox.call_args.args[:2]
        self.assertEqual(kind, "decision")
        for want in ("reel_SILENT.mp4", "Hare Krishna", "0:42", "https://youtube.com/shorts/YT1", str(d)):
            self.assertIn(want, text)

    def test_nothing_due(self):
        self.assertEqual(publish.run_slot(at(12, 30)), "nothing_due")
        self.make(slot="2026-11-18T19:30:00+05:30")
        self.assertEqual(publish.run_slot(at(12, 30)), "nothing_due")
        self.yt.assert_not_called()

    def test_only_approved_records_touched(self):
        self.make()
        add("raw", {"format": "f", "audio": "a", "slot_pref": "any"}, "api")
        transition("raw", "producing"); transition("raw", "preview_ready", yt_id="YT9")
        publish.run_slot(at(12, 31))
        self.yt.assert_called_once_with("YT1", "public")
        self.assertEqual(self.rec("raw")["status"], "preview_ready")

    def test_youtube_failure_keeps_private_and_second_failure_fails(self):
        self.make()
        self.yt.side_effect = publish.youtube_publish.YTError(500, "x")
        self.assertEqual(publish.run_slot(at(12, 31)), "yt_retry_pending")
        self.assertEqual(self.rec()["status"], "approved")
        self.assertFalse(self.rec().get("yt_public"))
        self.ig.assert_not_called()
        self.assertEqual(publish.run_slot(at(12, 40)), "failed")
        self.assertEqual(self.rec()["status"], "failed")

    def test_dry_run_changes_nothing(self):
        self.make()
        before = json.dumps(load())
        out = []
        self.assertEqual(publish.run_slot(at(12, 31), dry_run=True, say=out.append), "posted")
        self.assertEqual(json.dumps(load()), before)
        for m in (self.yt, self.ig, self.inbox):
            m.assert_not_called()
        self.assertTrue(any("YT1" in l for l in out))

    def test_missing_video_blocks_before_going_public(self):
        d = self.make()
        (d / "out/final/reel_with_song.mp4").unlink()
        self.assertEqual(publish.run_slot(at(12, 31)), "failed")
        self.yt.assert_not_called()
        self.assertEqual(self.rec()["status"], "failed")

    def _ig_writes_meta(self, d, media_id="M1"):
        def fake(ep, video, on_container=None):
            if on_container:
                on_container("C1")
            m = json.loads((d / "episode.json").read_text())
            m["published"]["instagram"] = {"media_id": media_id}
            (d / "episode.json").write_text(json.dumps(m))
            return {"media_id": media_id, "permalink": None}
        return fake

    def test_adopts_existing_instagram_post(self):
        d = self.make()
        m = json.loads((d / "episode.json").read_text())
        m["published"]["instagram"] = {"media_id": "OLD"}
        (d / "episode.json").write_text(json.dumps(m))
        self.assertEqual(publish.run_slot(at(12, 31)), "posted")
        self.ig.assert_not_called()
        self.assertEqual(self.rec()["ig_media_id"], "OLD")

    def test_queue_write_failure_after_ig_post_then_rerun_adopts(self):
        d = self.make()
        self.ig.side_effect = self._ig_writes_meta(d)
        with mock.patch.object(publish.vqueue, "transition", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                publish.run_slot(at(12, 31))
        self.assertEqual(self.rec()["status"], "approved")
        self.assertEqual(publish.run_slot(at(12, 40)), "posted")
        self.assertEqual(self.ig.call_count, 1)
        self.assertEqual(self.yt.call_count, 1)
        self.assertEqual(self.rec()["ig_media_id"], "M1")

    def test_missing_caption_fails_before_going_public(self):
        d = self.make()
        (d / "out/package/caption_instagram.txt").unlink()
        self.assertEqual(publish.run_slot(at(12, 31)), "failed")
        self.yt.assert_not_called()
        self.assertEqual(self.rec()["status"], "failed")

    def test_retry_checks_container_and_adopts_if_published(self):
        d = self.make()
        def fail_after_container(ep, video, on_container=None):
            on_container("C1")
            raise SystemExit("ambiguous")
        self.ig.side_effect = fail_after_container
        self.assertEqual(publish.run_slot(at(12, 31)), "ig_retry_pending")
        self.assertEqual(self.rec()["ig_container"], "C1")
        with mock.patch.object(publish.instagram_publish, "container_published", return_value=True):
            self.assertEqual(publish.run_slot(at(19, 31)), "posted")
        self.assertEqual(self.ig.call_count, 1)
        self.assertEqual(self.rec()["status"], "posted")

    def test_retry_publishes_again_if_container_not_published(self):
        self.make()
        def fail_after_container(ep, video, on_container=None):
            on_container("C1")
            raise SystemExit("x")
        self.ig.side_effect = fail_after_container
        publish.run_slot(at(12, 31))
        self.ig.side_effect = None
        with mock.patch.object(publish.instagram_publish, "container_published", return_value=False):
            self.assertEqual(publish.run_slot(at(19, 31)), "posted")
        self.assertEqual(self.ig.call_count, 2)

    def test_retry_and_due_record_handled_in_one_run(self):
        self.make("a")
        self.ig.side_effect = SystemExit("x")
        publish.run_slot(at(12, 31))
        self.ig.side_effect = None
        self.make("b", yt_id="YT2", slot="2026-11-18T19:30:00+05:30")
        self.assertEqual(publish.run_slot(at(19, 31)), "posted")
        self.assertEqual(self.rec("a")["status"], "posted")
        self.assertEqual(self.rec("b")["status"], "posted")
        self.assertEqual([c.args for c in self.yt.call_args_list], [("YT1", "public"), ("YT2", "public")])

    def test_youtube_404_fails_immediately(self):
        self.make()
        self.yt.side_effect = publish.youtube_publish.YTError(404, "gone")
        self.assertEqual(publish.run_slot(at(12, 31)), "failed")
        self.assertEqual(self.rec()["status"], "failed")
        self.assertTrue(any("private preview missing" in c.args[0] and c.args[1] == "failure"
                            for c in self.inbox.call_args_list))
        self.assertEqual(publish.run_slot(at(12, 35)), "nothing_due")

    def test_run_lock_blocks_concurrent_run(self):
        import fcntl
        self.make()
        publish.LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
        with open(publish.LOCKFILE, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.assertEqual(publish.run_slot(at(12, 31)), "locked")
        self.yt.assert_not_called()
        self.assertEqual(self.rec()["status"], "approved")
        self.assertEqual(publish.run_slot(at(12, 31)), "posted")

    def test_youtube_log_merges_existing_entry(self):
        d = self.make()
        m = json.loads((d / "episode.json").read_text())
        m["published"]["youtube"] = {"id": "YT1", "captions": ["hi"]}
        (d / "episode.json").write_text(json.dumps(m))
        publish.run_slot(at(12, 31))
        yt = json.loads((d / "episode.json").read_text())["published"]["youtube"]
        self.assertEqual((yt["captions"], yt["privacy"]), (["hi"], "public"))

    def test_manual_handoff_sent_before_record_posted(self):
        self.make(mode="manual")
        order = []
        self.inbox.side_effect = lambda *a, **k: order.append(("inbox", self.rec()["status"]))
        publish.run_slot(at(12, 31))
        self.assertEqual(order, [("inbox", "approved")])


class PublishReelTest(unittest.TestCase):
    def test_permalink_failure_after_post_keeps_media_id(self):
        import instagram_publish as ip
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "out/final").mkdir(parents=True); (d / "out/package").mkdir(parents=True)
            (d / "out/final/v.mp4").write_bytes(b"x")
            (d / "out/package/caption_instagram.txt").write_text("c")
            (d / "episode.json").write_text(json.dumps({"id": "e"}))
            def fake(method, url, params=None, headers=None, body=None):
                if url.endswith("/media_publish"):
                    return {"id": "M"}
                if method == "POST" and url.endswith("/media"):
                    return {"id": "C", "uri": "https://up"}
                if url.endswith("/M"):
                    raise SystemExit("permalink boom")
                return {"status_code": "FINISHED"}
            seen = []
            with mock.patch.object(ip, "call", side_effect=fake), \
                 mock.patch.object(ip, "load", return_value={"access_token": "t", "ig_user_id": "U"}):
                res = ip.publish_reel(d, "v.mp4", on_container=seen.append)
            self.assertEqual(res, {"media_id": "M", "permalink": None})
            self.assertEqual(seen, ["C"])
            self.assertEqual(json.loads((d / "episode.json").read_text())["published"]["instagram"]["media_id"], "M")


if __name__ == "__main__":
    unittest.main()
