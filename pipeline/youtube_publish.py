#!/usr/bin/env python3
"""Publish an episode to the Kathakaar YouTube channel (YouTube Data API v3). Standard library only.

Credentials live in ~/kathakaar-lab/secrets/ (chmod 600) and are never printed:
  youtube_client.json   the OAuth client (type "Desktop app") downloaded from Google Cloud Console
  youtube_token.json    written by `setup`: the refresh token for the channel

  setup                       open the Google consent page in the browser (loopback + PKCE), save the refresh token
  check                       show the channel the token posts to
  publish <episode> --yes-publish [--privacy private|unlisted|public] [--publish-at 2026-11-08T18:30:00+05:30]
          [--video short-hi.mp4] [--synthetic] [--dry-run]
                              upload out/final/<video> with the Hindi title, description and tags from
                              out/package/youtube.md (video language Hindi), the English title and description as an
                              "en" localization, then the Hindi and English caption files; log it in episode.json.
                              Only after Satyam said "publish" for this episode (Gate 5).

Facts that shape this (see PIPELINE.md): uploads from an unaudited API project are locked to private until the free
API audit passes; captions.insert costs 400 of the 10,000 daily quota units (videos.insert ~100). A long video's
English audio track can't be added through the API: that stays a manual Studio step.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import re
import secrets as pysecrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SECRETS = LAB / "secrets"
CLIENT = SECRETS / "youtube_client.json"
TOKEN = SECRETS / "youtube_token.json"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
CHUNK = 8 * 1024 * 1024
REDACT: list[str] = []


def scrub(text: str) -> str:
    for s in REDACT:
        if s:
            text = text.replace(s, "***")
    return text


def http(method: str, url: str, body: bytes | None = None, headers: dict | None = None, raw: bool = False):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
            return (r, data) if raw else (json.loads(data) if data else {})
    except urllib.error.HTTPError as e:
        if raw and e.code == 308:              # resumable upload: "resume incomplete"
            return e, b""
        sys.exit(f"HTTP {e.code} from {url.split('?')[0]}: {scrub(e.read().decode(errors='replace'))[:800]}")


def save(path: Path, data: dict) -> None:
    SECRETS.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))
    os.chmod(path, 0o600)


def client() -> dict:
    if not CLIENT.exists():
        sys.exit(f"missing {CLIENT}: download the OAuth client (Desktop app) JSON there first (see PUBLISHING_SETUP.md)")
    c = json.loads(CLIENT.read_text())
    c = c.get("installed") or c.get("web") or c
    REDACT.append(c.get("client_secret", ""))
    return c


def access_token() -> str:
    c = client()
    if not TOKEN.exists():
        sys.exit("no token yet: run `pipeline/youtube_publish.py setup` first")
    t = json.loads(TOKEN.read_text())
    REDACT.append(t.get("refresh_token", ""))
    if t.get("access_token") and t.get("expires_at", 0) > time.time() + 120:
        REDACT.append(t["access_token"])
        return t["access_token"]
    body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
                                   "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
    r = http("POST", TOKEN_URL, body, {"Content-Type": "application/x-www-form-urlencoded"})
    t.update(access_token=r["access_token"], expires_at=time.time() + int(r.get("expires_in", 3600)))
    REDACT.append(r["access_token"])
    save(TOKEN, t)
    return r["access_token"]


def auth_headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {access_token()}"}
    h.update(extra or {})
    return h


# ------------------------------------------------------------------ setup / check
def cmd_setup(_):
    c = client()
    verifier = base64.urlsafe_b64encode(pysecrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = pysecrets.token_urlsafe(16)
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Kathakaar: you can close this tab and return to the terminal.".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = AUTH + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})
    print("Opening the Google consent page in your browser. Sign in with the account that owns the Kathakaar channel.")
    print("If it doesn't open, paste this address into the browser:\n" + url)
    webbrowser.open(url)
    th = threading.Thread(target=srv.handle_request)
    th.start()
    th.join(timeout=600)
    srv.server_close()
    if got.get("state") != state or "code" not in got:
        sys.exit(f"consent not completed ({got.get('error', 'no reply')})")
    body = urllib.parse.urlencode({"code": got["code"], "client_id": c["client_id"], "client_secret": c["client_secret"],
                                   "redirect_uri": redirect, "grant_type": "authorization_code",
                                   "code_verifier": verifier}).encode()
    r = http("POST", TOKEN_URL, body, {"Content-Type": "application/x-www-form-urlencoded"})
    if "refresh_token" not in r:
        sys.exit("Google returned no refresh token; remove the app's access at myaccount.google.com/permissions and retry")
    save(TOKEN, {"refresh_token": r["refresh_token"], "access_token": r["access_token"],
                 "expires_at": time.time() + int(r.get("expires_in", 3600)),
                 "saved": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    print(f"saved {TOKEN.relative_to(LAB)} (chmod 600)")
    cmd_check(None)


def cmd_check(_):
    r = http("GET", f"{API}/channels?part=snippet,status&mine=true", headers=auth_headers())
    items = r.get("items", [])
    if not items:
        sys.exit("the token works but this Google account has no YouTube channel")
    ch = items[0]
    print(f"channel: {ch['snippet']['title']}  (https://www.youtube.com/channel/{ch['id']})")
    print(f"long uploads allowed: {ch.get('status', {}).get('longUploadsStatus', '?')}")


# ------------------------------------------------------------------ metadata from the package
def sections(md: str) -> dict[str, str]:
    out, key = {}, None
    for line in md.splitlines():
        if line.startswith("## "):
            key = line[3:].strip().lower()
            out[key] = ""
        elif key is not None:
            out[key] += line + "\n"
    return {k: v.strip() for k, v in out.items()}


def pick(sec: dict[str, str], *starts: str) -> str:
    for k, v in sec.items():
        if any(k.startswith(s) for s in starts):
            return v
    return ""


def metadata(ep: Path) -> dict:
    sec = sections((ep / "out/package/youtube.md").read_text())
    m = {
        "title": pick(sec, "title"),
        "description": pick(sec, "description"),
        "title_en": pick(sec, "english title", "localised english title", "localized english title"),
        "description_en": pick(sec, "english description", "localised english description", "localized english description"),
        "tags": [t.strip() for t in pick(sec, "tags").replace("\n", ",").split(",") if t.strip()],
    }
    for k in ("title", "title_en"):
        if len(m[k]) > 100:
            sys.exit(f"{k} is {len(m[k])} characters; YouTube allows 100")
    for k in ("title", "description", "title_en", "description_en"):
        if re.search(r"[<>]", m[k]):
            sys.exit(f"{k} contains < or >, which YouTube rejects")
        if not m[k]:
            sys.exit(f"youtube.md has no {k}")
    while sum(len(t) + 3 for t in m["tags"]) > 480:      # YouTube: 500 characters in all, quotes counted
        m["tags"].pop()
    return m


# ------------------------------------------------------------------ upload
def upload_video(path: Path, body: dict) -> str:
    size = path.stat().st_size
    r, _ = http("POST", f"{UPLOAD}/videos?uploadType=resumable&part=snippet,status,localizations",
                json.dumps(body).encode(), auth_headers({"Content-Type": "application/json; charset=UTF-8",
                                                         "X-Upload-Content-Type": "video/mp4",
                                                         "X-Upload-Content-Length": str(size)}), raw=True)
    loc = r.headers["Location"]
    sent = 0
    with path.open("rb") as f:
        while sent < size:
            f.seek(sent)
            chunk = f.read(CHUNK)
            end = sent + len(chunk) - 1
            r, data = http("PUT", loc, chunk, auth_headers({"Content-Length": str(len(chunk)),
                                                            "Content-Range": f"bytes {sent}-{end}/{size}"}), raw=True)
            if (getattr(r, "status", None) or getattr(r, "code", 0)) == 308:
                rng = r.headers.get("Range")
                sent = int(rng.split("-")[1]) + 1 if rng else 0
            else:
                sent = size
                video = json.loads(data)
            print(f"  uploaded {100 * sent // size}%")
    return video["id"]


def upload_caption(video_id: str, lang: str, name: str, srt: Path) -> str:
    boundary = uuid.uuid4().hex
    meta = json.dumps({"snippet": {"videoId": video_id, "language": lang, "name": name, "isDraft": False}})
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + srt.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    r = http("POST", f"{UPLOAD}/captions?uploadType=multipart&part=snippet", body,
             auth_headers({"Content-Type": f"multipart/related; boundary={boundary}"}))
    return r["id"]


def cmd_publish(a):
    ep = Path(a.episode)
    ep = ep if ep.is_dir() else LAB / "episodes" / a.episode
    info = json.loads((ep / "episode.json").read_text())
    video = ep / "out/final" / a.video
    if not video.exists():
        sys.exit(f"missing {video.relative_to(LAB)}: render it first (engine/render.sh)")
    m = metadata(ep)
    status = {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False, "embeddable": True,
              "containsSyntheticMedia": bool(a.synthetic)}
    if a.publish_at:
        status.update(privacyStatus="private", publishAt=a.publish_at)
    body = {"snippet": {"title": m["title"], "description": m["description"], "tags": m["tags"], "categoryId": "1",
                        "defaultLanguage": "hi", "defaultAudioLanguage": "hi"},
            "status": status,
            "localizations": {"en": {"title": m["title_en"], "description": m["description_en"]}}}
    caps = [(lang, name, ep / "out/package" / f"captions_{lang}.srt") for lang, name in (("hi", "Hindi"), ("en", "English"))]
    caps = [c for c in caps if c[2].exists()]
    print(f"episode {info['id']}: {video.relative_to(LAB)} ({video.stat().st_size / 1e6:.1f} MB)")
    print(f"  privacy {status['privacyStatus']}" + (f", goes public at {a.publish_at}" if a.publish_at else "")
          + f"; synthetic-content label {'on' if a.synthetic else 'off'}; {len(m['tags'])} tags")
    print(f"  captions: {', '.join(c[0] for c in caps) or 'none'}; localization: en")
    if a.dry_run:
        print("dry run: nothing uploaded")
        return
    if not a.yes_publish:
        sys.exit("refusing to upload without --yes-publish (only after Satyam said \"publish\" for this episode)")
    vid = upload_video(video, body)
    url = f"https://www.youtube.com/shorts/{vid}" if info.get("format") == "short" else f"https://youtu.be/{vid}"
    print(f"uploaded: {url}")
    done = []
    for lang, name, srt in caps:
        upload_caption(vid, lang, name, srt)
        done.append(lang)
        print(f"  captions {lang} added")
    info.setdefault("published", {})["youtube"] = {
        "id": vid, "url": url, "privacy": status["privacyStatus"], "publish_at": a.publish_at,
        "captions": done, "uploaded": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (ep / "episode.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n")
    print("logged in episode.json. If the project isn't audited yet, YouTube keeps the video private: check Studio.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(required=True)
    sub.add_parser("setup").set_defaults(f=cmd_setup)
    sub.add_parser("check").set_defaults(f=cmd_check)
    p = sub.add_parser("publish")
    p.add_argument("episode")
    p.add_argument("--video", default="short-hi.mp4")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--publish-at", help="RFC 3339 time; uploads private and YouTube makes it public then")
    p.add_argument("--synthetic", action="store_true", help="tick YouTube's altered/synthetic content label")
    p.add_argument("--yes-publish", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(f=cmd_publish)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
