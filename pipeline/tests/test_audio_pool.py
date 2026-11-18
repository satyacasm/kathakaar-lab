import io, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
for p in (PIPELINE, os.path.join(PIPELINE, "loop")):
    if p not in sys.path:
        sys.path.insert(0, p)

import audio_pool
import vqueue
from audio_pool import PoolError


class FakeResp:
    def __init__(self, body=b"ID3" + b"\0" * 100, ctype="audio/mpeg", url="https://cdn.pixabay.com/a.mp3", length=None):
        self._f = io.BytesIO(body)
        self.headers = {"Content-Type": ctype}
        if length is not None:
            self.headers["Content-Length"] = str(length)
        self._url = url

    def geturl(self):
        return self._url

    def read(self, n=-1):
        return self._f.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class PoolBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.pool, self.assets = root / "pool", root / "ASSETS.md"
        self.assets.write_text("# Assets\n\nexisting\n")
        for name, val in (("POOL", self.pool), ("FLAGS", self.pool / "flags.json"), ("ASSETS", self.assets)):
            m = mock.patch.object(audio_pool, name, val)
            m.start()
            self.addCleanup(m.stop)
        q = mock.patch.object(vqueue, "QUEUE", root / "queue.json")
        q.start()
        self.addCleanup(q.stop)

    def track(self, kind, name):
        d = self.pool / kind
        d.mkdir(parents=True, exist_ok=True)
        f = d / name
        f.write_bytes(b"x")
        return f

    def fetch(self, resp, url="https://pixabay.com/music/x/", title="Epic Dawn"):
        with mock.patch.object(audio_pool, "_open", return_value=resp):
            return audio_pool.fetch_library(url, title, "Some Artist", "https://pixabay.com/service/license-summary/")


class TestList(PoolBase):
    def test_list_ignores_non_audio(self):
        a = self.track("popular", "a.mp3")
        self.track("popular", "notes.txt")
        self.track("popular", ".DS_Store")
        self.assertEqual(audio_pool.list_tracks("popular"), [a])

    def test_list_missing_dir_and_bad_kind(self):
        self.assertEqual(audio_pool.list_tracks("library"), [])
        with self.assertRaises(PoolError):
            audio_pool.list_tracks("bogus")


class TestFlags(PoolBase):
    def test_two_flags_block_track(self):
        a, b = self.track("popular", "a.mp3"), self.track("popular", "b.mp3")
        self.assertEqual(audio_pool.flag(a, "claim", "content id"), 1)
        self.assertFalse(audio_pool.blocked(a))
        self.assertIn(a, audio_pool.list_tracks("popular"))
        self.assertEqual(audio_pool.flag(a, "mute", "muted"), 2)
        self.assertTrue(audio_pool.blocked(a))
        self.assertFalse(audio_pool.blocked(b))
        self.assertEqual(audio_pool.list_tracks("popular"), [b])

    def test_flag_rejects_bad_kind(self):
        a = self.track("popular", "a.mp3")
        with self.assertRaises(PoolError):
            audio_pool.flag(a, "dislike", "")


class TestUseCount(PoolBase):
    def test_use_count(self):
        a = self.track("popular", "a.mp3")
        self.assertEqual(audio_pool.use_count(a), 0)  # no queue file
        vqueue.add("v1", {"format": "f", "audio": "a", "slot_pref": "any", "audio_file": str(a)}, "api")
        vqueue.add("v2", {"format": "f", "audio": "a", "slot_pref": "any", "audio_file": "popular/a.mp3"}, "api")
        vqueue.add("v3", {"format": "f", "audio": "a", "slot_pref": "any", "audio_file": "popular/other.mp3"}, "api")
        self.assertEqual(audio_pool.use_count(a), 2)


class TestFetch(PoolBase):
    def test_fetch_refuses_other_hosts(self):
        for url in ("https://example.com/a.mp3", "http://pixabay.com/a.mp3", "https://pixabay.com.evil.com/a.mp3",
                    "https://evil.com/pixabay.com/a.mp3", "https://pixabay.com@evil.com/a.mp3", "file:///etc/passwd"):
            with self.assertRaises(PoolError, msg=url):
                audio_pool.fetch_library(url, "t", "a", "l")

    def test_fetch_refuses_redirect_off_pixabay(self):
        h = audio_pool._HostCheckRedirect()
        req = mock.Mock(full_url="https://pixabay.com/a")
        with self.assertRaises(PoolError):
            h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/a.mp3")
        self.assertIn(audio_pool._HostCheckRedirect, [type(x) for x in audio_pool._make_opener().handlers])

    def test_fetch_refuses_final_url_off_pixabay(self):
        with self.assertRaises(PoolError):
            self.fetch(FakeResp(url="https://evil.example/a.mp3"))
        self.assertEqual(list((self.pool / "library").glob("*")) if (self.pool / "library").exists() else [], [])

    def test_fetch_refuses_non_audio(self):
        with self.assertRaises(PoolError):
            self.fetch(FakeResp(ctype="text/html"))

    def test_fetch_refuses_oversize_and_deletes_partial(self):
        with mock.patch.object(audio_pool, "MAX_BYTES", 1000):
            with self.assertRaises(PoolError):
                self.fetch(FakeResp(body=b"a" * 5000))
            with self.assertRaises(PoolError):
                self.fetch(FakeResp(body=b"a", length=5000))
        self.assertEqual(list((self.pool / "library").glob("*")), [])

    def test_fetch_records_assets_row(self):
        out = self.fetch(FakeResp())
        self.assertEqual(out, self.pool / "library" / "epic-dawn.mp3")
        self.assertTrue(out.exists())
        text = self.assets.read_text()
        self.assertEqual(text.count("## Loop audio"), 1)
        rows = [l for l in text.splitlines() if "https://pixabay.com/music/x/" in l]
        self.assertEqual(len(rows), 1)
        self.assertIn("| Epic Dawn | Some Artist |", rows[0])
        self.assertTrue(rows[0].rstrip().endswith("| loop library |"))
        self.fetch(FakeResp(), title="Other")
        self.assertEqual(self.assets.read_text().count("## Loop audio"), 1)

    def test_fetch_sanitises_name_and_never_overwrites(self):
        a = self.fetch(FakeResp(), title="../../etc/Pass|wd\n")
        self.assertEqual(a.parent, self.pool / "library")
        self.assertNotIn("/", a.name[:-4])
        b = self.fetch(FakeResp(), title="../../etc/Pass|wd\n")
        self.assertNotEqual(a, b)
        self.assertTrue(a.exists() and b.exists())
        for line in self.assets.read_text().splitlines():
            if "loop library" in line:
                self.assertEqual(line.count("|"), 7)

    def test_rows_stay_in_loop_audio_section(self):
        self.fetch(FakeResp())
        self.assets.write_text(self.assets.read_text() + "\n## Later\n\ntext\n")
        self.fetch(FakeResp(), title="Second")
        text = self.assets.read_text()
        self.assertLess(text.index("Second"), text.index("## Later"))


class TestRegister(PoolBase):
    def test_register_original(self):
        src = Path(self.tmp.name) / "gen.mp3"
        src.write_bytes(b"audio")
        out = audio_pool.register_original(src, "job-123", "slow tabla\nand flute")
        self.assertEqual(out.parent, self.pool / "original")
        self.assertEqual(out.read_bytes(), b"audio")
        self.assertTrue(src.exists())
        self.assertIn("job-123", self.assets.read_text())
        self.assertIn("slow tabla and flute", self.assets.read_text())
        self.assertIn(out, audio_pool.list_tracks("original"))


if __name__ == "__main__":
    unittest.main()
