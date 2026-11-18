import contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import vqueue
from reel import budget


def ledger(*entries):
    return {"entries": [{"date": d, "episode": e, "credits": c} for d, e, c in entries]}


class LoopCapTests(unittest.TestCase):
    def test_cap_november_150(self):
        self.assertEqual(budget.loop_cap("2026-11"), 150)

    def test_cap_december_300(self):
        self.assertEqual(budget.loop_cap("2026-12"), 300)

    def test_loop_spent_counts_only_loop_ids_in_month(self):
        lg = ledger(("2026-11-02", "a", 10), ("2026-11-03", "b", 99), ("2026-10-30", "a", 7))
        self.assertEqual(budget.loop_spent("2026-11", {"a"}, lg), 10)

    def test_can_spend_blocks_on_loop_cap(self):
        lg = ledger(("2026-11-02", "a", 145))
        ok, why = budget.can_spend(6, "2026-11", {"a"}, lg)
        self.assertFalse(ok)
        self.assertIn("loop cap", why)

    def test_can_spend_blocks_on_global_cap(self):
        lg = ledger(("2026-11-02", "manual", 598))
        ok, why = budget.can_spend(4, "2026-11", {"a"}, lg)
        self.assertFalse(ok)
        self.assertIn("monthly cap", why)

    def test_can_spend_ok(self):
        ok, _ = budget.can_spend(5, "2026-11", {"a"}, ledger(("2026-11-02", "a", 100)))
        self.assertTrue(ok)


class QueueIdsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "queue.json"
        p = mock.patch.object(vqueue, "QUEUE", self.path)
        p.start()
        self.addCleanup(p.stop)

    def test_missing_queue_file_is_empty(self):
        self.assertEqual(budget.queue_ids(), set())

    def test_ids_from_queue_file(self):
        self.path.write_text(json.dumps([{"id": "a"}, {"id": "b"}]))
        self.assertEqual(budget.queue_ids(), {"a", "b"})

    def _plan(self, ledger_entries):
        ep = Path(self.tmp.name) / "episodes" / "a"
        ep.mkdir(parents=True)
        (ep.parent / "credits.json").write_text(json.dumps({"entries": ledger_entries}))
        shot = {"n": 1, "hero": {"model": "m", "resolution": "720p", "duration": 5, "prompt": "p"}}
        cfg = {"credits_per_month": 600, "credits_per_reel": 10}
        sm = dict(cfg=cfg, pending=[shot], est={1: 6}, pending_total=6, episode_spent=0, month_spent=0,
                  month="2026-11", reel_total=6, month_total=6, over_reel=False, over_month=False)
        out = io.StringIO()
        with mock.patch.object(budget.S, "validate", return_value=mock.Mock(errors=[])), \
             mock.patch.object(budget.S, "load_shots", return_value={"shots": [shot]}), \
             mock.patch.object(budget, "summary", return_value=sm), \
             contextlib.redirect_stdout(out):
            rc = budget.hero_plan(ep)
        return rc, out.getvalue()

    def test_hero_plan_refuses_over_loop_cap_once(self):
        self.path.write_text(json.dumps([{"id": "a"}]))
        rc, out = self._plan([{"date": "2026-11-02", "episode": "a", "credits": 145}])
        self.assertEqual(rc, 1)
        self.assertEqual([l for l in out.splitlines() if l.startswith("REFUSED")].__len__(), 1)
        self.assertIn("loop cap", out)

    def test_hero_plan_ok_when_not_in_queue(self):
        rc, out = self._plan([{"date": "2026-11-02", "episode": "a", "credits": 145}])
        self.assertEqual(rc, 0)
        self.assertNotIn("REFUSED", out)


if __name__ == "__main__":
    unittest.main()
