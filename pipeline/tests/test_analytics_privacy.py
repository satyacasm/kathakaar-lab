"""Private loop previews never pollute analytics: no snapshots while non-public, buckets restart when public,
and `yt map` never suggests (or --set maps) a video that is not public yet. Temp DB, mocked API."""
import argparse, contextlib, io, json, os, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import analytics


def video(vid, privacy, published, title="Shiva drinks the poison"):
    return {"id": vid, "snippet": {"title": title, "publishedAt": published},
            "contentDetails": {"duration": "PT40S"}, "statistics": {"viewCount": "0"},
            "status": {"privacyStatus": privacy}}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.eps = root / "episodes"
        self.eps.mkdir()
        store = root / "analytics"
        for name, val in (("STORE", store), ("DB_PATH", store / "a.sqlite"), ("MAP_PATH", store / "map.json"),
                          ("EPISODES", self.eps)):
            p = mock.patch.object(analytics, name, val)
            p.start()
            self.addCleanup(p.stop)
        for name, kw in (("check_short", {"return_value": True}),):
            p = mock.patch.object(analytics, name, **kw)
            p.start()
            self.addCleanup(p.stop)
        self.now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
        p = mock.patch.object(analytics, "now_utc", side_effect=lambda: self.now)
        p.start()
        self.addCleanup(p.stop)
        self.con = analytics.db()
        self.addCleanup(self.con.close)

    def episode(self, slug, title, preview=None, public=None):
        d = self.eps / slug
        d.mkdir()
        pub = {}
        if preview:
            pub["youtube_preview"] = {"id": preview}
        if public:
            pub["youtube"] = {"id": public}
        (d / "episode.json").write_text(json.dumps({"slug": slug, "title_en": title, "published": pub}))

    def pull(self, vids):
        """cmd_pull with discovery mocked; returns the (video_id, bucket) pairs snapshotted and comment pulls."""
        snaps, comments = [], []
        with mock.patch.object(analytics, "discover_ids", return_value=[v["id"] for v in vids]), \
             mock.patch.object(analytics, "fetch_videos", return_value=vids), \
             mock.patch.object(analytics, "take_snapshot",
                               side_effect=lambda con, row, b, age: snaps.append((row["video_id"], b)) or
                               self._insert_snap(row["video_id"], b, con)), \
             mock.patch.object(analytics, "pull_comments", side_effect=lambda con, row: comments.append(row["video_id"]) or 0), \
             mock.patch.object(analytics, "export_all", return_value=0), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                analytics.cmd_pull(argparse.Namespace(video=None, force=False, no_comments=False))
        self.assertEqual(cm.exception.code, 0)
        return snaps, comments

    def _insert_snap(self, vid, bucket, con=None):
        con = con or self.con
        cur = con.execute("INSERT INTO snapshots(video_id,taken_at,day_ist,bucket) VALUES(?,?,?,?)",
                               (vid, analytics.iso(self.now), self.now.date().isoformat(), bucket))
        con.execute("INSERT INTO retention VALUES(?,?,?,?)", (cur.lastrowid, 0.5, 0.4, 0.1))
        con.execute("INSERT INTO traffic VALUES(?,?,?)", (cur.lastrowid, "SHORTS", 3))
        if con is self.con:
            con.commit()
        return cur.lastrowid


