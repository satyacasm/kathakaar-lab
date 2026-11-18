import os, sqlite3, sys, tempfile, unittest
from datetime import date
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import analytics
import review

TODAY = date(2026, 11, 18)


def mem_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(analytics.SCHEMA + analytics.IG_SCHEMA + analytics.FOLLOWERS_SCHEMA)
    return con


class TestWow(unittest.TestCase):
    def test_wow_delta(self):
        rows = [("2026-11-11", "youtube", 1000), ("2026-11-18", "youtube", 1100)]
        w = review.week_over_week(rows, TODAY)["youtube"]
        self.assertEqual((w["now"], w["week_ago"], w["delta"], w["pct"]), (1100, 1000, 100, 10.0))

    def test_wow_missing_week_ago(self):
        w = review.week_over_week([("2026-11-18", "youtube", 1100)], TODAY)["youtube"]
        self.assertEqual(w["now"], 1100)
        self.assertIsNone(w["delta"])
        self.assertIsNone(w["pct"])

    def test_wow_zero_base_has_no_pct(self):
        rows = [("2026-11-11", "instagram", 0), ("2026-11-18", "instagram", 5)]
        w = review.week_over_week(rows, TODAY)["instagram"]
        self.assertEqual(w["delta"], 5)
        self.assertIsNone(w["pct"])


class TestFollowersPull(unittest.TestCase):
    def test_followers_pull_idempotent(self):
        con = mem_db()
        with mock.patch.object(analytics, "request", return_value={"items": [{"statistics": {"subscriberCount": "321"}}]}) as yr, \
             mock.patch.object(analytics, "ig_get", return_value={"followers_count": 45}) as ig, \
             mock.patch.object(analytics, "IG_SECRETS", Path(__file__)):
            first = analytics.followers_pull(con)
            n = con.execute("SELECT COUNT(*) FROM followers").fetchone()[0]
            second = analytics.followers_pull(con)
        self.assertEqual(first, {"youtube": 321, "instagram": 45})
        self.assertEqual(second, first)
        self.assertEqual(n, 2)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM followers").fetchone()[0], 2)
        self.assertEqual(yr.call_count, 1)
        self.assertEqual(ig.call_count, 1)

    def test_instagram_skipped_without_secrets(self):
        con = mem_db()
        with mock.patch.object(analytics, "request", return_value={"items": [{"statistics": {"subscriberCount": "7"}}]}), \
             mock.patch.object(analytics, "ig_get") as ig, \
             mock.patch.object(analytics, "IG_SECRETS", Path("/nonexistent/instagram.json")):
            out = analytics.followers_pull(con)
        self.assertEqual(out, {"youtube": 7})
        ig.assert_not_called()


class TestViews(unittest.TestCase):
    def test_youtube_views_wow_from_daily(self):
        con = mem_db()
        for d, v in [("2026-11-12", 10), ("2026-11-18", 20), ("2026-11-05", 5), ("2026-11-11", 5)]:
            con.execute("INSERT INTO daily(video_id,day,views) VALUES('a',?,?)", (d, v))
        y = review.views_wow(con, TODAY)["youtube"]
        self.assertEqual((y["now"], y["prev"], y["delta"], y["pct"]), (30, 10, 20, 200.0))

    def test_instagram_views_from_snapshot_difference(self):
        con = mem_db()
        con.execute("INSERT INTO ig_media(media_id,timestamp,media_product_type) VALUES('m1','2026-11-01T10:00:00+0000','REELS')")
        con.execute("INSERT INTO ig_media(media_id,timestamp,media_product_type) VALUES('m2','2026-11-14T10:00:00+0000','REELS')")
        for mid, day, views in [("m1", "2026-11-10", 100), ("m1", "2026-11-18", 160), ("m2", "2026-11-18", 40)]:
            con.execute("INSERT INTO ig_snapshots(media_id,taken_at,day_ist,bucket,views,has_data) VALUES(?,?,?,?,?,1)",
                        (mid, day, day, "daily", views))
        i = review.views_wow(con, TODAY)["instagram"]
        self.assertEqual(i["now"], 100)          # (160-100) + (40-0)
        self.assertIsNone(i["prev"])             # no earlier boundary to compare against
        self.assertIsNone(i["delta"])
        self.assertTrue(i["approx"])

    def test_no_data_is_none_not_zero(self):
        v = review.views_wow(mem_db(), TODAY)
        self.assertIsNone(v["youtube"]["now"])
        self.assertIsNone(v["instagram"]["now"])


class TestCellTable(unittest.TestCase):
    def test_empty_without_loop_videos(self):
        self.assertEqual(review.cell_table(mem_db(), records=[], rows=[], scores={}), [])

    def test_groups_by_cell(self):
        recs = [
            {"id": "e1", "status": "posted", "slot": "2026-11-17T12:30:00+05:30",
             "cell": {"format": "narrated", "audio": "popular", "slot_pref": "any"}},
            {"id": "e2", "status": "posted", "slot": "2026-11-17T12:30:00+05:30",
             "cell": {"format": "narrated", "audio": "popular", "slot_pref": "any"}},
            {"id": "e3", "status": "planned", "slot": None,
             "cell": {"format": "narrated", "audio": "popular", "slot_pref": "any"}},
        ]
        rows = [{"episode_slug": "e1", "video_id": "v1", "an_views": "1000", "subs_gained": "3"},
                {"episode_slug": "e2", "video_id": "v2", "an_views": "1000", "subs_gained": "1"}]
        t = review.cell_table(mem_db(), records=recs, rows=rows, scores={"v1": 2.0, "v2": 1.0})
        self.assertEqual(len(t), 1)
        c = t[0]
        self.assertEqual((c["format"], c["audio"], c["slot"], c["n"], c["median_score"]), ("narrated", "popular", "12:30", 2, 1.5))
        self.assertEqual(c["followers_per_1k"], 2.0)


if __name__ == "__main__":
    unittest.main()
