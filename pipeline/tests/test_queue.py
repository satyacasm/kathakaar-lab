import contextlib, fcntl, io, multiprocessing, os, sys, tempfile, unittest
from unittest import mock
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import vqueue
from vqueue import TZ, QueueError, add, approve, due, one_line, reject, transition, load, save


def _add_worker(path, rid):
    vqueue.QUEUE = Path(path)
    add(rid, {"format": "f", "audio": "a", "slot_pref": "any"}, "api")


class QueueTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "queue.json"
        self._orig = vqueue.QUEUE
        vqueue.QUEUE = self.path
        self.addCleanup(setattr, vqueue, "QUEUE", self._orig)

    def make(self, rid, status="preview_ready", **fields):
        add(rid, {"format": "f", "audio": "a", "slot_pref": "any"}, "api")
        chain = {"planned": [], "producing": ["producing"], "preview_ready": ["producing", "preview_ready"]}[status]
        for s in chain:
            transition(rid, s, **fields)


class TestQueue(QueueTestBase):
    def test_transition_rejects_skip(self):
        add("a", {"format": "f", "audio": "a", "slot_pref": "any"}, "api")
        with self.assertRaises(QueueError):
            transition("a", "approved")

    def test_transition_records_history(self):
        add("a", {"format": "f", "audio": "a", "slot_pref": "any"}, "api")
        r = transition("a", "producing")
        self.assertEqual([h[1] for h in r["history"]], ["planned", "producing"])

    def test_approve_assigns_slots_in_order(self):
        for rid in "abc":
            self.make(rid, yt_id="yt_" + rid)
        now = datetime(2026, 11, 19, 9, 0, tzinfo=TZ)
        out = approve(["a", "b", "c"], now, lambda vid: True)
        self.assertEqual([r["slot"][:16] for r in out],
                         ["2026-11-19T12:30", "2026-11-19T19:30", "2026-11-20T12:30"])
        self.assertTrue(all(r["status"] == "approved" for r in out))

    def test_approve_after_both_slots_goes_to_tomorrow(self):
        self.make("a", yt_id="yt_a")
        now = datetime(2026, 11, 19, 20, 15, tzinfo=TZ)
        out = approve(["a"], now, lambda vid: True)
        self.assertEqual(out[0]["slot"][:16], "2026-11-20T12:30")

    def test_approve_skips_slots_held_by_approved(self):
        self.make("a", yt_id="yt_a")
        self.make("b", yt_id="yt_b")
        now = datetime(2026, 11, 19, 9, 0, tzinfo=TZ)
        approve(["a"], now, lambda vid: True)
        out = approve(["b"], now, lambda vid: True)
        self.assertEqual(out[0]["slot"][:16], "2026-11-19T19:30")

    def test_approve_refuses_missing_preview(self):
        self.make("a", yt_id="yt_a")
        with self.assertRaisesRegex(QueueError, "private preview .* not found"):
            approve(["a"], datetime(2026, 11, 19, 9, 0, tzinfo=TZ), lambda vid: False)
        self.assertEqual(load()[0]["status"], "preview_ready")

    def test_approve_only_preview_ready(self):
        self.make("a", status="producing")
        with self.assertRaises(QueueError):
            approve(["a"], datetime(2026, 11, 19, 9, 0, tzinfo=TZ), lambda vid: True)

    def test_approve_is_all_or_nothing(self):
        self.make("a", yt_id="yt_a")
        self.make("b", status="producing")
        with self.assertRaises(QueueError):
            approve(["a", "b"], datetime(2026, 11, 19, 9, 0, tzinfo=TZ), lambda vid: True)
        self.assertEqual({r["id"]: r["status"] for r in load()}, {"a": "preview_ready", "b": "producing"})

    def test_reject_stores_one_line_reason(self):
        self.make("a", yt_id="yt_a")
        r = reject("a", "slow hook\n- [x] fake | item\n# heading")
        self.assertEqual(r["status"], "rejected")
        self.assertNotIn("\n", r["reason"])
        self.assertTrue(r["reason"].startswith("slow hook"))
        self.assertNotIn(" | ", r["reason"])

    def _rejected_on(self, rid, iso):
        self.make(rid)
        reject(rid, "weak hook")
        recs = load()
        for r in recs:
            if r["id"] == rid:
                r["history"][-1][0] = iso
        save(recs)

    def test_rejections_since(self):
        self._rejected_on("old", "2026-11-10T10:00:00+05:30")
        self._rejected_on("new", "2026-11-17T10:00:00+05:30")
        self.make("kept")  # not rejected: never returned
        got = vqueue.rejections_since(date(2026, 11, 12))
        self.assertEqual([r["id"] for r in got], ["new"])
        self.assertEqual(got[0]["reason"], "weak hook")
        self.assertEqual(got[0]["rejected_on"], "2026-11-17")
        self.assertEqual([r["id"] for r in vqueue.rejections_since(date(2026, 11, 10))], ["old", "new"])

    def test_rejections_cli(self):
        import io, contextlib
        self._rejected_on("new", "2026-11-17T10:00:00+05:30")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            vqueue.main(["rejections", "--since", "2026-11-12"])
        self.assertEqual(buf.getvalue().strip(), "2026-11-17 | new | f / a | weak hook")

    def test_rejections_cli_dash_for_missing_cell_fields(self):
        import io, contextlib
        add("x", {}, "api")
        for st in ("producing", "preview_ready"):
            transition("x", st)
        reject("x", "r")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            vqueue.main(["rejections", "--since", "2000-01-01"])
        self.assertIn("| - / - | r", buf.getvalue())

    def test_one_line(self):
        self.assertEqual(one_line("## - [x]  hi\n there"), "x] hi there")
        self.assertEqual(len(one_line("x" * 500)), 300)

    def test_due_respects_grace(self):
        self.make("a", yt_id="yt_a")
        approve(["a"], datetime(2026, 11, 19, 9, 0, tzinfo=TZ), lambda vid: True)
        self.assertEqual(due(datetime(2026, 11, 19, 13, 0, tzinfo=TZ))["id"], "a")
        self.assertIsNone(due(datetime(2026, 11, 19, 14, 31, tzinfo=TZ)))
        self.assertIsNone(due(datetime(2026, 11, 19, 12, 0, tzinfo=TZ)))

    def test_atomic_save_roundtrip(self):
        save([{"id": "x"}])
        self.assertEqual(load(), [{"id": "x"}])
        self.assertEqual(load(Path(self.tmp.name) / "missing.json"), [])

    def test_concurrent_save_keeps_both_records(self):
        ctx = multiprocessing.get_context("spawn")
        procs = [ctx.Process(target=_add_worker, args=(str(self.path), rid)) for rid in ("p1", "p2")]
        for p in procs:
            p.start()
        for p in procs:
            p.join(60)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(sorted(r["id"] for r in load()), ["p1", "p2"])

    def test_update_sets_fields_without_status_change(self):
        add("u", {"format": "f", "audio": "a", "slot_pref": "any"}, "api")
        vqueue.update("u", yt_public=True)
        self.assertTrue(load()[0]["yt_public"])
        self.assertEqual(load()[0]["status"], "planned")
        with self.assertRaises(QueueError):
            vqueue.update("u", status="posted")


