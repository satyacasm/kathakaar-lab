#!/usr/bin/env python3
"""Publish an episode's Reel to the Kathakaar Instagram account, and read its insights and comments.

Two Meta routes are supported; `setup` detects which from the token:
  - Instagram Login: token starts "IG", API graph.instagram.com, 60-day token renewed by `refresh`.
  - Unified Login (Meta's recommended setup since 2026; also older Facebook Login): token starts "EAA" (a "Business
    Integration System User Access Token"), API graph.facebook.com. The Instagram account comes from
    GET /me/assigned_instagram_accounts (no Facebook Page needed); falls back to a Page's linked account.
    Permissions: instagram_basic, instagram_content_publish, instagram_manage_insights, instagram_manage_comments.
    Expiry is chosen in the app's login configuration; `refresh` is a no-op.

Standard library only. Credentials live in ~/kathakaar-lab/secrets/instagram.json (chmod 600) and are never printed.

  setup                      ask (hidden input) for the token; Instagram-login: optionally the app secret to get a
                             60-day token; system user: pick the Page whose linked Instagram account to use. Save.
                             Run it in Terminal.app.
  diagnose                   test a token against both APIs without saving anything
  check                      verify the saved token and show the account it posts to, plus days left; test that
                             insights and comments can be read (needed by analytics.py)
  refresh                    renew the 60-day Instagram-login token (once it is 24 h old); no-op for system users
  publish <episode> --yes-publish [--video short-hi.mp4] [--dry-run]
                             upload out/final/<video> as a Reel with the caption in out/package/caption_instagram.txt,
                             wait until Instagram has processed it, publish, and log the result in episode.json.
                             Only after Satyam said "publish" for this episode (Gate 5).

Flow (Meta docs, same on both routes): POST <graph>/<ver>/<ig-user-id>/media (media_type=REELS, upload_type=resumable)
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
GRAPH = "https://graph.instagram.com"           # Instagram-login route
FB_GRAPH = "https://graph.facebook.com"         # Facebook-login / system-user route
FB_NEEDED = ["instagram_basic", "instagram_content_publish", "instagram_manage_insights", "instagram_manage_comments"]
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


def base(s: dict) -> str:
    """API host for the saved credentials' route."""
    return FB_GRAPH if s.get("api") == "facebook" else GRAPH


def days_left(s: dict) -> str:
    if not s.get("expires_at"):
        return "per app login configuration" if s.get("api") == "facebook" else "unknown"
    return f"{(s['expires_at'] - time.time()) / 86400:.0f}"


def cmd_setup(_):
    raw = getpass.getpass("Paste the access token from the app dashboard (hidden): ")
    token = "".join(raw.split())                     # drop any spaces/line breaks picked up while copying
    REDACT.append(token)
    # Safe hint for spotting paste mistakes: length and first 4 characters only (Instagram tokens start "IG").
    print(f"read a token of {len(token)} characters starting '{token[:4]}'")
    if token.startswith("EAA"):
        return setup_facebook(token)
    if not token.startswith("IG"):
        print("  warning: Instagram-login tokens start with 'IG'. If this isn't the token from 'Generate token', "
              "press Ctrl-C and copy it again.")
    try:                                              # 1) is the token valid at all?
        me = call("GET", f"{GRAPH}/{VERSION}/me", {"fields": "user_id,username,account_type", "access_token": token})
    except SystemExit as e:
        raise SystemExit(f"{e}\nThe token itself was rejected: copy it again from 'Generate token' and rerun setup.")
    s = {"access_token": token, "expires_at": None}
    secret = "".join(getpass.getpass("Paste the Instagram app secret to get a 60-day token (hidden, Enter to skip): ").split())
    REDACT.append(secret)
    if secret:                                        # 2) try to swap a short-lived token for a 60-day one
        try:
            r = call("GET", f"{GRAPH}/access_token", {"grant_type": "ig_exchange_token", "client_secret": secret,
                                                       "access_token": token})
            s["access_token"] = r["access_token"]
            s["expires_at"] = time.time() + int(r.get("expires_in", 0))
            REDACT.append(s["access_token"])
            print("exchanged for a 60-day token")
        except SystemExit:
            # Tokens made by the dashboard's "Generate token" are usually already long-lived and can't be exchanged.
            s["expires_at"] = time.time() + 60 * 86400
            s["expiry_assumed"] = True
            print("exchange not needed (token from the dashboard is already long-lived); assuming 60 days. "
                  "`refresh` works once it is 24 h old and then records the real expiry.")
    s.update(ig_user_id=me["user_id"], username=me.get("username"), account_type=me.get("account_type"),
             saved_at=datetime.now(timezone.utc).isoformat())
    save(s)
    print(f"Saved. Posting account: @{s['username']} ({s['account_type']}); token days left: {days_left(s)}")


