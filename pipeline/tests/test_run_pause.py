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
        # run.sh prepends /opt/homebrew/bin:$HOME/.local/bin:/usr/bin to PATH, so a fake osascript in a temp
        # $HOME/.local/bin shadows /usr/bin/osascript: no real notification ever fires; calls land in a marker file.
        self.home = self.lab / "home"
        fake = self.home / ".local" / "bin" / "osascript"
        fake.parent.mkdir(parents=True)
        self.notified = self.lab / "osascript-calls"
        fake.write_text(f"#!/bin/sh\necho \"$@\" >> '{self.notified}'\n")
        fake.chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_job(self, job):
        return subprocess.run(["bash", str(self.lab / "pipeline/loop/run.sh"), job], cwd=self.lab, env=self.env,
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
        self.assertIn("unknown job name", (self.lab / "ideas/INBOX.md").read_text())
        self.assertIn("display notification", self.notified.read_text())  # the fake, not the real one


class InstallGateTest(unittest.TestCase):
    """install.sh in a throw-away lab copy with fake launchctl/plutil and a temp HOME: nothing real is installed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Path(self.tmp.name) / "lab"
        (self.lab / "pipeline/loop").mkdir(parents=True)
        shutil.copy(REPO / "pipeline/loop/install.sh", self.lab / "pipeline/loop/install.sh")
        self.home = Path(self.tmp.name) / "home"
        bin_ = Path(self.tmp.name) / "bin"
        bin_.mkdir()
        self.calls = Path(self.tmp.name) / "calls"
        for tool in ("launchctl", "plutil"):
            f = bin_ / tool
            f.write_text(f"#!/bin/sh\necho {tool} \"$@\" >> '{self.calls}'\n")
            f.chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home), "PATH": f"{bin_}:/usr/bin:/bin"}

    def install(self, *args):
        return subprocess.run(["/bin/zsh", "-f", str(self.lab / "pipeline/loop/install.sh"), *args],
                              env=self.env, capture_output=True, text=True, timeout=60)

    def agents(self):
        return sorted(p.name for p in (self.home / "Library/LaunchAgents").glob("*.plist"))

    def test_without_rehearsal_only_original_jobs(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NOT installing produce, ask, publish-1, publish-2", r.stdout)
        self.assertEqual(self.agents(), [f"com.kathakaar.{j}.plist" for j in sorted(
            ("pull", "trends", "ig-refresh", "review"))])
        self.assertNotIn("produce", self.calls.read_text())

    def test_with_rehearsal_ok_all_jobs(self):
        (self.lab / "cache/loop").mkdir(parents=True)
        (self.lab / "cache/loop/REHEARSAL_OK").touch()
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.agents()), 8)

    def test_dry_run_prints_all_and_installs_nothing(self):
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        for j in ("pull", "trends", "ig-refresh", "review", "produce", "ask", "publish-1", "publish-2"):
            self.assertIn(f"com.kathakaar.{j}.plist", r.stdout)
        self.assertFalse((self.home / "Library/LaunchAgents").exists())
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
