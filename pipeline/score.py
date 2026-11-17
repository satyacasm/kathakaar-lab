#!/usr/bin/env python3
"""Score each video against the channel's own baseline (Phase 3 input). Standard library only.

  python3 pipeline/score.py [--csv cache/analytics/features_table.csv]

Reads the table written by `features.py table` (one row per video: tags + latest metrics), computes the channel
median of each metric, then gives every video one number: how far above or below a typical Kathakaar video it did.
Phase 3 (the weekly review) groups videos by tag and compares their scores, so "what works" is decided by this one
function. A score of 1.0 means "exactly typical"; 2.0 means "twice as good as typical on what we care about".

Why ratios to the median and not raw numbers: one viral video (Jatayu, 131k views vs ~1k for the rest) would swamp
any average. Medians ignore one outlier; ratios make a 900-view video and a 130k-view video comparable on rates.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
DEFAULT_CSV = LAB / "cache/analytics/features_table.csv"

# Metrics the scorer may use. Rates are per 1,000 views so a small video isn't punished for being small.
METRICS = ["avg_view_pct", "shares_per_1k", "subs_gained_per_1k", "comments_per_1k", "views"]


def ratio(value, median) -> float:
    """value / median, safe for blanks and zero medians (returns 1.0 = 'typical' when there is nothing to compare)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    return v / median if median else 1.0


def score(r: dict[str, float]) -> float:
    """Combine one video's metric ratios into a single score.

    `r` maps each name in METRICS to that video's value divided by the channel median, e.g.
      r["avg_view_pct"] = 1.2    → people watched 20% more of it than of a typical video
      r["shares_per_1k"] = 5.0   → shared 5x as often per view as a typical video
      r["views"] = 0.8           → reach 20% below typical

    TODO(Satyam): decide what the channel optimises for. Return one float where 1.0 = typical.
    Things to weigh:
      - avg_view_pct: did the hook and pacing hold people? (the algorithm's main Shorts signal)
      - shares_per_1k: did it move people enough to send it on? (Jatayu: 110 shares but only 0.9 per 1k views,
        no better than the rest, so per-view rates and reach tell different stories)
      - subs_gained_per_1k: does it build the channel, or just get views?
      - beware tiny denominators: the long video shows 48 shares/1k from just 124 views. Consider ignoring rates
        (ratio 1.0) below some view count, or shrinking them toward typical.
      - comments_per_1k: conversation, and the feedback the loop reads
      - views: raw reach; noisy and mostly a *result* of the others, so a small weight or none
    A weighted geometric mean (multiply r**weight, weights summing to 1) keeps one huge ratio from dominating;
    a weighted sum is simpler but lets a 20x share spike swamp everything. Either is fine: pick deliberately.
    """
    raise NotImplementedError("write score(): see the TODO above")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    a = ap.parse_args()
    rows = list(csv.DictReader(a.csv.open(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"no rows in {a.csv}: run `python3 pipeline/features.py table` first")
    med = {}
    for m in METRICS:
        vals = [float(x[m]) for x in rows if x.get(m) not in (None, "")]
        med[m] = statistics.median(vals) if vals else 0.0
    scored = []
    for x in rows:
        r = {m: ratio(x.get(m), med[m]) for m in METRICS}
        scored.append((score(r), x))
    print("medians: " + ", ".join(f"{m}={v:g}" for m, v in med.items()))
    for s, x in sorted(scored, key=lambda t: -t[0]):
        print(f"{s:6.2f}  {x.get('video_id', '?'):12}  {x.get('title', '')[:70]}")


if __name__ == "__main__":
    main()
