"""run.sh PAUSE switch, tested in a throw-away lab copy (no real cache, no network, no jobs run)."""
import os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "pipeline", REPO / "pipeline" / "loop"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


class RunPauseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Path(self.tmp.name)
        loop = self.lab / "pipeline" / "loop"
        loop.mkdir(parents=True)
        shutil.copy(REPO / "pipeline/loop/run.sh", loop / "run.sh")
        shutil.copy(REPO / "pipeline/loop/inbox.py", loop / "inbox.py")
        for name in ("ask.py", "publish.py"):  # stubs: leave a marker when they really run
            (loop / name).write_text(f"import pathlib; pathlib.Path('ran-{name}').write_text('x')\n")
        self.pause = self.lab / "cache" / "loop" / "PAUSE"

    def tearDown(self):
        self.tmp.cleanup()

    def run_job(self, job):
        return subprocess.run(["bash", str(self.lab / "pipeline/loop/run.sh"), job], cwd=self.lab,
                              capture_output=True, text=True, timeout=60)

    def logs(self):
        return "".join(p.read_text() for p in (self.lab / "cache/loop/logs").glob("*.log"))

    def test_paused_jobs_exit_zero_and_do_not_run(self):
        self.pause.parent.mkdir(parents=True)
        self.pause.touch()
        for job in ("ask", "publish", "produce", "pull"):
            r = self.run_job(job)
            self.assertEqual(r.returncode, 0, (job, r.stderr))
        self.assertIn("paused", self.logs())
        self.assertFalse((self.lab / "ran-ask.py").exists())
        self.assertFalse((self.lab / "ran-publish.py").exists())
        self.assertFalse((self.lab / "cache/loop/locks/publish.lock").exists())

    def test_status_reports_paused(self):
        self.pause.parent.mkdir(parents=True)
        self.pause.touch()
        self.assertIn("PAUSED", self.run_job("status").stdout)

    def test_without_pause_jobs_run(self):
        self.assertNotIn("PAUSED", self.run_job("status").stdout)
        self.assertEqual(self.run_job("ask").returncode, 0)
        self.assertEqual(self.run_job("publish").returncode, 0)
        self.assertTrue((self.lab / "ran-ask.py").exists())
        self.assertTrue((self.lab / "ran-publish.py").exists())

    def test_unknown_job_still_fails(self):
        self.assertEqual(self.run_job("nope").returncode, 2)


if __name__ == "__main__":
    unittest.main()
