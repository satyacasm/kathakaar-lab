"""What an approval covers: digests of the files and episode.json fields that go public, recorded by produce.py
finish and verified by publish.py before anything is made public. Standard library only.

  finals   out/final/reel_with_song.mp4, reel_SILENT.mp4          (the videos)
  package  out/package/caption_instagram.txt, youtube.md          (the public copy)
  meta     episode.json fields the publisher reads (Instagram hand-off text: id, title_en/title_hi, song)
"""
import hashlib, json
from pathlib import Path

FINALS = ("reel_with_song.mp4", "reel_SILENT.mp4")
PACKAGE = ("caption_instagram.txt", "youtube.md")
META_FIELDS = ("id", "slug", "title_en", "title_hi", "song")
YT_META_FIELDS = ("id", "slug", "title_en", "title_hi")   # the part the YouTube preview already carries


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def meta_digest(meta: dict, fields=META_FIELDS) -> str:
    sub = {k: meta.get(k) for k in fields}
    return hashlib.sha256(json.dumps(sub, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def record(ep: Path) -> dict:
    """Queue-record fields for an episode as it is now."""
    ep = Path(ep)
    meta = json.loads((ep / "episode.json").read_text())
    return {"final_sha256": {f: sha256(ep / "out/final" / f) for f in FINALS if (ep / "out/final" / f).is_file()},
            "package_sha256": {f: sha256(ep / "out/package" / f) for f in PACKAGE if (ep / "out/package" / f).is_file()},
            "meta_sha256": meta_digest(meta), "yt_meta_sha256": meta_digest(meta, YT_META_FIELDS)}


def youtube_side_change(old: dict, new: dict):
    """None if `new` differs from `old` (both record() dicts) only in what Instagram uses (caption_instagram.txt, the
    song fields), else what changed on the YouTube side (a video file, youtube.md, the titles). Missing = changed."""
    of, nf = old.get("final_sha256") or {}, new.get("final_sha256") or {}
    for name in sorted(set(of) | set(nf)):
        if of.get(name) != nf.get(name):
            return f"final video {name}"
    if (old.get("package_sha256") or {}).get("youtube.md") != (new.get("package_sha256") or {}).get("youtube.md"):
        return "youtube.md"
    if old.get("meta_sha256") == new.get("meta_sha256"):
        return None
    if not old.get("yt_meta_sha256") or old["yt_meta_sha256"] != new.get("yt_meta_sha256"):
        return "episode.json title"   # older records cannot tell a title change from a song change: refuse
    return None


def problem(rec: dict, ep: Path):
    """None if every recorded digest still matches, else the reason. Records without digests pass (older videos)."""
    ep = Path(ep)
    for name, digest in (rec.get("final_sha256") or {}).items():
        f = ep / "out/final" / name
        if not f.is_file() or sha256(f) != digest:
            return f"final file changed since approval: {name}"
    for name, digest in (rec.get("package_sha256") or {}).items():
        f = ep / "out/package" / name
        if not f.is_file() or sha256(f) != digest:
            return f"package changed since approval: {name}"
    if rec.get("meta_sha256"):
        try:
            meta = json.loads((ep / "episode.json").read_text())
        except (OSError, ValueError) as e:
            return f"episode.json unreadable: {e}"
        if meta_digest(meta) != rec["meta_sha256"]:
            return "package changed since approval: episode.json (title/song)"
    return None
