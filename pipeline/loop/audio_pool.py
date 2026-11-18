#!/usr/bin/env python3
"""Audio pool for the content loop. Standard library only.

  audio_pool.py list <popular|library|original>
  audio_pool.py fetch <url> --title T --artist A --licence LICENCE_URL   (Pixabay only)
  audio_pool.py register <file> --job JOB_ID --prompt "..."              (Higgsfield original music)
  audio_pool.py flag <file> --kind claim|mute --note "..."

Pool: music-lab/pool/{popular,library,original}/ (git-ignored; popular songs are supplied by the owner).
Library tracks come only from pixabay.com / cdn.pixabay.com and are logged in ASSETS.md under "## Loop audio".
A track with 2+ flags (claim/mute) is blocked and no longer listed.
"""
import argparse, json, os, re, shutil, sys, urllib.error, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vqueue

LAB = Path(__file__).resolve().parents[2]
POOL = LAB / "music-lab/pool"
FLAGS = POOL / "flags.json"
ASSETS = LAB / "ASSETS.md"

KINDS = ("popular", "library", "original")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".flac")
ALLOWED_HOSTS = ("pixabay.com", "cdn.pixabay.com")
MAX_BYTES = 25 * 1024 * 1024
BLOCK_AT = 2
CTYPE_EXT = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
             "audio/wave": ".wav", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/m4a": ".m4a",
             "audio/flac": ".flac", "audio/x-flac": ".flac"}
HEADING = "## Loop audio"
TABLE_HEAD = ["| Date | Title | Artist | URL | Licence | Kind |", "|---|---|---|---|---|---|"]


class PoolError(Exception):
    pass


# ---- listing, flags, usage -------------------------------------------------

def _key(path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(Path(POOL).resolve()))
    except ValueError:
        return str(p)


def _flags() -> dict:
    try:
        return json.loads(Path(FLAGS).read_text())
    except FileNotFoundError:
        return {}


def flag(path, kind: str, note: str) -> int:
    if kind not in ("claim", "mute"):
        raise PoolError(f"flag kind must be claim or mute, not {kind!r}")
    data = _flags()
    entries = data.setdefault(_key(path), [])
    entries.append({"kind": kind, "note": " ".join(str(note).split()), "date": date.today().isoformat()})
    Path(FLAGS).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(FLAGS) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, FLAGS)
    return len(entries)


def blocked(path) -> bool:
    return len(_flags().get(_key(path), [])) >= BLOCK_AT


def list_tracks(kind: str) -> list[Path]:
    if kind not in KINDS:
        raise PoolError(f"kind must be one of {KINDS}, not {kind!r}")
    d = Path(POOL) / kind
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.is_file() and p.suffix.lower() in AUDIO_EXT and not blocked(p))


def use_count(path) -> int:
    """How many queue records already use this track (cell.audio_file)."""
    key, resolved = _key(path), str(Path(path).resolve())
    n = 0
    for rec in vqueue.load():
        af = str((rec.get("cell") or {}).get("audio_file") or "")
        if af and (af == key or af.endswith("/" + key) or af == resolved or str(Path(af).resolve()) == resolved):
            n += 1
    return n


# ---- ASSETS.md log ---------------------------------------------------------

def _cell(s) -> str:
    return " ".join(str(s).replace("|", "/").split())


def _append_row(title, artist, url, licence, kind):
    p = Path(ASSETS)
    lines = p.read_text().splitlines() if p.exists() else []
    if HEADING not in lines:
        lines += ["", HEADING, ""] + TABLE_HEAD
    row = "| " + " | ".join([date.today().isoformat(), _cell(title), _cell(artist), _cell(url),
                             _cell(licence), kind]) + " |"
    i = lines.index(HEADING) + 1
    while i < len(lines) and not lines[i].startswith("|"):
        i += 1
    while i < len(lines) and lines[i].startswith("|"):
        i += 1
    lines.insert(i, row)
    p.write_text("\n".join(lines) + "\n")


# ---- Pixabay fetch ---------------------------------------------------------

def _check_url(url: str):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS or u.username or u.password:
        raise PoolError(f"refusing URL (https on {' / '.join(ALLOWED_HOSTS)} only): {url}")


class _HostCheckRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(urllib.parse.urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _make_opener():
    return urllib.request.build_opener(_HostCheckRedirect())


def _open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "kathakaar-loop/1.0"})
    return _make_opener().open(req, timeout=60)


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")[:60].strip("-")
    return s or "track"


def _create_unique(d: Path, slug: str, ext: str):
    d.mkdir(parents=True, exist_ok=True)
    for n in range(0, 1000):
        dest = d / (f"{slug}{ext}" if n == 0 else f"{slug}-{n + 1}{ext}")
        try:
            return dest, open(dest, "xb")
        except FileExistsError:
            continue
    raise PoolError("could not find a free file name")


def fetch_library(url: str, title: str, artist: str, licence_url: str) -> Path:
    _check_url(url)
    try:
        resp = _open(url)
    except PoolError:
        raise
    except (urllib.error.URLError, OSError) as e:
        raise PoolError(f"download failed: {e}") from e
    with resp:
        _check_url(resp.geturl())
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = CTYPE_EXT.get(ctype)
        if ext is None:
            raise PoolError(f"not an audio content type: {ctype or 'none'}")
        try:
            declared = int(resp.headers.get("Content-Length") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_BYTES:
            raise PoolError(f"file too large ({declared} bytes, cap {MAX_BYTES})")
        dest, f = _create_unique(Path(POOL) / "library", _slug(title), ext)
        ok = False
        try:
            with f:
                size = 0
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise PoolError(f"file too large (over {MAX_BYTES} bytes)")
                    f.write(chunk)
            if size == 0:
                raise PoolError("empty download")
            ok = True
        except OSError as e:
            raise PoolError(f"download failed: {e}") from e
        finally:
            if not ok:
                dest.unlink(missing_ok=True)
    _append_row(title, artist, url, licence_url, "loop library")
    return dest


def register_original(path, job_id: str, prompt: str) -> Path:
    src = Path(path)
    if src.suffix.lower() not in AUDIO_EXT or not src.is_file():
        raise PoolError(f"not an audio file: {src}")
    dest, f = _create_unique(Path(POOL) / "original", _slug(src.stem), src.suffix.lower())
    with f, open(src, "rb") as s:
        shutil.copyfileobj(s, f)
    _append_row(dest.name, "Higgsfield generate_audio", f"job {job_id}", f"generated; prompt: {prompt}",
                "loop original")
    return dest


# ---- CLI -------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("kind", choices=KINDS)
    s = sub.add_parser("fetch"); s.add_argument("url")
    s.add_argument("--title", required=True); s.add_argument("--artist", required=True)
    s.add_argument("--licence", required=True, help="licence URL")
    s = sub.add_parser("register"); s.add_argument("file")
    s.add_argument("--job", required=True); s.add_argument("--prompt", required=True)
    s = sub.add_parser("flag"); s.add_argument("file")
    s.add_argument("--kind", required=True, choices=("claim", "mute")); s.add_argument("--note", default="")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "list":
            for p in list_tracks(a.kind):
                print(f"{use_count(p)}\t{p}")
        elif a.cmd == "fetch":
            print(fetch_library(a.url, a.title, a.artist, a.licence))
        elif a.cmd == "register":
            print(register_original(Path(a.file), a.job, a.prompt))
        elif a.cmd == "flag":
            n = flag(Path(a.file), a.kind, a.note)
            print(f"{n} flag(s); blocked={blocked(Path(a.file))}")
    except PoolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
