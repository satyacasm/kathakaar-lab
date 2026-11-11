"""Credit ledger (episodes/credits.json) and caps (config.json).

The ledger lives next to the episode folders: <ep_dir>/../credits.json. Higgsfield is never called from here;
this only records and checks numbers.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from reel import shots as S


def ledger_path(ep_dir) -> Path:
    return Path(ep_dir).resolve().parent / "credits.json"


def load_ledger(ep_dir) -> dict:
    p = ledger_path(ep_dir)
    if not p.exists():
        return {"entries": []}
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise S.ReelError(f"{p}: ledger is not valid JSON ({e}); fix or restore it before spending credits")
    d.setdefault("entries", [])
    return d


def _save(ep_dir, d):
    p = ledger_path(ep_dir)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=1) + "\n")
    os.replace(tmp, p)


def month_spent(ledger, month: str) -> float:
    """month = 'YYYY-MM'"""
    return sum(e.get("credits", 0) for e in ledger["entries"] if str(e.get("date", "")).startswith(month))


def episode_spent(ledger, slug: str) -> float:
    return sum(e.get("credits", 0) for e in ledger["entries"] if e.get("episode") == slug)


def logged(ledger, slug: str) -> set:
    return {e.get("n") for e in ledger["entries"] if e.get("episode") == slug}


def pending_hero(ep_dir, shots, ledger=None):
    """Hero shots that still need buying: no file in out/hero_raw/ and no ledger entry for this episode."""
    ep = Path(ep_dir)
    ledger = ledger or load_ledger(ep)
    done = logged(ledger, ep.name)
    return [s for s in shots["shots"] if s.get("source") == "hero"
            and not (ep / f"out/hero_raw/c{s['n']:02d}.mp4").exists() and s["n"] not in done]


def summary(ep_dir, today=None) -> dict:
    """Numbers for `check` and `hero-plan`."""
    ep = Path(ep_dir)
    cfg = S.load_config()
    shots = S.load_shots(ep)
    ledger = load_ledger(ep)
    month = (today or dt.date.today()).strftime("%Y-%m")
    pend = pending_hero(ep, shots, ledger)           # still to make: no raw file, no ledger entry
    done = logged(ledger, ep.name)
    unlogged = [s for s in shots["shots"] if s.get("source") == "hero" and s["n"] not in done]
    est = {s["n"]: S.hero_cost(s, cfg) for s in unlogged}
    # budget view: every hero shot without a ledger entry counts, even if its raw file already exists
    pend_total = sum(v for v in est.values() if v is not None)
    ep_spent = episode_spent(ledger, ep.name)
    m_spent = month_spent(ledger, month)
    all_hero = [s for s in shots["shots"] if s.get("source") == "hero"]
    return dict(cfg=cfg, pending=pend, unlogged=len(unlogged), est=est, pending_total=pend_total, episode_spent=ep_spent,
                month_spent=m_spent, month=month,
                reel_total=ep_spent + pend_total, month_total=m_spent + pend_total,
                hero_seconds=sum(s["hero"]["duration"] for s in all_hero if isinstance(s.get("hero"), dict)
                                 and isinstance(s["hero"].get("duration"), (int, float))),
                hero_count=len(all_hero),
                over_reel=ep_spent + pend_total > cfg["credits_per_reel"] + 1e-9,
                over_month=m_spent + pend_total > cfg["credits_per_month"] + 1e-9)


def cap_problems(sm) -> list[str]:
    c = sm["cfg"]
    out = []
    if sm["over_reel"]:
        out.append(f"hero plan is over the per-reel cap: {sm['reel_total']:g} credits "
                   f"({sm['episode_spent']:g} already spent + {sm['pending_total']:g} planned) > {c['credits_per_reel']}")
    if sm["over_month"]:
        out.append(f"hero plan is over the monthly cap: {sm['month_total']:g} credits "
                   f"({sm['month_spent']:g} spent in {sm['month']} + {sm['pending_total']:g} planned) > "
                   f"{c['credits_per_month']}")
    return out


def hero_plan(ep_dir) -> int:
    """Print the plan; return the exit code (1 if a cap would be exceeded or a shot cannot be priced)."""
    ep = Path(ep_dir)
    rep = S.validate(ep)
    if rep.errors:
        for m in rep.errors:
            print("error:", m)
        print("fix these first (reel.py <ep> check)")
        return 1
    sm = summary(ep)
    shots = S.load_shots(ep)
    if not sm["pending"]:
        print("no hero shots to buy (all have a file in out/hero_raw/ or a ledger entry)")
        return 0
    print(f"Hero plan for {ep.name}:")
    for s in sm["pending"]:
        h = s["hero"]
        still = f"out/keyframes/s{s['n']:02d}.png"
        end = f"out/keyframes/s{s['n']:02d}_{h['end_pose']}.png" if h.get("end_pose") else None
        print(f"\n  shot {s['n']}  ->  save to out/hero_raw/c{s['n']:02d}.mp4")
        print(f"    start frame : {still}{'' if (ep / still).exists() else '  (NOT MADE YET: run the stills stage)'}")
        if end:
            print(f"    end frame   : {end}{'' if (ep / end).exists() else '  (NOT MADE YET)'}")
        print(f"    model       : {h['model']}  {h['resolution']}  {h['duration']} s")
        print(f"    prompt      : {h['prompt']}")
        print(f"    estimate    : {sm['est'][s['n']]:g} credits (confirm with the quote before generating)")
    c = sm["cfg"]
    print(f"\n  planned (all hero shots not yet in the ledger): {sm['pending_total']:g} credits")
    print(f"  this reel          : {sm['reel_total']:g} / {c['credits_per_reel']}")
    print(f"  month {sm['month']}    : {sm['month_total']:g} / {c['credits_per_month']}")
    probs = cap_problems(sm)
    for m in probs:
        print("REFUSED:", m)
    return 1 if probs else 0


def hero_log(ep_dir, n, credits, job=None, model=None, seconds=None, date=None) -> None:
    ep = Path(ep_dir).resolve()
    shots = S.load_shots(ep)
    shot = S.shot_by_n(shots).get(n)
    if not shot or shot.get("source") != "hero":
        raise S.ReelError(f"shot {n} is not a hero shot in shots.json")
    if credits < 0:
        raise S.ReelError("--credits must be >= 0")
    h = shot["hero"]
    ledger = load_ledger(ep)
    if n in logged(ledger, ep.name):
        raise S.ReelError(f"shot {n} already has a ledger entry for {ep.name}; edit {ledger_path(ep)} by hand to correct it")
    cfg = S.load_config()
    entry = {"date": date or dt.date.today().isoformat(), "episode": ep.name, "n": n,
             "model": model or h["model"], "seconds": seconds if seconds is not None else h["duration"],
             "credits": float(credits), "job": job or ""}
    new_month = str(entry["date"])[:7]
    total_ep = episode_spent(ledger, ep.name) + credits
    total_m = month_spent(ledger, new_month) + credits
    ledger["entries"].append(entry)
    _save(ep, ledger)
    print(f"logged: shot {n}, {credits:g} credits, job {job or '-'} -> {ledger_path(ep)}")
    print(f"this reel: {total_ep:g} / {cfg['credits_per_reel']}   month {new_month}: {total_m:g} / {cfg['credits_per_month']}")
    if total_ep > cfg["credits_per_reel"]:
        print("warning: this reel is now over its credit cap")
    if total_m > cfg["credits_per_month"]:
        print("warning: the month is now over its credit cap")
