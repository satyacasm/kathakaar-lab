#!/usr/bin/env python3
"""Music-reel pipeline CLI. See pipeline/REEL_PIPELINE.md.

  pipeline/.venv/bin/python pipeline/reel.py <episode-slug-or-path> <stage> [options]

Stages: check, stills, motion, hero-plan, hero-log, finish, assemble, all.
Stage modules are imported only when their stage runs, so a problem in one never breaks the others.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # pipeline/: `reel` resolves to the package pipeline/reel/

STAGES = ["check", "stills", "motion", "hero-plan", "hero-log", "finish", "assemble", "all"]


def fail(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def resolve_ep(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir() and (p / "script").is_dir():
        return p.resolve()
    ep = LAB / "episodes" / arg.rstrip("/").split("/")[-1]
    if not ep.is_dir():
        fail(f"no such episode: {arg} (looked in {LAB / 'episodes'})")
    return ep


def parse_only(s):
    if not s:
        return None
    try:
        return [int(x) for x in s.split(",") if x.strip()]
    except ValueError:
        fail(f"--only must be shot numbers separated by commas, got {s!r}")


def stage_call(module, ep, **kw):
    """Import reel.<module> lazily and call its run(); report a broken module without a traceback."""
    try:
        mod = importlib.import_module(f"reel.{module}")
    except Exception as e:                       # missing file, syntax error, missing dependency
        fail(f"cannot run the {module} stage: reel/{module}.py failed to load ({type(e).__name__}: {e})")
    if not hasattr(mod, "run"):
        fail(f"cannot run the {module} stage: reel/{module}.py has no run()")
    return mod.run(ep, **kw)


# ---- check -------------------------------------------------------------------------------------------------
def cmd_check(ep: Path, strict=False) -> int:
    from reel import budget, shots as S
    try:
        rep = S.validate(ep, strict_clips=strict)
        shots, edit = S.load_shots(ep), S.load_edit(ep)
    except S.ReelError as e:
        print(f"error: {e}")
        return 1
    by_n = S.shot_by_n(shots)
    bars = edit.get("bars", [])
    print(f"{ep.name}: {len(shots.get('shots', []))} shots, style {shots.get('style')}, "
          f"layout {edit.get('layout', 'full')} {edit.get('size')}, {edit.get('fps')} fps, "
          f"{bars[-1] if bars else 0:.2f} s")
    print("\n shot  bars    seconds  source  clip")
    for e in edit.get("shots", []):
        s = by_n.get(e.get("n"), {})
        try:
            dur = bars[e["to_bar"]] - bars[e["from_bar"]]
            span = f"{e['from_bar']:>2}-{e['to_bar']:<2}"
        except (KeyError, IndexError, TypeError):
            dur, span = float("nan"), "?"
        cp = ep / e.get("clip", "")
        state = "ok" if e.get("clip") and cp.is_file() else "not made yet"
        if s.get("source") == "hero" and not (ep / f"out/hero_raw/c{e['n']:02d}.mp4").exists():
            state += ", hero raw missing"
        print(f" {e.get('n'):>4}  {span}  {dur:7.2f}  {s.get('source', '?'):6}  {e.get('clip')} ({state})")
    try:
        sm = budget.summary(ep)
        c = sm["cfg"]
        print(f"\nhero shots: {sm['hero_count']} ({sm['hero_seconds']:g} s of hero video)")
        print(f"credit estimate: {sm['pending_total']:g} for {sm['unlogged']} hero shot(s) not yet in the ledger; this reel {sm['reel_total']:g} / "
              f"{c['credits_per_reel']}; month {sm['month']} {sm['month_total']:g} / {c['credits_per_month']}")
        for m in budget.cap_problems(sm):
            rep.err(m)
    except (S.ReelError, KeyError, TypeError) as e:
        if not rep.errors:
            rep.err(f"credit estimate failed: {e}")
    for m in rep.notes:
        print("note:", m)
    for m in rep.warnings:
        print("warning:", m)
    for m in rep.errors:
        print("error:", m)
    print("\ncheck FAILED" if rep.errors else "\ncheck passed")
    return 1 if rep.errors else 0


# ---- all ---------------------------------------------------------------------------------------------------
def missing_hero(ep: Path):
    from reel import shots as S
    return [s for s in S.load_shots(ep)["shots"] if s.get("source") == "hero"
            and not (ep / f"out/hero_raw/c{s['n']:02d}.mp4").exists()]


def cmd_all(ep: Path, args) -> int:
    if cmd_check(ep):
        return 1
    only, force = parse_only(args.only), args.force
    print("\n== stills ==")
    stage_call("stills", ep, only=only, force=force)
    print("\n== motion ==")
    stage_call("motion", ep, only=only, force=force)
    miss = missing_hero(ep)
    if miss:
        print("\nStopped before finish: hero clips are missing from out/hero_raw/:")
        for s in miss:
            print(f"  shot {s['n']}: out/hero_raw/c{s['n']:02d}.mp4  ({s['hero']['model']} {s['hero']['resolution']}"
                  f" {s['hero']['duration']} s)")
        print("Run `reel.py <ep> hero-plan`, make them (Claude, via Higgsfield), log each with `hero-log`, "
              "then run `all` again (finished stages are skipped).")
        return 2
    print("\n== finish ==")
    stage_call("finish", ep, only=only, force=force)
    print("\n== assemble ==")
    from reel import assemble
    assemble.run(ep)
    return 0


def main():
    ap = argparse.ArgumentParser(prog="reel.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("episode", help="episode slug (e.g. 900-pipeline-demo) or path to an episode folder")
    ap.add_argument("stage", choices=STAGES)
    ap.add_argument("--only", help="comma-separated shot numbers (stills, motion, finish, all)")
    ap.add_argument("--force", action="store_true", help="redo outputs that already exist")
    ap.add_argument("--strict", action="store_true", help="check: a missing clip file is an error")
    ap.add_argument("--captions", action="store_true", help="assemble: redo only captions, preview and cover")
    ap.add_argument("--n", type=int, help="hero-log: shot number")
    ap.add_argument("--credits", type=float, help="hero-log: credits charged")
    ap.add_argument("--job", help="hero-log: Higgsfield job id")
    ap.add_argument("--model", help="hero-log: override model (default from shots.json)")
    ap.add_argument("--seconds", type=float, help="hero-log: override seconds (default from shots.json)")
    ap.add_argument("--date", help="hero-log: YYYY-MM-DD (default today)")
    a = ap.parse_args()
    ep = resolve_ep(a.episode)
    from reel import shots as S
    try:
        if a.stage == "check":
            return cmd_check(ep, a.strict)
        if a.stage in ("stills", "motion", "finish"):
            if a.stage == "finish":
                rep = S.validate(ep)
                if rep.errors:
                    fail("fix check errors first:\n  " + "\n  ".join(rep.errors))
            stage_call(a.stage, ep, only=parse_only(a.only), force=a.force)
            return 0
        if a.stage == "hero-plan":
            from reel import budget
            return budget.hero_plan(ep)
        if a.stage == "hero-log":
            if a.n is None or a.credits is None:
                fail("hero-log needs --n <shot> and --credits <amount> (and --job <id>)", 2)
            from reel import budget
            budget.hero_log(ep, a.n, a.credits, a.job, a.model, a.seconds, a.date)
            return 0
        if a.stage == "assemble":
            from reel import assemble
            assemble.run(ep, captions_only=a.captions)
            return 0
        if a.stage == "all":
            return cmd_all(ep, a)
    except S.ReelError as e:
        fail(f"error: {e}")


if __name__ == "__main__":
    sys.exit(main() or 0)