class TestRejectDeletesPreview(QueueTestBase):
    def setUp(self):
        super().setUp()
        import inbox, youtube_publish
        self.yt, self.inbox = youtube_publish, inbox
        p = mock.patch.object(inbox, "add")
        self.inbox_add = p.start()
        self.addCleanup(p.stop)

    def _cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            vqueue.main(list(argv))

    def test_library_reject_is_pure(self):
        self.make("a", yt_id="yt_a")
        with mock.patch.object(self.yt, "delete_video") as d:
            reject("a", "meh")
        d.assert_not_called()

    def test_cli_reject_deletes_after_lock_released(self):
        self.make("a", yt_id="yt_a")
        seen = {}

        def fake_delete(vid):
            seen["vid"] = vid
            with open(self.path.with_name(self.path.name + ".lock"), "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if the queue lock were still held
                seen["status"] = load()[0]["status"]

        with mock.patch.object(self.yt, "delete_video", side_effect=fake_delete):
            self._cli("reject", "a", "--reason", "weak hook")
        self.assertEqual(seen, {"vid": "yt_a", "status": "rejected"})
        rec = load()[0]
        self.assertEqual(rec["status"], "rejected")
        self.assertIs(rec["yt_deleted"], True)
        self.inbox_add.assert_not_called()

    def test_cli_reject_delete_failure_goes_to_inbox(self):
        self.make("a", yt_id="yt_a")
        with mock.patch.object(self.yt, "delete_video", side_effect=self.yt.YTError(403, "quota")):
            self._cli("reject", "a", "--reason", "weak hook")
        rec = load()[0]
        self.assertEqual(rec["status"], "rejected")
        self.assertNotIn("yt_deleted", rec)
        text, kind = self.inbox_add.call_args.args
        self.assertEqual(kind, "failure")
        self.assertIn("could not delete private preview yt_a", text)

    def test_cli_reject_without_preview_skips_delete(self):
        self.make("a")
        with mock.patch.object(self.yt, "delete_video") as d:
            self._cli("reject", "a", "--reason", "x")
        d.assert_not_called()


class TestResealRequeue(QueueTestBase):
    def failed(self, rid, **fields):
        self.make(rid, **fields)
        recs = load()
        for r in recs:
            if r["id"] == rid:
                r.update(status="failed", reason="package changed", slot="2026-11-19T12:30:00+05:30",
                         yt_retry=1, ig_retry=1, ig_container="c1", final_sha256={"x": "old"})
        save(recs)

    def test_reseal_back_to_preview_ready_with_new_digests(self):
        self.failed("a", yt_id="yt_a")
        r = vqueue.reseal("a", lambda vid: vid == "yt_a", lambda rid: {"final_sha256": {"x": "new"},
                                                                        "package_sha256": {}, "meta_sha256": "m"})
        self.assertEqual(r["status"], "preview_ready")
        rec = load()[0]
        for k in ("slot", "yt_retry", "ig_retry", "ig_container", "reason"):
            self.assertIsNone(rec[k], k)
        self.assertEqual(rec["final_sha256"], {"x": "new"})
        self.assertEqual(rec["meta_sha256"], "m")
        self.assertEqual(rec["history"][-1][1], "preview_ready")
        # still needs a fresh approval
        out = approve(["a"], datetime(2026, 11, 19, 9, 0, tzinfo=TZ), lambda vid: True)
        self.assertEqual(out[0]["status"], "approved")

    def test_reseal_refuses_missing_preview(self):
        self.failed("a", yt_id="yt_a")
        with self.assertRaisesRegex(QueueError, "not found"):
            vqueue.reseal("a", lambda vid: False, lambda rid: {})
        self.assertEqual(load()[0]["status"], "failed")

    def test_reseal_refuses_non_failed_and_no_preview(self):
        self.make("a", yt_id="yt_a")
        with self.assertRaisesRegex(QueueError, "only failed"):
            vqueue.reseal("a", lambda vid: True, lambda rid: {})
        self.failed("b")
        with self.assertRaisesRegex(QueueError, "requeue"):
            vqueue.reseal("b", lambda vid: True, lambda rid: {})

    def test_requeue_only_without_preview(self):
        self.failed("a", yt_id="yt_a")
        with self.assertRaisesRegex(QueueError, "use reseal"):
            vqueue.requeue("a")
        self.assertEqual(load()[0]["status"], "failed")
        self.failed("b")
        self.assertEqual(vqueue.requeue("b")["status"], "planned")

    def test_cli_requeue_refusal_exits(self):
        self.failed("a", yt_id="yt_a")
        with self.assertRaises(SystemExit) as cm:
            vqueue.main(["requeue", "a"])
        self.assertIn("use reseal", str(cm.exception.code))

    def test_cli_reseal_uses_integrity_of_episode(self):
        import integrity, youtube_publish
        self.failed("a", yt_id="yt_a")
        eps = Path(self.tmp.name) / "episodes"
        with mock.patch.object(vqueue, "EPISODES", eps), \
             mock.patch.object(youtube_publish, "video_exists", return_value=True), \
             mock.patch.object(integrity, "record", return_value={"meta_sha256": "z"}) as rec, \
             contextlib.redirect_stdout(io.StringIO()):
            vqueue.main(["reseal", "a"])
        rec.assert_called_once_with(eps / "a")
        self.assertEqual(load()[0]["status"], "preview_ready")


class TestApproveNetworkErrors(QueueTestBase):
    def test_approve_network_error_clean_exit(self):
        import socket, urllib.error, youtube_publish
        self.make("a", yt_id="yt_a")
        for err in (urllib.error.URLError("dns"), TimeoutError("slow"), socket.timeout("t"), ConnectionResetError()):
            with mock.patch.object(youtube_publish, "video_exists", side_effect=err):
                with self.assertRaises(SystemExit) as cm:
                    vqueue.main(["approve", "a"])
            self.assertIn("could not reach YouTube", str(cm.exception.code))
            self.assertEqual(load()[0]["status"], "preview_ready")


if __name__ == "__main__":
    unittest.main()
