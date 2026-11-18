import argparse, io, json, os, sys, tempfile, unittest, urllib.error, urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import youtube_publish as yt

YT_MD = """## Title
शीर्षक
## Description
विवरण
## English title
Title
## English description
Desc
## Tags
a, b
"""


class YoutubeOpsTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(yt, "auth_headers", return_value={"Authorization": "Bearer x"})
        p.start()
        self.addCleanup(p.stop)

    def test_video_exists_true_and_false(self):
        with mock.patch.object(yt, "http", return_value={"items": [{"id": "v"}]}) as h:
            self.assertTrue(yt.video_exists("v"))
            self.assertIn("part=status", h.call_args.args[1])
            self.assertIn("id=v", h.call_args.args[1])
        with mock.patch.object(yt, "http", return_value={"items": []}):
            self.assertFalse(yt.video_exists("v"))

    def test_video_exists_uses_short_timeout_and_raises(self):
        with mock.patch.object(yt, "http", side_effect=yt.YTError(500, "boom")) as h:
            with self.assertRaises(yt.YTError):
                yt.video_exists("v")
            self.assertLessEqual(h.call_args.kwargs.get("timeout", 600), 15)

    def test_set_privacy_sends_status_body(self):
        with mock.patch.object(yt, "http", return_value={"status": {"privacyStatus": "public"}}) as h:
            self.assertEqual(yt.set_privacy("v", "public"), "public")
            method, url = h.call_args.args[:2]
            body = json.loads(h.call_args.args[2])
        self.assertEqual(method, "PUT")
        self.assertIn("part=status", url)
        self.assertEqual(body["id"], "v")
        self.assertEqual(body["status"]["privacyStatus"], "public")
        self.assertIs(body["status"]["selfDeclaredMadeForKids"], False)
        self.assertIs(body["status"]["embeddable"], True)

    def test_set_privacy_rejects_unknown(self):
        with mock.patch.object(yt, "http") as h:
            with self.assertRaises(ValueError):
                yt.set_privacy("v", "secret")
            h.assert_not_called()

    def test_delete_404_is_ok(self):
        with mock.patch.object(yt, "http", side_effect=yt.YTError(404, "gone")):
            yt.delete_video("v")

    def test_delete_other_errors_propagate(self):
        with mock.patch.object(yt, "http", side_effect=yt.YTError(403, "no")):
            with self.assertRaises(yt.YTError):
                yt.delete_video("v")

    def test_delete_sends_delete(self):
        with mock.patch.object(yt, "http", return_value={}) as h:
            yt.delete_video("v")
        self.assertEqual(h.call_args.args[0], "DELETE")
        self.assertIn("id=v", h.call_args.args[1])

    def test_main_prints_and_exits_on_yterror(self):
        with mock.patch.object(yt, "http", side_effect=yt.YTError(403, "nope")), \
             mock.patch.object(sys, "argv", ["yt", "delete", "v"]):
            with self.assertRaises(SystemExit) as cm:
                yt.main()
        self.assertIn("HTTP 403", str(cm.exception.code))

    def test_preview_logs_youtube_preview_not_youtube(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "ep"
            (ep / "out/final").mkdir(parents=True)
            (ep / "out/package").mkdir(parents=True)
            (ep / "out/final/short-hi.mp4").write_bytes(b"x")
            (ep / "out/package/youtube.md").write_text(YT_MD)
            (ep / "episode.json").write_text(json.dumps({"id": "ep"}))
            a = argparse.Namespace(episode=str(ep), video="short-hi.mp4", privacy="public", publish_at=None,
                                   synthetic=False, yes_publish=False, dry_run=False, preview=True)
            out = io.StringIO()
            with mock.patch.object(yt, "upload_video", return_value="abc123") as up, \
                 mock.patch.object(yt, "upload_caption"), redirect_stdout(out):
                yt.cmd_publish(a)
            body = up.call_args.args[1]
            self.assertEqual(body["status"]["privacyStatus"], "private")
            self.assertNotIn("publishAt", body["status"])
            info = json.loads((ep / "episode.json").read_text())
        pub = info["published"]
        self.assertNotIn("youtube", pub)
        self.assertEqual(pub["youtube_preview"]["id"], "abc123")
        self.assertIn("url", pub["youtube_preview"])
        self.assertIn("uploaded", pub["youtube_preview"])
        self.assertEqual(out.getvalue().strip().splitlines()[-1], "preview_id=abc123")

    def test_publish_without_flags_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "ep"
            (ep / "out/final").mkdir(parents=True)
            (ep / "out/package").mkdir(parents=True)
            (ep / "out/final/short-hi.mp4").write_bytes(b"x")
            (ep / "out/package/youtube.md").write_text(YT_MD)
            (ep / "episode.json").write_text(json.dumps({"id": "ep"}))
            a = argparse.Namespace(episode=str(ep), video="short-hi.mp4", privacy="private", publish_at=None,
                                   synthetic=False, yes_publish=False, dry_run=False, preview=False)
            with mock.patch.object(yt, "upload_video") as up, redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    yt.cmd_publish(a)
            up.assert_not_called()


class TokenRefreshFailureTest(unittest.TestCase):
    """R3: a dead refresh token stays a clean SystemExit for yt.access_token() and every importer."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / "client.json").write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "SEKRET"}}))
        (d / "token.json").write_text(json.dumps({"refresh_token": "RT", "expires_at": 0}))
        for name, val in (("CLIENT", d / "client.json"), ("TOKEN", d / "token.json")):
            p = mock.patch.object(yt, name, val)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(yt, "REDACT", [])
        p.start()
        self.addCleanup(p.stop)
        err = urllib.error.HTTPError(yt.TOKEN_URL, 400, "bad", {}, io.BytesIO(b"invalid_grant SEKRET"))
        p = mock.patch.object(urllib.request, "urlopen", side_effect=err)
        self.urlopen = p.start()
        self.addCleanup(p.stop)

    def test_access_token_refresh_failure_exits_scrubbed(self):
        with self.assertRaises(SystemExit) as cm:
            yt.access_token()
        msg = str(cm.exception.code)
        self.assertIn("HTTP 400", msg)
        self.assertNotIn("SEKRET", msg)

    def test_analytics_pull_exits_cleanly(self):
        import analytics
        a = argparse.Namespace(video=None)
        with mock.patch.object(analytics, "db", return_value=mock.MagicMock()), \
             mock.patch.object(analytics, "load_episodes", return_value=[]), \
             mock.patch.object(analytics, "effective_map", return_value={}):
            with self.assertRaises(SystemExit) as cm:
                analytics.cmd_pull(a)
        self.assertNotIn("SEKRET", str(cm.exception.code))
        self.assertGreaterEqual(self.urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
