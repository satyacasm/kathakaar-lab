#!/usr/bin/env python3
"""Search the local source library (sources/texts) and cite where each passage sits. Offline; standard library only.

  sources_search.py markandeya banyan child            all terms within a window of lines (default 14)
  sources_search.py "markandeya|markandya" flood --work Mahabharata --window 30
  sources_search.py --show mbh1:21876 --context 40     print a passage to read and quote
  sources_search.py --list                             the library, with the 'use' rule per text

Matching ignores case and diacritics (Márkandeya = markandeya); "a|b" accepts either spelling, and terms are expanded
with the variants in sources/variants.json (banyan → banian, nyagrodha; child → boy, infant …) unless --exact.
Each hit is cited as: work · part · book/parva › section/canto/chapter · line, with the 'use' rule:
'quote' texts are public domain; 'verify only' texts may be checked against but not quoted on screen.
OCR texts (scans) contain misreadings: confirm a quotation against the scan before using it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SRC = LAB / "sources"

BOOK_RE = re.compile(r"^(BOOK\s+[\dIVXLC]+\b|Book\s+[IVXLC]+\b|[A-Z][A-Za-z\-]+\s+PARVA\b|[A-Z][a-z\-]+\s+Parva\b|PART\s+[IVXLC\d]+\b"
                     r"|SKANDHA\s+\w+|Skandha\s+\w+|[A-Z][A-Za-z]+\s+KANDA\b|[A-Z][a-z]+\s+Kanda\b)")
SEC_RE = re.compile(r"^(SECTION|CANTO|Canto|CHAPTER|Chapter|ADHYAYA|Adhyaya|LECTURE|KHANDA|Khanda|VALLI|Valli)\.?\s+[\dIVXLCl]+\b")


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def variants() -> dict[str, list[str]]:
    groups = json.loads((SRC / "variants.json").read_text())["groups"] if (SRC / "variants.json").exists() else []
    out: dict[str, list[str]] = {}
    for g in groups:
        g = [fold(x) for x in g]
        for x in g:
            out.setdefault(x, [])
            out[x] += [y for y in g if y not in out[x]]
    return out


def expand(term: str, var: dict[str, list[str]], exact: bool) -> list[str]:
    alts = [fold(a) for a in term.split("|")]
    if not exact:
        alts += [v for a in alts for v in var.get(a, []) if v not in alts]
    return alts


def library() -> list[dict]:
    man = json.loads((SRC / "manifest.json").read_text())
    return [t for t in man["texts"] if (SRC / "texts" / f"{t['key']}.txt").exists()]


def load(t: dict) -> tuple[list[str], list[str], list[str]]:
    """Lines, folded lines, and the citation (book › section) in force at each line."""
    lines = (SRC / "texts" / f"{t['key']}.txt").read_text(errors="replace").splitlines()
    book = sec = ""
    cites = []
    for ln in lines:
        s = ln.strip()
        if 0 < len(s) < 60:
            m = BOOK_RE.match(s)
            if m:
                book, sec = m.group(0).strip(), ""
            m = SEC_RE.match(s)
            if m:
                sec = m.group(0).strip()
        cites.append(" › ".join(x for x in (book, sec) if x))
    return lines, [fold(x) for x in lines], cites


def search(terms: list[str], works: str | None, window: int, per_source: int, exact: bool) -> None:
    var = variants()
    alts = [expand(t, var, exact) for t in terms]
    print("searching: " + " AND ".join("(" + " | ".join(g) + ")" for g in alts))
    total = 0
    for t in library():
        if works and fold(works) not in fold(t["work"]):
            continue
        lines, folded, cites = load(t)
        hits, i, n = [], 0, len(lines)
        while i < n:
            if any(a in folded[i] for a in alts[0]):
                lo, hi = max(0, i - window // 2), min(n, i + window // 2 + 1)
                block = " ".join(folded[lo:hi])
                if all(any(a in block for a in group) for group in alts):
                    score = sum(block.count(a) for group in alts for a in group)
                    hits.append((score, i, lo, hi))
                    i = hi
                    continue
            i += 1
        if not hits:
            continue
        total += len(hits)
        print(f"\n## {t['work']} · {t['part']} · {t['translator']} [{t['key']}] · use: {t.get('use', 'quote')} · {len(hits)} hit(s)")
        for score, i, lo, hi in sorted(hits, key=lambda h: -h[0])[:per_source]:
            snippet = " ".join(x.strip() for x in lines[max(lo, i - 3): min(hi, i + 5)] if x.strip())
            for group in alts:
                for a in group:
                    snippet = re.sub(f"({re.escape(a)})", r"«\1»", snippet, flags=re.I) if a.isascii() else snippet
            print(f"- {cites[i] or '(no heading found)'} · line {i + 1} · show: --show {t['key']}:{i + 1}")
            print(f"  {snippet[:420]}{'…' if len(snippet) > 420 else ''}")
    print(f"\n{total} hit(s) in total." if total else "No hits. Try other spellings (a|b), fewer terms or a wider --window.")


def show(spec: str, context: int) -> None:
    key, line = spec.split(":")
    t = next((x for x in library() if x["key"] == key), None)
    if not t:
        raise SystemExit(f"unknown source key: {key} (see --list)")
    lines, _, cites = load(t)
    i = int(line) - 1
    lo, hi = max(0, i - context // 2), min(len(lines), i + context // 2)
    print(f"{t['work']} · {t['part']} · {t['translator']} ({t['year']}) · use: {t.get('use', 'quote')}")
    print(f"Citation: {cites[i] or '(no heading found)'} · lines {lo + 1}-{hi}\n")
    for k in range(lo, hi):
        print(f"{k + 1:>7}{'>' if k == i else ' '} {lines[k]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="*")
    ap.add_argument("--work", help="limit to works whose name contains this, e.g. Mahabharata, Purana, Ramayana")
    ap.add_argument("--window", type=int, default=14, help="lines within which all terms must appear")
    ap.add_argument("--per-source", type=int, default=6)
    ap.add_argument("--show", help="key:line to print a passage")
    ap.add_argument("--context", type=int, default=30)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--exact", action="store_true", help="don't expand spelling variants (sources/variants.json)")
    a = ap.parse_args()
    if a.list:
        for t in library():
            print(f"{t['key']:<26} {t['work']:<22} {t['part'][:48]:<48} use: {t.get('use', 'quote')}")
    elif a.show:
        show(a.show, a.context)
    elif a.terms:
        search(a.terms, a.work, a.window, a.per_source, a.exact)
    else:
        ap.print_help()


if __name__ == "__main__":
    sys.exit(main())
