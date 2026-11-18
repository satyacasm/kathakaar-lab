#!/usr/bin/env python3
"""Experiment plan for the content loop: which format / audio / slot each upcoming video uses. Standard library only.

  plan.py new-fortnight [--start DATE]   28 rows that bring every (format, audio) cell to n>=3 within the budget
  plan.py next-week [--start DATE]       14 rows: 10 from the best-scoring cells, 4 exploratory (needs analytics)
  plan.py show                           print the plan file
  plan.py next [--take VIDEO_ID]         print the earliest row without an id; --take records the id on it

Plan file: ideas/experiment_plan.md (git-ignored), or --path / $PLAN_PATH. Markdown table, one row per video:
day | slot | format | audio | topic_source | locked | id.  Rows marked locked (or already holding an id) survive
a regeneration. Budget wins over n>=3 (cells that do not fit are carried into the next fortnight).
"""
import argparse, os, statistics, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

for _p in (Path(__file__).resolve().parent, Path(__file__).resolve().parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

LAB = Path(__file__).resolve().parents[2]
PLAN_PATH = LAB / "ideas/experiment_plan.md"
TZ = ZoneInfo("Asia/Kolkata")

FORMATS = ("music", "narrated", "claim", "shloka", "dialogue")
AUDIO = {"music": ("popular", "library", "original"), "shloka": ("library", "original"),
         "dialogue": ("popular",), "narrated": ("bed",), "claim": ("bed",)}
CREDIT_EST = {"music": 10, "shloka": 4, "dialogue": 6, "narrated": 0, "claim": 0}
ORIGINAL_EXTRA = 3
SLOTS = ("12:30", "19:30")
FREE = ("narrated", "claim")
CELLS = [(f, a) for f in FORMATS for a in AUDIO[f]]
COUNTED = ("preview_ready", "approved", "posted")
MIN_N = 3
FORTNIGHT_ROWS = 28
WEEK_ROWS = 14
EXPLOIT_ROWS = 10
BASE_TOPICS = ("trend_gap", "festival", "comment_request", "untold_detail")
EXTRA_TOPIC = {"music": "song_story", "dialogue": "dialogue_catalogue"}
TOPICS = BASE_TOPICS + tuple(EXTRA_TOPIC.values())
HEADER = ("day", "slot", "format", "audio", "topic_source", "locked", "id")


def cell_cost(cell) -> float:
    f, a = cell
    return CREDIT_EST[f] + (ORIGINAL_EXTRA if a == "original" and CREDIT_EST[f] else 0)


def row_cost(row) -> float:
    return cell_cost((row["format"], row["audio"]))


def existing_counts(existing) -> dict:
    n = {c: 0 for c in CELLS}
    for r in existing or []:
        if r.get("status") not in COUNTED:
            continue
        c = r.get("cell") or {}
        key = (c.get("format"), c.get("audio"))
        if key in n:
            n[key] += 1
    return n


class _Builder:
    """Turns a sequence of cells into rows: positional day/slot, rotating topic_source per format."""

    def __init__(self, start: date):
        self.start, self.rows, self.topic_n = start, [], {}

    def slot_at(self, i):
        return SLOTS[i % 2]

    def add(self, cell):
        i = len(self.rows)
        f, a = cell
        topics = BASE_TOPICS + ((EXTRA_TOPIC[f],) if f in EXTRA_TOPIC else ())
        k = self.topic_n.get(f, 0)
        self.topic_n[f] = k + 1
        self.rows.append({"day": (self.start + timedelta(days=i // 2)).isoformat(), "slot": self.slot_at(i),
                          "format": f, "audio": a, "topic_source": topics[k % len(topics)],
                          "locked": False, "id": ""})


def fortnight(start: date, existing: list, credits_left: float) -> list:
    """28 rows, greedy: the cell with the largest deficit to n>=3 whose format differs from the previous row and
    whose cost fits the remaining budget. Once nothing affordable is short, fill with the least-covered cells."""
    n = existing_counts(existing)
    left = credits_left
    b = _Builder(start)
    last_slot = {}
    prev = None
    for i in range(FORTNIGHT_ROWS):
        slot = b.slot_at(i)
        # credits that the cells still short of n>=3 will need: surplus rows may not eat into them
        reserve = sum((MIN_N - n[c]) * cell_cost(c) for c in CELLS if n[c] < MIN_N)
        short = [c for c in CELLS if c[0] != prev and n[c] < MIN_N and cell_cost(c) <= left]
        if short:
            key = lambda c: (last_slot.get(c[0]) == slot, -(MIN_N - n[c]), cell_cost(c), CELLS.index(c))
            pool = short
        else:
            pool = [c for c in CELLS if c[0] != prev and (cell_cost(c) <= left - reserve or cell_cost(c) == 0)]
            key = lambda c: (last_slot.get(c[0]) == slot, n[c], cell_cost(c), CELLS.index(c))
        cell = min(pool, key=key)
        b.add(cell)
        n[cell] += 1
        left -= cell_cost(cell)
        last_slot[cell[0]] = slot
        prev = cell[0]
    return _alternate_slots(b.rows)


def _flips(rows) -> int:
    """Number of times a format's next appearance uses the other slot (higher = better alternation)."""
    last, n = {}, 0
    for r in rows:
        if r["format"] in last and last[r["format"]] != r["slot"]:
            n += 1
        last[r["format"]] = r["slot"]
    return n


def _swap_day(rows, d):
    a, b = rows[2 * d], rows[2 * d + 1]
    a["slot"], b["slot"] = b["slot"], a["slot"]
    rows[2 * d], rows[2 * d + 1] = b, a


def _ok_adjacent(rows) -> bool:
    return all(x["format"] != y["format"] for x, y in zip(rows, rows[1:]))


def _alternate_slots(rows) -> list:
    """Swap the two videos of a day between slots when that gives formats more slot alternation and keeps
    the no-back-to-back rule intact. Rows stay sorted by (day, slot)."""
    improved = True
    while improved:
        improved = False
        for d in range(len(rows) // 2):
            before, was_ok = _flips(rows), _ok_adjacent(rows)
            _swap_day(rows, d)
            if _flips(rows) > before and (_ok_adjacent(rows) or not was_ok):
                improved = True
            else:
                _swap_day(rows, d)
    return rows


def _allocate(scores: list, total: int) -> list:
    """Largest-remainder split of `total` rows over cells in proportion to score (each gets at least 1 when possible)."""
    k = len(scores)
    if k == 0:
        return []
    s = sum(max(x, 0) for x in scores) or 1.0
    base = [1 if total >= k else 0] * k
    rest = total - sum(base)
    shares = [max(x, 0) / s * rest for x in scores]
    out = [b + int(sh) for b, sh in zip(base, shares)]
    order = sorted(range(k), key=lambda i: -(shares[i] - int(shares[i])))
    for i in order[: total - sum(out)]:
        out[i] += 1
    return out


def exploit_week(start: date, cell_scores: dict, credits_left: float) -> list:
    """14 rows: 10 from the top-scoring cells in proportion to score, 4 exploratory (untested cells first,
    then the lowest-scoring ones). Over-budget rows are swapped to narrated/claim, costliest first."""
    ranked = sorted(cell_scores, key=lambda c: -cell_scores[c])
    top = ranked[:3]
    picks = []
    for c, k in zip(top, _allocate([cell_scores[c] for c in top], EXPLOIT_ROWS)):
        picks += [c] * k
    explore_pool = [c for c in CELLS if c not in cell_scores] or list(reversed(ranked[3:])) or list(CELLS)
    for i in range(WEEK_ROWS - len(picks)):
        picks.append(explore_pool[i % len(explore_pool)])
    # budget: downgrade the costliest picks to free formats (the less used of narrated/claim)
    total = sum(cell_cost(c) for c in picks)
    for i in sorted(range(len(picks)), key=lambda i: -cell_cost(picks[i])):
        if total <= credits_left:
            break
        total -= cell_cost(picks[i])
        picks[i] = None
    free_n = {f: 0 for f in FREE}
    for c in picks:
        if c and c[0] in free_n:
            free_n[c[0]] += 1
    for i, c in enumerate(picks):
        if c is None:
            f = min(FREE, key=lambda f: free_n[f])
            free_n[f] += 1
            picks[i] = (f, AUDIO[f][0])
    # order: always take from the most frequent format that differs from the previous row (no adjacent repeats
    # whenever that is possible)
    remaining = list(picks)
    ordered, prev = [], None
    while remaining:
        fcount = {}
        for c in remaining:
            fcount[c[0]] = fcount.get(c[0], 0) + 1
        opts = [f for f in fcount if f != prev] or list(fcount)
        f = max(opts, key=lambda f: (fcount[f], -FORMATS.index(f)))
        pick = next(c for c in remaining if c[0] == f)
        remaining.remove(pick)
        ordered.append(pick)
        prev = f
    b = _Builder(start)
    for c in ordered:
        b.add(c)
    return _alternate_slots(b.rows)


# ---------------------------------------------------------------- file

def _fmt(r):
    return "| " + " | ".join([r["day"], r["slot"], r["format"], r["audio"], r["topic_source"],
                              "yes" if r["locked"] else "no", r.get("id", "")]).rstrip() + " |"


def read(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(HEADER) or cells[0] == HEADER[0] or set(cells[0]) <= set("-: "):
            continue
        d = dict(zip(HEADER, cells))
        d["locked"] = d["locked"].lower() in ("yes", "true", "1", "x")
        rows.append(d)
    return rows


def write(rows: list, path) -> None:
    """Write the table. Rows already in the file that are locked (or hold an id) are kept, replacing generated rows
    at the same day+slot."""
    p = Path(path)
    merged = {(r["day"], r["slot"]): dict(r) for r in rows}
    for r in read(p):
        if r["locked"] or r["id"]:
            merged[(r["day"], r["slot"])] = r
    out = sorted(merged.values(), key=lambda r: (r["day"], r["slot"]))
    lines = ["# Experiment plan", "",
             "Generated by pipeline/loop/plan.py. Mark a row `locked` to keep it across regeneration; the producer fills `id`.",
             "", "| " + " | ".join(HEADER) + " |", "|" + "---|" * len(HEADER)] + [_fmt(r) for r in out]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def next_row(rows: list, queue_records: list):
    """Earliest row without an id (queue_records is accepted for the caller's convenience; the id is the marker)."""
    for r in sorted(rows, key=lambda r: (r["day"], r["slot"])):
        if not r.get("id"):
            return r
    return None


# ---------------------------------------------------------------- CLI

def _today():
    return datetime.now(TZ).date()


def _credits_left(records, today) -> float:
    from reel import budget
    month = today.strftime("%Y-%m")
    return budget.loop_cap(month) - budget.loop_spent(month, {r["id"] for r in records})


def cell_scores_from(records: list, rows: list, scores: dict) -> dict:
    """Median score per (format, audio) cell: loop records (id = episode slug) joined to scored videos."""
    cell_of = {r["id"]: (r["cell"]["format"], r["cell"]["audio"]) for r in records
               if r.get("status") in COUNTED and r.get("cell")}
    by = {}
    for row in rows:
        c = cell_of.get(row.get("episode_slug"))
        if c is not None and row.get("video_id") in scores:
            by.setdefault(c, []).append(scores[row["video_id"]])
    return {c: statistics.median(v) for c, v in by.items()}


def _load_scores(records):
    try:
        import review                                   # lazy: heavy, and needs analytics data
        rows = review.load_rows()
        scores, _, _ = review.score_all(rows)
        return cell_scores_from(records, rows, scores)
    except Exception as e:                              # no data / review cannot load
        print(f"scores unavailable ({type(e).__name__}: {e}); using exploration rows", file=sys.stderr)
        return {}


def _keep_before(path, start: date) -> list:
    return [r for r in read(path) if r["day"] < start.isoformat()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="plan.py")
    ap.add_argument("--path", default=os.environ.get("PLAN_PATH") or str(PLAN_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("new-fortnight", "next-week"):
        sp = sub.add_parser(name)
        sp.add_argument("--start", type=date.fromisoformat)
    sub.add_parser("show")
    sp = sub.add_parser("next")
    sp.add_argument("--take", metavar="VIDEO_ID")
    a = ap.parse_args(argv)
    path = Path(a.path)

    if a.cmd == "show":
        print(path.read_text(encoding="utf-8") if path.exists() else "no plan yet")
        return 0
    if a.cmd == "next":
        import vqueue
        rows = read(path)
        r = next_row(rows, vqueue.load())
        if r is None:
            print("no open rows")
            return 1
        if a.take:
            r["id"] = a.take
            write(rows, path)
        print(" ".join(f"{k}={r[k]}" for k in HEADER if k != "id"))
        return 0

    import vqueue
    records = vqueue.load()
    start = a.start or _today()
    left = _credits_left(records, start)
    if a.cmd == "new-fortnight":
        new = fortnight(start, records, left)
    else:
        cs = _load_scores(records)
        new = exploit_week(start, cs, left) if cs else fortnight(start, records, left)[:WEEK_ROWS]
        if not cs:
            print("no scored cells: wrote exploration rows (fortnight order, first 14)")
    write(_keep_before(path, start) + new, path)
    print(f"wrote {len(new)} rows from {start} ({left:g} credits left) to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
