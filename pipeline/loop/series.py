"""Queue an already-finished series (episode 005, "रामायण का मार्ग", parts 4-17) through the content loop.

  python3 pipeline/loop/series.py status          which parts are queued, and their status
  python3 pipeline/loop/series.py stage [--max N] the next N unqueued parts (default all): folder + private preview

Each part gets its own episode folder (episodes/<NNN>-ramayana-route-pNN/) so the publisher, integrity digests and
analytics treat it like any loop video: the mp4 is hard-linked (no extra disk), the package files are copied. The
record's cell is {"format": "series", "slot_pref": "19:30", ...}: approved parts go out in the evening slot, in part
order, and series records never count towards the producer's buffer. Nothing is public until `vqueue.py approve`.
Runs unsandboxed by hand (it needs secrets/ for the private upload). Standard library only.
"""
import argparse, json, os, re, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import produce, vqueue  # noqa: E402

LAB = HERE.parents[1]
SOURCE = LAB / "episodes/005-ramayana-evidence"
SHORTS = SOURCE / "out/package/shorts"
FIRST_PART = 4                       # parts 1-3 are already public (YouTube + Instagram)
SLUG = "ramayana-route"


def parts() -> list[tuple[int, Path]]:
    out = []
    for d in sorted(SHORTS.iterdir()):
        m = re.match(r"^(\d{2})_", d.name)
        if d.is_dir() and m and int(m.group(1)) >= FIRST_PART:
            out.append((int(m.group(1)), d))
    return out


def queued() -> dict[int, dict]:
    return {r["cell"]["part"]: r for r in vqueue.load()
            if (r.get("cell") or {}).get("format") == "series" and r["cell"].get("series") == SOURCE.name}


def _scaffold(n: int, src: Path, episodes: Path) -> str:
    rid = f"{produce.next_number(episodes):03d}-{SLUG}-p{n:02d}"
    ep = episodes / rid
    for sub in ("out/final", "out/package", "out/qa"):
        (ep / sub).mkdir(parents=True, exist_ok=True)
    mp4 = next(src.glob("*.mp4"))
    dest = ep / "out/final/reel_with_song.mp4"
    try:
        os.link(mp4, dest)
    except OSError:
        shutil.copy2(mp4, dest)
    for name in ("youtube.md", "caption_instagram.txt", "captions_hi.srt"):
        if (src / name).exists():
            shutil.copy2(src / name, ep / "out/package" / name)
    if (src / "cover.jpg").exists():
        shutil.copy2(src / "cover.jpg", ep / "out/final/cover.jpg")
    base = json.loads((SOURCE / "episode.json").read_text())
    title = produce_title(ep)
    meta = {"id": f"E{rid[:3]}", "slug": rid, "title_hi": title, "format": "narrated_reel", "kind": "narrated_reel",
            "narration": True, "resolution": "1080x1920", "languages": base.get("languages", {"primary": "hi"}),
            "sources": base.get("sources", []), "status": "assembled", "published": {},
            "platforms": ["instagram", "youtube"], "series": {"of": SOURCE.name, "part": n, "folder": src.name},
            "outputs": {"preview": "out/final/reel_with_song.mp4", "cover": "out/final/cover.jpg"},
            "loop": {"format": "series", "audio": "own", "topic_source": "series"}}
    (ep / "episode.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    return rid


def produce_title(ep: Path) -> str:
    for line in (ep / "out/package/youtube.md").read_text().split("\n## ")[1:]:
        head, _, body = line.partition("\n")
        if head.lower().startswith("title"):
            return body.strip().splitlines()[0]
    return ""


def stage(max_n=None, episodes: Path | None = None) -> list[str]:
    episodes = Path(episodes or produce.EPISODES)
    done, todo = queued(), [(n, d) for n, d in parts() if n not in queued()]
    out = []
    for n, src in todo[:max_n]:
        rid = _scaffold(n, src, episodes)
        cell = {"format": "series", "audio": "own", "topic_source": "series", "series": SOURCE.name, "part": n,
                "slot_pref": "19:30"}
        vqueue.add(rid, cell, "api")
        vqueue.transition(rid, "producing")
        try:
            produce.frames(rid)
            out.append(produce.finish(rid))
        except Exception as e:
            produce.fail(rid, f"series stage: {e}")
            out.append(f"FAILED {rid}: {e}")
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("stage"); s.add_argument("--max", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        q = queued()
        for n, d in parts():
            r = q.get(n)
            print(f"part {n:02d} {d.name:40s} {r['id'] + ' ' + r['status'] if r else '(not queued)'}")
    else:
        for line in stage(a.max):
            print(line)


if __name__ == "__main__":
    main()
