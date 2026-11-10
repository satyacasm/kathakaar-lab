#!/usr/bin/env python3
"""Download the source library listed in sources/manifest.json into sources/texts/<key>.txt.

Project Gutenberg: plain UTF-8 text, licence header/footer stripped. archive.org: the scan's OCR text (_djvu.txt).
Writes sources/INDEX.md (what each file is, translator, year, origin URL, size, SHA-256). Re-running skips files
already present; pass --force to re-download. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SRC = LAB / "sources"
UA = {"User-Agent": "kathakaar-research/1.0 (personal study; contact via archive.org account)"}


def get(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - retry any network error, then give up loudly
            if attempt == 3:
                raise SystemExit(f"failed: {url}: {e}")
            time.sleep(5 * (attempt + 1))
    raise AssertionError


def gutenberg(i: int) -> tuple[str, str]:
    url = f"https://www.gutenberg.org/cache/epub/{i}/pg{i}.txt"
    t = get(url).decode("utf-8", errors="replace")
    a = t.find("*** START OF")
    b = t.find("*** END OF")
    if a != -1:
        t = t[t.find("\n", a) + 1:]
    if b != -1:
        t = t[: t.find("*** END OF")]
    return t, url


def archive(ident: str) -> tuple[str, str]:
    meta = json.loads(get(f"https://archive.org/metadata/{ident}"))
    # the whole-book OCR is the largest _djvu.txt; some items also carry one small file per page
    txt = sorted((f for f in meta.get("files", []) if f["name"].endswith("_djvu.txt")), key=lambda f: -int(f.get("size", 0)))
    if not txt:
        raise SystemExit(f"no OCR text in archive.org item {ident}")
    url = f"https://archive.org/download/{ident}/{urllib.request.quote(txt[0]['name'])}"
    return get(url).decode("utf-8", errors="replace"), url


def main():
    force = "--force" in sys.argv
    man = json.loads((SRC / "manifest.json").read_text())
    (SRC / "texts").mkdir(exist_ok=True)
    rows = ["# Source library", "", "Translations for verifying stories, stored locally so research needs no network. Search with `pipeline/sources_search.py`.",
            "OCR texts (from scans) are noisy: confirm any quotation against the scan before using it.", "",
            "| Key | Work | Part | Translator | Year | Kind | Use | Size | SHA-256 (first 12) | Origin |", "|---|---|---|---|---|---|---|---|---|---|"]
    for t in man["texts"]:
        out = SRC / "texts" / f"{t['key']}.txt"
        if force or not out.exists():
            text, url = gutenberg(t["id"]) if t["source"] == "gutenberg" else archive(t["id"])
            out.write_text(text)
            t["url"] = url
            print(f"fetched {t['key']}: {len(text) / 1e6:.1f} MB")
            time.sleep(2)
        else:
            t["url"] = (f"https://www.gutenberg.org/ebooks/{t['id']}" if t["source"] == "gutenberg"
                        else f"https://archive.org/details/{t['id']}")
        data = out.read_bytes()
        kind = "clean text" if t["source"] == "gutenberg" else "OCR"
        rows.append(f"| {t['key']} | {t['work']} | {t['part']} | {t['translator']} | {t['year']} | {kind} | "
                    f"{len(data) / 1e6:.1f} MB | {hashlib.sha256(data).hexdigest()[:12]} | {t['url']} |")
    if man.get("gaps"):
        rows += ["", "## Known gaps"] + [f"- {g}" for g in man["gaps"]]
    (SRC / "INDEX.md").write_text("\n".join(rows) + "\n")
    print(f"index: {SRC / 'INDEX.md'}")


if __name__ == "__main__":
    main()
