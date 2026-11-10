#!/usr/bin/env python3
"""Publish an episode's Reel to the Kathakaar Instagram account (Instagram API with Instagram Login).

Standard library only. Credentials live in ~/kathakaar-lab/secrets/instagram.json (chmod 600) and are never printed.

  setup                      ask (hidden input) for the token from the app dashboard and, optionally, the app secret;
                             exchange for a 60-day token, look up the account, save. Run it in Terminal.app.
  check                      verify the saved token and show the account it posts to, plus days left
  refresh                    renew the 60-day token (allowed once it is at least 24 h old)
  publish <episode> --yes-publish [--video short-hi.mp4] [--dry-run]
                             upload out/final/<video> as a Reel with the caption in out/package/caption_instagram.txt,
                             wait until Instagram has processed it, publish, and log the result in episode.json.
                             Only after Satyam said "publish" for this episode (Gate 5).

Flow (Meta docs): POST graph.instagram.com/<ver>/<ig-user-id>/media (media_type=REELS, upload_type=resumable)
→ POST rupload.facebook.com/ig-api-upload/<ver>/<container-id> (the bytes) → poll status_code until FINISHED
→ POST /<ig-user-id>/media_publish (creation_id).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SECRETS = LAB / "secrets/instagram.json"
GRAPH = "https://graph.instagram.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"
VERSION = os.environ.get("IG_API_VERSION", "v26.0")
MAX_BYTES = 300 * 1024 * 1024            # stay well inside Reels limits
REDACT = []                               # secrets to scrub from any error text


def scrub(text: str) -> str:
    for s in REDACT:
        if s:
            text = text.replace(s, "***")
    return text


def call(method: str, url: str, params: dict | None = None, headers: dict | None = None, body: bytes | None = None) -> dict:
    if params and method == "GET":
        url += "?" + urllib.parse.urlencode(params)
        data = body
    elif params:
        data = urllib.parse.urlencode(params).encode()
    else:
        data = body
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(scrub(f"Instagram API error {e.code} on {method} {url.split('?')[0]}: {detail}"))


def load() -> dict:
    if not SECRETS.exists():
        raise SystemExit(f"No credentials yet: run `{Path(__file__).name} setup` in Terminal.app")
    if SECRETS.stat().st_mode & 0o077:
        raise SystemExit(f"{SECRETS} is readable by others; run: chmod 600 {SECRETS}")
    s = json.loads(SECRETS.read_text())
    REDACT.extend([s.get("access_token", ""), s.get("app_secret", "")])
    return s


def save(s: dict) -> None:
    SECRETS.parent.mkdir(mode=0o700, exist_ok=True)
    tmp = SECRETS.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1))
    os.chmod(tmp, 0o600)
    tmp.replace(SECRETS)


def days_left(s: dict) -> str:
    if not s.get("expires_at"):
        return "unknown"
    return f"{(s['expires_at'] - time.time()) / 86400:.0f}"


def cmd_setup(_):
    token = getpass.getpass("Paste the access token from the app dashboard (hidden): ").strip()
    secret = getpass.getpass("Paste the Instagram app secret to get a 60-day token (hidden, Enter to skip): ").strip()
    REDACT.extend([token, secret])
    s = {"access_token": token, "expires_at": None}
    if secret:
        r = call("GET", f"{GRAPH}/access_token", {"grant_type": "ig_exchange_token", "client_secret": secret, "access_token": token})
        s["access_token"] = r["access_token"]
        s["expires_at"] = time.time() + int(r.get("expires_in", 0))
        REDACT.append(s["access_token"])
    me = call("GET", f"{GRAPH}/{VERSION}/me", {"fields": "user_id,username,account_type", "access_token": s["access_token"]})
    s.update(ig_user_id=me["user_id"], username=me.get("username"), account_type=me.get("account_type"),
             saved_at=datetime.now(timezone.utc).isoformat())
    save(s)
    print(f"Saved. Posting account: @{s['username']} ({s['account_type']}); token days left: {days_left(s)}")


def cmd_check(_):
    s = load()
    me = call("GET", f"{GRAPH}/{VERSION}/me", {"fields": "user_id,username,account_type", "access_token": s["access_token"]})
    print(f"OK: @{me.get('username')} ({me.get('account_type')}), user id matches: {me['user_id'] == s['ig_user_id']}; "
          f"token days left: {days_left(s)}")


def cmd_refresh(_):
    s = load()
    r = call("GET", f"{GRAPH}/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": s["access_token"]})
    s["access_token"], s["expires_at"] = r["access_token"], time.time() + int(r.get("expires_in", 0))
    save(s)
    print(f"Refreshed; token days left: {days_left(s)}")


def cmd_publish(a):
    ep = Path(a.episode)
    ep = ep if ep.is_dir() else LAB / "episodes" / a.episode
    meta_path = ep / "episode.json"
    meta = json.loads(meta_path.read_text())
    video = ep / "out/final" / a.video
    caption_file = ep / "out/package/caption_instagram.txt"
    if not video.exists():
        raise SystemExit(f"missing video: {video}")
    if not caption_file.exists():
        raise SystemExit(f"missing caption: {caption_file}")
    caption = caption_file.read_text().strip()
    size = video.stat().st_size
    if size > MAX_BYTES:
        raise SystemExit(f"{video.name} is {size / 2**20:.0f} MB; re-encode below {MAX_BYTES / 2**20:.0f} MB first")
    if meta.get("published", {}).get("instagram"):
        raise SystemExit(f"already on Instagram: {meta['published']['instagram'].get('permalink')}")
    print(f"Episode {meta['id']} · {video.name} · {size / 2**20:.0f} MB · caption {len(caption)} chars")
    if a.dry_run:
        print("dry run: nothing uploaded")
        return
    if not a.yes_publish:
        raise SystemExit("refusing to publish without --yes-publish (Gate 5: Satyam's explicit 'publish')")
    s = load()
    tok, uid = s["access_token"], s["ig_user_id"]
    c = call("POST", f"{GRAPH}/{VERSION}/{uid}/media", {"media_type": "REELS", "upload_type": "resumable", "caption": caption,
                                                        "share_to_feed": "true", "access_token": tok})
    cid = c["id"]
    print(f"container {cid}; uploading…")
    call("POST", f"{RUPLOAD}/{VERSION}/{cid}", headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)},
         body=video.read_bytes())
    for _ in range(90):                       # up to ~15 min of processing
        st = call("GET", f"{GRAPH}/{VERSION}/{cid}", {"fields": "status_code,status", "access_token": tok})
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram could not process the video: {st}")
        time.sleep(10)
    else:
        raise SystemExit("still processing after 15 min; container id saved below, publish later")
    pub = call("POST", f"{GRAPH}/{VERSION}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    info = call("GET", f"{GRAPH}/{VERSION}/{pub['id']}", {"fields": "permalink,media_product_type,timestamp", "access_token": tok})
    meta.setdefault("published", {})["instagram"] = {"media_id": pub["id"], "permalink": info.get("permalink"),
                                                     "type": info.get("media_product_type"), "at": info.get("timestamp"),
                                                     "video": video.name}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    print(f"Published: {info.get('permalink')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup").set_defaults(f=cmd_setup)
    sub.add_parser("check").set_defaults(f=cmd_check)
    sub.add_parser("refresh").set_defaults(f=cmd_refresh)
    p = sub.add_parser("publish")
    p.add_argument("episode")
    p.add_argument("--video", default="short-hi.mp4")
    p.add_argument("--yes-publish", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(f=cmd_publish)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