def setup_facebook(token: str):
    """Unified-login / system-user token: check permissions, find the assigned Instagram account, save."""
    try:
        who = call("GET", f"{FB_GRAPH}/{VERSION}/me", {"fields": "id,name", "access_token": token})
    except SystemExit as e:
        raise SystemExit(f"{e}\nThe token itself was rejected: generate it again in Business settings and rerun setup.")
    print(f"Facebook-login token for: {who.get('name')}")
    perms = call("GET", f"{FB_GRAPH}/{VERSION}/me/permissions", {"access_token": token}).get("data", [])
    granted = {p["permission"] for p in perms if p.get("status") == "granted"}
    missing = [p for p in FB_NEEDED if p not in granted]
    if missing:
        print("  missing permissions: " + ", ".join(missing) + ". Add them in the app: Use cases → Manage messaging & "
              "content on Instagram → Customize → API setup with Unified login → your configuration → Edit permissions; "
              "then Generate token again (PUBLISHING_SETUP.md, section B2).")
    # Unified Login: accounts assigned to the business integration system user (no Facebook Page needed).
    cands = []
    try:
        for a in call("GET", f"{FB_GRAPH}/{VERSION}/me/assigned_instagram_accounts",
                      {"fields": "id,username", "access_token": token}).get("data", []):
            cands.append({"ig": a, "page_id": None, "page_name": None})
    except SystemExit as e:
        print(f"  assigned_instagram_accounts not available ({str(e)[:120]}); trying linked Pages")
    if not cands:  # older Facebook Login setup: Instagram account linked to a Facebook Page
        try:
            for pg in call("GET", f"{FB_GRAPH}/{VERSION}/me/accounts",
                           {"fields": "id,name,instagram_business_account{id,username}", "access_token": token}).get("data", []):
                if pg.get("instagram_business_account"):
                    cands.append({"ig": pg["instagram_business_account"], "page_id": pg["id"], "page_name": pg["name"]})
        except SystemExit:
            pass
    if not cands:
        raise SystemExit("No Instagram account is assigned to this token. In the app: API setup with Unified login → "
                         "Generate access tokens → Add account (accept the Instagram Tester invite), then Generate token "
                         "again (PUBLISHING_SETUP.md, section B2).")
    if len(cands) > 1:
        for i, c in enumerate(cands, 1):
            print(f"  {i}. @{c['ig'].get('username')}" + (f" (Page {c['page_name']})" if c["page_name"] else ""))
        pick = cands[int(input("Which one? number: ")) - 1]
    else:
        pick = cands[0]
    ig = pick["ig"]
    s = {"api": "facebook", "access_token": token, "expires_at": None, "page_id": pick["page_id"], "page_name": pick["page_name"],
         "ig_user_id": ig["id"], "username": ig.get("username"), "account_type": "BUSINESS_OR_CREATOR",
         "system_user": who.get("name"), "missing_permissions": missing,
         "saved_at": datetime.now(timezone.utc).isoformat()}
    save(s)
    print(f"Saved. Posting account: @{s['username']} (unified login); token expiry: {days_left(s)}"
          + ("" if not missing else "  (fix the missing permissions above before relying on it)"))


def probe(label: str, permission: str, method: str, url: str, params: dict) -> bool:
    """Try one read call; report OK or which dashboard permission is missing. Never exits."""
    try:
        call(method, url, params)
        print(f"{label}: OK")
        return True
    except SystemExit as e:
        print(f"{label}: FAILED. Add `{permission}` under the app's permissions, generate a new token, and run setup "
              f"again\n  {str(e)[:300]}")
        return False


