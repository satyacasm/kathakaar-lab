import os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib.util

_spec = importlib.util.spec_from_file_location("reel_cli", os.path.join(PIPELINE, "reel.py"))
reel_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reel_cli)


class ResolveEpTest(unittest.TestCase):
    """reel.py stages write under the episode, so the episode must sit directly inside episodes/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.eps = self.root / "episodes"
        (self.eps / "001-a/script").mkdir(parents=True)
        (self.root / "elsewhere/script").mkdir(parents=True)
        (self.eps / "001-a/nested/script").mkdir(parents=True)
        (self.eps / "002-link").symlink_to(self.root / "elsewhere")

    def resolve(self, arg):
        return reel_cli.resolve_ep(arg, self.eps)

    def test_slug_and_path_inside_episodes(self):
        self.assertEqual(self.resolve("001-a"), self.eps / "001-a")
        self.assertEqual(self.resolve(str(self.eps / "001-a")), self.eps / "001-a")

    def test_refuses_folders_elsewhere(self):
        for arg in (str(self.root / "elsewhere"), str(self.eps / "001-a/nested"), "002-link", "nope"):
            with self.assertRaises(SystemExit, msg=arg):
                with unittest.mock.patch("sys.stderr"):
                    self.resolve(arg)


class HeroDateTest(unittest.TestCase):
    """hero-log --date: a loop video may only log today's IST date."""

    def setUp(self):
        import json
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.q = Path(self.tmp.name) / "queue.json"
        self.q.write_text(json.dumps([{"id": "loop-ep"}]))

    def check(self, name, date):
        with unittest.mock.patch("sys.stderr"):
            reel_cli.check_hero_date(Path("/x") / name, date, self.q, today="2026-11-19")

    def test_loop_video_other_date_refused(self):
        with self.assertRaises(SystemExit) as cm:
            self.check("loop-ep", "2026-10-31")
        self.assertEqual(cm.exception.code, 2)

    def test_loop_video_today_and_no_date_ok(self):
        self.check("loop-ep", "2026-11-19")
        self.check("loop-ep", None)

    def test_hand_made_episode_may_backdate(self):
        self.check("hand-ep", "2026-10-31")

    def test_no_queue_file_ok(self):
        self.q.unlink()
        self.check("loop-ep", "2026-10-31")


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
