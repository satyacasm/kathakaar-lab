import multiprocessing, os, sys, tempfile, unittest
from datetime import datetime, timedelta
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


if __name__ == "__main__":
    unittest.main()