def cmd_check(_):
    s = load()
    tok, g, fb = s["access_token"], base(s), s.get("api") == "facebook"
    if fb:
        me = call("GET", f"{g}/{VERSION}/{s['ig_user_id']}", {"fields": "id,username", "access_token": tok})
        print(f"OK: @{me.get('username')} (unified login, {s.get('system_user')}); "
              f"token expiry: {days_left(s)}")
    else:
        me = call("GET", f"{g}/{VERSION}/me", {"fields": "user_id,username,account_type", "access_token": tok})
        print(f"OK: @{me.get('username')} ({me.get('account_type')}), user id matches: {me['user_id'] == s['ig_user_id']}; "
              f"token days left: {days_left(s)}")
    p_ins = "instagram_manage_insights" if fb else "instagram_business_manage_insights"
    p_com = "instagram_manage_comments" if fb else "instagram_business_manage_comments"
    ok = probe("insights", p_ins, "GET", f"{g}/{VERSION}/{s['ig_user_id']}/insights",
               {"metric": "reach", "period": "day", "access_token": tok})
    media = call("GET", f"{g}/{VERSION}/{s['ig_user_id']}/media", {"fields": "id", "limit": 1, "access_token": tok})
    if media.get("data"):
        ok &= probe("comments", p_com, "GET",
                    f"{g}/{VERSION}/{media['data'][0]['id']}/comments", {"fields": "id", "access_token": tok})
    else:
        print("comments: not tested yet (no posts on the account)")
    if not ok:
        raise SystemExit(1)


def cmd_refresh(_):
    s = load()
    if s.get("api") == "facebook":
        print("Unified-login token: no refresh here (its expiry is set in the app's login configuration).")
        return
    r = call("GET", f"{GRAPH}/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": s["access_token"]})
    s["access_token"], s["expires_at"] = r["access_token"], time.time() + int(r.get("expires_in", 0))
    s.pop("expiry_assumed", None)
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
    tok, uid, g = s["access_token"], s["ig_user_id"], base(s)
    c = call("POST", f"{g}/{VERSION}/{uid}/media", {"media_type": "REELS", "upload_type": "resumable", "caption": caption,
                                                        "share_to_feed": "true", "access_token": tok})
    cid = c["id"]
    print(f"container {cid}; uploading…")
    call("POST", f"{RUPLOAD}/{VERSION}/{cid}", headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)},
         body=video.read_bytes())
    for _ in range(90):                       # up to ~15 min of processing
        st = call("GET", f"{g}/{VERSION}/{cid}", {"fields": "status_code,status", "access_token": tok})
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram could not process the video: {st}")
        time.sleep(10)
    else:
        raise SystemExit("still processing after 15 min; container id saved below, publish later")
    pub = call("POST", f"{g}/{VERSION}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    info = call("GET", f"{g}/{VERSION}/{pub['id']}", {"fields": "permalink,media_product_type,timestamp", "access_token": tok})
    meta.setdefault("published", {})["instagram"] = {"media_id": pub["id"], "permalink": info.get("permalink"),
                                                     "type": info.get("media_product_type"), "at": info.get("timestamp"),
                                                     "video": video.name}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    print(f"Published: {info.get('permalink')}")


def cmd_diagnose(_):
    """Try a pasted token against both Meta APIs and report what works. Saves nothing; never prints the token."""
    token = "".join(getpass.getpass("Paste the token to test (hidden): ").split())
    REDACT.append(token)
    print(f"token: {len(token)} characters, starts '{token[:3]}'")
    fb = "https://graph.facebook.com"

    def tryit(label, url, params):
        try:
            r = call("GET", url, dict(params, access_token=token))
            print(f"  {label}: OK -> {json.dumps(r, ensure_ascii=False)[:400]}")
            return r
        except SystemExit as e:
            print(f"  {label}: FAILED -> {str(e)[:250]}")
            return None

    print("Instagram-login API (graph.instagram.com):")
    tryit("me", f"{GRAPH}/{VERSION}/me", {"fields": "user_id,username,account_type"})
    print("Facebook-login API (graph.facebook.com):")
    tryit("me", f"{fb}/{VERSION}/me", {"fields": "id,name"})
    tryit("permissions", f"{fb}/{VERSION}/me/permissions", {})
    tryit("assigned Instagram accounts (unified login)", f"{fb}/{VERSION}/me/assigned_instagram_accounts",
          {"fields": "id,username"})
    tryit("pages + linked Instagram", f"{fb}/{VERSION}/me/accounts",
          {"fields": "name,instagram_business_account{id,username}"})
    print("Paste this output to Claude (it contains no token).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup").set_defaults(f=cmd_setup)
    sub.add_parser("check").set_defaults(f=cmd_check)
    sub.add_parser("diagnose").set_defaults(f=cmd_diagnose)
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
