import os, sys, tempfile, unittest
from collections import Counter
from datetime import date
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import plan

START = date(2026, 11, 19)
CELLS = [(f, a) for f, auds in plan.AUDIO.items() for a in auds]


def cost(r):
    return plan.row_cost(r)


class TestFortnight(unittest.TestCase):
    def test_fortnight_has_28_rows(self):
        rows = plan.fortnight(START, [], 300)
        self.assertEqual(len(rows), 28)
        self.assertEqual(rows[0]["day"], "2026-11-19")
        self.assertEqual(rows[-1]["day"], "2026-12-02")
        self.assertEqual([r["slot"] for r in rows[:4]], ["12:30", "19:30", "12:30", "19:30"])
        self.assertTrue(all(not r["locked"] and not r["id"] for r in rows))

    def test_every_cell_reaches_three(self):
        rows = plan.fortnight(START, [], 300)
        n = Counter((r["format"], r["audio"]) for r in rows)
        self.assertEqual(len(CELLS), 8)
        for c in CELLS:
            self.assertGreaterEqual(n[c], 3, c)
        s = Counter(r["slot"] for r in rows)
        self.assertGreaterEqual(s["12:30"], 12)
        self.assertGreaterEqual(s["19:30"], 12)

    def test_existing_videos_count_towards_three(self):
        existing = [{"cell": {"format": "music", "audio": "popular"}, "status": "posted"}] * 3
        rows = plan.fortnight(START, existing, 300)
        n = Counter((r["format"], r["audio"]) for r in rows)
        self.assertEqual(len(rows), 28)
        for c in CELLS:
            self.assertGreaterEqual(n[c] + (3 if c == ("music", "popular") else 0), 3)
        self.assertLessEqual(n[("music", "popular")], n[("music", "library")])

    def test_budget_respected(self):
        rows = plan.fortnight(START, [], 150)
        self.assertLessEqual(sum(cost(r) for r in rows), 150)
        n = Counter((r["format"], r["audio"]) for r in rows)
        self.assertTrue(all(n[c] >= 3 for c in CELLS), n)      # 150 is exactly enough for every cell
        rows = plan.fortnight(START, [], 40)
        self.assertEqual(len(rows), 28)
        self.assertLessEqual(sum(cost(r) for r in rows), 40)
        self.assertGreater(sum(r["format"] in ("narrated", "claim") for r in rows), 20)
        rows = plan.fortnight(START, [], 0)
        self.assertTrue(all(r["format"] in ("narrated", "claim") for r in rows))

    def test_no_back_to_back_format(self):
        for credits in (300, 150, 40, 0):
            rows = plan.fortnight(START, [], credits)
            for a, b in zip(rows, rows[1:]):
                self.assertNotEqual(a["format"], b["format"], credits)

    def test_formats_alternate_slots(self):
        for credits in (300, 150):
            rows = plan.fortnight(START, [], credits)
            for f in plan.FORMATS:
                slots = [r["slot"] for r in rows if r["format"] == f]
                if len(slots) >= 2:
                    self.assertEqual(set(slots), {"12:30", "19:30"}, (credits, f))
                flips = sum(a != b for a, b in zip(slots, slots[1:]))
                self.assertGreaterEqual(flips, (len(slots) - 1) // 2, (credits, f))

    def test_topic_sources_valid(self):
        rows = plan.fortnight(START, [], 300)
        for r in rows:
            self.assertIn(r["topic_source"], plan.TOPICS)
            if r["topic_source"] == "song_story":
                self.assertEqual(r["format"], "music")
            if r["topic_source"] == "dialogue_catalogue":
                self.assertEqual(r["format"], "dialogue")

    def test_only_loop_statuses_count(self):
        existing = [{"cell": {"format": "music", "audio": "popular"}, "status": "rejected"}] * 5
        self.assertEqual(plan.fortnight(START, existing, 300), plan.fortnight(START, [], 300))


class TestFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "experiment_plan.md"

    def test_roundtrip(self):
        rows = plan.fortnight(START, [], 300)
        rows[2]["id"] = "ep1"
        plan.write(rows, self.path)
        self.assertEqual(plan.read(self.path), rows)

    def test_read_missing_is_empty(self):
        self.assertEqual(plan.read(self.path), [])

    def test_locked_rows_survive_rewrite(self):
        rows = plan.fortnight(START, [], 300)
        rows[3]["locked"] = True
        rows[3]["format"], rows[3]["audio"], rows[3]["topic_source"] = "claim", "bed", "festival"
        plan.write(rows, self.path)
        fresh = plan.fortnight(START, [], 300)
        plan.write(fresh, self.path)
        got = plan.read(self.path)
        self.assertEqual(len(got), 28)
        self.assertEqual(got[3], rows[3])
        self.assertTrue(got[3]["locked"])

    def test_take_locked_row_sticks(self):
        rows = plan.fortnight(START, [], 300)
        rows[0]["locked"] = True
        plan.write(rows, self.path)
        got = plan.read(self.path)
        nxt = plan.next_row(got, [])
        self.assertEqual((nxt["day"], nxt["slot"]), (rows[0]["day"], rows[0]["slot"]))
        nxt["id"] = "ep_taken"
        plan.write(got, self.path)
        got = plan.read(self.path)
        self.assertEqual(got[0]["id"], "ep_taken")
        self.assertTrue(got[0]["locked"])
        self.assertEqual(plan.next_row(got, [])["slot"], rows[1]["slot"])
        self.assertEqual(plan.next_row(got, [])["id"], "")

    def test_read_accepts_y_and_locked(self):
        plan.write(plan.fortnight(START, [], 300)[:2], self.path)
        txt = self.path.read_text().replace("| no |", "| y |", 1).replace("| no |", "| locked |", 1)
        self.path.write_text(txt)
        self.assertTrue(all(r["locked"] for r in plan.read(self.path)))

    def test_next_row(self):
        rows = plan.fortnight(START, [], 300)
        rows[0]["id"] = "a"
        self.assertEqual(plan.next_row(rows, []), rows[1])
        for r in rows:
            r["id"] = "x"
        self.assertIsNone(plan.next_row(rows, []))


class TestExploit(unittest.TestCase):
    def test_exploit_week_split(self):
        scores = {("music", "popular"): 3.0, ("music", "library"): 2.0, ("shloka", "library"): 1.0,
                  ("narrated", "bed"): 0.5, ("claim", "bed"): 0.4}
        rows = plan.exploit_week(START, scores, 300)
        self.assertEqual(len(rows), 14)
        top = {("music", "popular"), ("music", "library"), ("shloka", "library")}
        n_top = sum((r["format"], r["audio"]) in top for r in rows)
        self.assertEqual(n_top, 10)
        untested = {c for c in CELLS if c not in scores}
        self.assertEqual(sum((r["format"], r["audio"]) in untested for r in rows), 4)
        c = Counter((r["format"], r["audio"]) for r in rows)
        self.assertGreater(c[("music", "popular")], c[("shloka", "library")])

    def _check_week(self, rows):
        self.assertEqual(len(rows), 14)
        for a, b in zip(rows, rows[1:]):
            self.assertNotEqual(a["format"], b["format"])

    def test_nonpositive_scores_still_10_4(self):
        for scores in ({("music", "popular"): -1, ("music", "library"): -2, ("shloka", "library"): -3},
                       {("music", "popular"): 0, ("narrated", "bed"): 0, ("shloka", "library"): 0}):
            rows = plan.exploit_week(START, scores, 300)
            n_top = sum((r["format"], r["audio"]) in scores for r in rows)
            self.assertEqual(n_top, 10, scores)
            self._check_week(rows)

    def test_all_music_top_cells_capped(self):
        scores = {("music", "popular"): 3.0, ("music", "library"): 2.0, ("music", "original"): 1.0,
                  ("shloka", "library"): 0.5, ("narrated", "bed"): 0.2}
        rows = plan.exploit_week(START, scores, 300)
        self._check_week(rows)
        self.assertLessEqual(sum(r["format"] == "music" for r in rows), 7)

    def test_explore_uses_counts(self):
        scores = {("music", "popular"): 3.0, ("music", "library"): 2.0, ("shloka", "library"): 1.0}
        counts = {c: 5 for c in CELLS}
        counts[("claim", "bed")] = 1
        counts[("dialogue", "popular")] = 0
        rows = plan.exploit_week(START, scores, 300, counts)
        got = Counter((r["format"], r["audio"]) for r in rows)
        self.assertGreaterEqual(got[("claim", "bed")] + got[("dialogue", "popular")], 4)
        scores = {("shloka", "library"): 3.0, ("dialogue", "popular"): 2.0, ("narrated", "bed"): 1.0}
        counts = {c: 5 for c in CELLS}
        counts[("music", "original")] = 3
        rows = plan.exploit_week(START, scores, 300, counts)
        self.assertEqual(sum((r["format"], r["audio"]) == ("music", "original") for r in rows), 4)

    def test_exploit_week_budget(self):
        scores = {("music", "popular"): 3.0, ("music", "library"): 2.0, ("shloka", "library"): 1.0}
        rows = plan.exploit_week(START, scores, 20)
        self.assertEqual(len(rows), 14)
        self.assertLessEqual(sum(cost(r) for r in rows), 20)
        for a, b in zip(rows, rows[1:]):
            self.assertNotEqual(a["format"], b["format"])


if __name__ == "__main__":
    unittest.main()
