"""Output-path confinement: the review job's allow-listed scripts must not write outside their data folders."""
import argparse, contextlib, io, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import features, plan, review, trends


def refused(fn, *args):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            fn(*args)
        except SystemExit as e:
            return str(e.code) if e.code not in (None, 0) else None
    return None


class TestConfine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bad = str(Path(self.tmp.name) / "evil")
        self.link = Path(self.tmp.name) / "link"

    def test_review_out_refused(self):
        msg = refused(review.cmd_pack, argparse.Namespace(out=self.bad, since=None, no_record=True))
        self.assertIn("refusing to write", msg)
        self.assertFalse(os.path.exists(self.bad))

    def test_review_out_allowed_under_review_dir(self):
        self.assertEqual(review._confine(review.REVIEW_DIR / "x.md", review.REVIEW_DIR),
                         (review.REVIEW_DIR / "x.md").resolve())

    def test_features_csv_refused(self):
        msg = refused(features.cmd_table, argparse.Namespace(csv=self.bad, no_csv=False))
        self.assertIn("refusing to write", msg)

    def test_features_csv_allowed_default_and_sibling(self):
        root = features.LAB / "cache/analytics"
        self.assertEqual(features._confine(features.CSV_DEFAULT, root), features.CSV_DEFAULT.resolve())

    def test_trends_out_refused(self):
        msg = refused(trends.cmd_digest, argparse.Namespace(out=self.bad))
        self.assertIn("refusing to write", msg)

    def test_trends_out_allowed_under_ideas(self):
        p = trends.IDEAS / "trends-2026-01-01.md"
        self.assertEqual(trends._confine(p, trends.IDEAS), p.resolve())

    def test_plan_path_refused(self):
        with self.assertRaises(SystemExit) as c, contextlib.redirect_stderr(io.StringIO()):
            plan.main(["--path", os.path.expanduser("~/.zshrc_x"), "show"])
        self.assertIn("refusing to write", str(c.exception.code))

    def test_plan_path_symlink_escape_refused(self):
        self.link.symlink_to("/etc")
        # inside tempdir lexically, but resolves outside both allowed roots
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            plan.main(["--path", str(self.link / "plan.md"), "show"])

    def test_plan_path_allowed_in_tempdir_and_ideas(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(plan.main(["--path", str(Path(self.tmp.name) / "p.md"), "show"]), 0)
        self.assertEqual(plan._confine(plan.PLAN_PATH, plan.LAB / "ideas"), plan.PLAN_PATH.resolve())

    def test_plan_env_path_refused(self):
        os.environ["PLAN_PATH"] = self.bad.replace(tempfile.gettempdir(), "/usr/local")
        self.addCleanup(os.environ.pop, "PLAN_PATH", None)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            plan.main(["show"])


class TestPlanStatus(unittest.TestCase):
    def test_status(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "p.md")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                plan.main(["--path", path, "status"])
            self.assertEqual(out.getvalue().strip(), "no plan yet")
            rows = plan.fortnight(__import__("datetime").date(2026, 11, 19), [], 300)
            plan.write(rows, path)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                plan.main(["--path", path, "status"])
            self.assertEqual(out.getvalue().strip(), "last_day=2026-12-02 rows=28")


if __name__ == "__main__":
    unittest.main()
