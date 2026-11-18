import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

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


if __name__ == "__main__":
    unittest.main()