class TestPullSkipsPrivate(Base):
    def test_private_preview_gets_no_snapshot_or_comments(self):
        snaps, comments = self.pull([video("prv", "private", "2026-11-19T02:00:00Z"),
                                     video("pub", "public", "2026-11-19T02:00:00Z")])
        self.assertEqual(snaps, [("pub", "6h")])
        self.assertEqual(comments, ["pub"])
        self.assertEqual(self.con.execute("SELECT privacy FROM videos WHERE video_id='prv'").fetchone()[0], "private")

    def test_unlisted_also_skipped(self):
        snaps, _ = self.pull([video("u", "unlisted", "2026-11-19T02:00:00Z")])
        self.assertEqual(snaps, [])

    def test_going_public_restarts_buckets(self):
        # an earlier run (before this fix) snapshotted the private preview: 6h and 24h at ~0 views
        self.pull([video("v", "public", "2026-11-17T00:00:00Z")])            # stored as public, upload time
        self.con.execute("UPDATE videos SET privacy='private' WHERE video_id='v'")
        for t in ("snapshots", "retention", "traffic"):
            self.con.execute(f"DELETE FROM {t}")
        self.con.commit()
        for b, hour in (("6h", 6), ("24h", 0)):
            self.now = datetime(2026, 11, 17 if hour else 18, hour, 5, tzinfo=timezone.utc)
            self._insert_snap("v", b)
        self.now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
        # the publisher made it public at 11:00 UTC: publishedAt moves to the go-public time
        snaps, _ = self.pull([video("v", "public", "2026-11-19T10:59:00Z")])
        self.assertEqual(snaps, [("v", "1h")])
        left = [r[0] for r in self.con.execute("SELECT bucket FROM snapshots WHERE video_id='v'")]
        self.assertEqual(left, ["1h"])
        sid = self.con.execute("SELECT id FROM snapshots WHERE video_id='v'").fetchone()[0]
        self.assertEqual([r[0] for r in self.con.execute("SELECT snapshot_id FROM retention")], [sid])
        self.assertEqual([r[0] for r in self.con.execute("SELECT snapshot_id FROM traffic")], [sid])
        self.now = datetime(2026, 11, 19, 17, 30, tzinfo=timezone.utc)
        snaps, _ = self.pull([video("v", "public", "2026-11-19T10:59:00Z")])
        self.assertEqual(snaps, [("v", "6h")])

    def test_purge_keeps_snapshots_after_publish_time(self):
        self.pull([video("v", "private", "2026-11-18T00:00:00Z")])
        self.now = datetime(2026, 11, 18, 5, 0, tzinfo=timezone.utc)
        self._insert_snap("v", "1h")   # taken before going public
        self.now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
        self._insert_snap("v", "6h")   # after
        self.assertEqual(analytics.purge_before(self.con, "v", "2026-11-19T00:00:00Z"), 1)
        self.assertEqual([r[0] for r in self.con.execute("SELECT bucket FROM snapshots")], ["6h"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM retention").fetchone()[0], 1)

    def test_unchanged_public_video_is_not_purged(self):
        self.pull([video("v", "public", "2026-11-19T02:00:00Z")])
        self.now = datetime(2026, 11, 20, 3, 0, tzinfo=timezone.utc)
        snaps, _ = self.pull([video("v", "public", "2026-11-19T02:00:00Z")])
        self.assertEqual(snaps, [("v", "24h")])
        self.assertEqual(sorted(r[0] for r in self.con.execute("SELECT bucket FROM snapshots")), ["24h", "6h"])


class TestMapSkipsPrivate(Base):
    def _map(self, **kw):
        a = argparse.Namespace(set=None, unset=None, **kw)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            analytics.cmd_map(a)
        return buf.getvalue()

    def test_map_never_suggests_private_previews(self):
        self.episode("shiva-poison", "Shiva drinks the poison", preview="prv")
        self.pull([video("prv", "private", "2026-11-19T02:00:00Z"),
                   video("old", "public", "2026-11-10T02:00:00Z")])
        out = self._map()
        self.assertNotIn("prv", out)
        self.assertIn("old", out)
        self.assertIn("1 not public yet (skipped)", out)

    def test_map_set_refuses_non_public(self):
        self.episode("shiva-poison", "Shiva drinks the poison", preview="prv")
        self.pull([video("prv", "private", "2026-11-19T02:00:00Z")])
        with self.assertRaises(SystemExit) as cm:
            analytics.cmd_map(argparse.Namespace(set=["prv", "shiva-poison"], unset=None))
        self.assertIn("not public yet", str(cm.exception.code))
        self.assertFalse(analytics.MAP_PATH.exists())

    def test_map_set_refuses_unknown_preview_id(self):
        self.episode("shiva-poison", "Shiva drinks the poison", preview="prv")
        with self.assertRaises(SystemExit):
            analytics.cmd_map(argparse.Namespace(set=["prv", "shiva-poison"], unset=None))

    def test_public_video_still_mappable(self):
        self.episode("shiva-poison", "Shiva drinks the poison")
        self.pull([video("pub", "public", "2026-11-19T02:00:00Z")])
        with contextlib.redirect_stdout(io.StringIO()):
            analytics.cmd_map(argparse.Namespace(set=["pub", "shiva-poison"], unset=None))
        self.assertEqual(json.loads(analytics.MAP_PATH.read_text()), {"pub": "shiva-poison"})


if __name__ == "__main__":
    unittest.main()
