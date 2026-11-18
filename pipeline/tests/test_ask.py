import json, os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ask
from vqueue import TZ


def rec(rid, status="preview_ready", yt="abc", ig="api", credits=10, fmt="music_reel", audio="popular"):
    return {"id": rid, "status": status, "cell": {"format": fmt, "audio": audio}, "yt_id": yt,
            "ig_mode": ig, "credits": credits}


class TestAsk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, val in (("STATE", Path(self.tmp.name) / "ask_state.json"), ("EPISODES", Path(self.tmp.name))):
            p = mock.patch.object(ask, name, val); p.start(); self.addCleanup(p.stop)
        self.now = datetime(2026, 11, 19, 9, 0, tzinfo=TZ)

    def test_compose_none_when_empty(self):
        self.assertIsNone(ask.compose([]))
        self.assertIsNone(ask.compose([rec("a", "approved")]))

    def test_compose_lists_private_links(self):
        out = ask.compose([rec("a"), rec("b", yt="xyz", ig="manual")])
        self.assertIn("https://youtu.be/abc", out)
        self.assertIn("(private)", out)
        self.assertIn("https://youtu.be/xyz", out)
        self.assertIn("IG: by hand", out)
        self.assertIn("IG: api", out)
        self.assertIn("python3 pipeline/loop/vqueue.py approve <id>", out)
        self.assertIn('python3 pipeline/loop/vqueue.py reject <id> --reason "', out)
        self.assertEqual(len(ask.compose([rec("a")], multiline=False).splitlines()), 1)

    def test_title_from_package_else_id(self):
        pkg = Path(self.tmp.name) / "a" / "out" / "package"
        pkg.mkdir(parents=True)
        (pkg / "youtube.md").write_text("## Title\nHello Title\n")
        self.assertEqual(ask._title("a"), "Hello Title")
        self.assertEqual(ask._title("missing"), "missing")

    def test_run_no_duplicate_same_set(self):
        with mock.patch.object(ask.inbox, "add") as add, mock.patch.object(ask.vqueue, "load", return_value=[rec("a")]):
            self.assertTrue(ask.run(self.now))
            self.assertFalse(ask.run(self.now))
            self.assertEqual(add.call_count, 1)
            self.assertEqual(add.call_args[0][1], "decision")
            self.assertNotIn("\n", add.call_args[0][0])

    def test_run_new_set_asks_again(self):
        recs = [rec("a")]
        with mock.patch.object(ask.inbox, "add") as add, mock.patch.object(ask.vqueue, "load", return_value=recs):
            ask.run(self.now)
            recs.append(rec("b"))
            self.assertTrue(ask.run(self.now))
            self.assertEqual(add.call_count, 2)
            self.assertTrue(ask.run(self.now.replace(day=20)))  # same set, new IST day: ask again
            self.assertEqual(add.call_count, 3)
