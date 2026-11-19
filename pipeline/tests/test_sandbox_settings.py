"""The producer's Bash sandbox settings (pipeline/loop/sandbox_settings.py) and run.sh's use of them."""
import json, subprocess, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline" / "loop"))
import sandbox_settings  # noqa: E402

LAB, HOME = "/u/me/lab", "/u/me"


class SandboxSettingsTest(unittest.TestCase):
    def setUp(self):
        self.sb = sandbox_settings.settings(LAB, HOME)["sandbox"]
        self.fs = self.sb["filesystem"]

    def test_strict_mode(self):
        self.assertTrue(self.sb["enabled"])
        self.assertTrue(self.sb["failIfUnavailable"])
        self.assertFalse(self.sb["allowUnsandboxedCommands"])
        self.assertFalse(self.sb["autoAllowBashIfSandboxed"])

    def test_lab_root_readable_home_denied(self):
        # getcwd() opens the working directory: the lab root itself must be readable (rehearsal 2026-11-19)
        self.assertIn(LAB, self.fs["allowRead"])
        self.assertIn(HOME, self.fs["denyRead"])
        self.assertNotIn(HOME, self.fs["allowRead"])

    def test_secrets_denied_twice(self):
        creds = {e["path"] for e in self.sb["credentials"]["files"] if e["mode"] == "deny"}
        for p in (f"{LAB}/secrets", f"{HOME}/.ssh", f"{HOME}/.cache/huggingface/token"):
            self.assertIn(p, creds)
            self.assertIn(p, self.fs["denyRead"])
            self.assertNotIn(p, self.fs["allowRead"])
        for p in (".remember", "downloads", ".git"):
            self.assertIn(f"{LAB}/{p}", self.fs["denyRead"])

    def test_allow_read_never_covers_a_credential(self):
        creds = [e["path"] for e in self.sb["credentials"]["files"]]
        for a in self.fs["allowRead"]:
            if a == LAB:
                continue  # the lab is allowed; secrets/ inside it is re-denied (denyRead + credentials)
            for c in creds:
                self.assertFalse(c == a or c.startswith(a + "/"), (a, c))

    def test_code_and_secrets_write_denied(self):
        for p in ("pipeline", "engine", "secrets", ".git", ".claude"):
            self.assertIn(f"{LAB}/{p}", self.fs["denyWrite"])

    def test_excluded_commands_are_the_fixed_few(self):
        self.assertEqual(self.sb["excludedCommands"], [
            "python3 pipeline/loop/produce.py finish *",
            "python3 pipeline/loop/produce.py voice *",
            "pipeline/.venv/bin/python pipeline/reel.py * stills",
            "pipeline/.venv/bin/python pipeline/reel.py * stills --*",
        ])

    def test_network_allowlist_unchanged(self):
        self.assertEqual(set(self.sb["network"]), {"allowedDomains"})
        self.assertNotIn("*", self.sb["network"]["allowedDomains"])
        self.assertIn("*.higgsfield.ai", self.sb["network"]["allowedDomains"])

    def test_cli_prints_json(self):
        out = subprocess.run([sys.executable, str(REPO / "pipeline/loop/sandbox_settings.py"), LAB, HOME],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), sandbox_settings.settings(LAB, HOME))

    def test_run_sh_uses_the_module(self):
        text = (REPO / "pipeline/loop/run.sh").read_text()
        self.assertIn('python3 pipeline/loop/sandbox_settings.py "$LAB" "$HOME"', text)


if __name__ == "__main__":
    unittest.main()
