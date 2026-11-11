"""Stills stage: base stills and pose variants with FLUX.2 klein 4B through mflux.

run(ep_dir, only=None, force=False)
Every mflux call is wrapped in pipeline/gpu_lock.sh (one heavy job at a time).
Pose edits: the base still is image 1 (the picture to edit); the character ref is NOT passed
unless config "still.pose_with_ref" is true (see report: passing it made the model re-compose).
"""
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = HERE.parent / "gpu_lock.sh"
DEFAULTS = {"model": "flux2-klein-4b", "quantize": 4, "steps": 4, "width": 1344, "height": 768,
            "pose_with_ref": False, "pose_guidance": None}


def _cfg():
    p = HERE / "config.json"
    cfg = dict(DEFAULTS)
    if p.exists():
        cfg.update(json.loads(p.read_text()).get("still", {}))
    return cfg


def _style(name):
    p = HERE / "styles" / f"{name}.txt"
    if not p.exists():
        raise SystemExit(f"stills: unknown style '{name}' ({p} missing)")
    return p.read_text().strip()


def _generate(cmd_base, prompt, out, seed, cfg, images=None, guidance=None):
    out.parent.mkdir(parents=True, exist_ok=True)
    pfile = out.with_suffix(".prompt.txt")
    pfile.write_text(prompt + "\n")
    exe = "mflux-generate-flux2-edit" if images else "mflux-generate-flux2"
    cmd = [str(LOCK), exe, "--model", cfg["model"], "--quantize", str(cfg["quantize"]),
           "--prompt-file", str(pfile), "--width", str(cfg["width"]), "--height", str(cfg["height"]),
           "--steps", str(cfg["steps"]), "--seed", str(seed), "--output", str(out)]
    if images:
        cmd += ["--image-paths", *map(str, images)]
    if guidance is not None:
        cmd += ["--guidance", str(guidance)]
    pfile.write_text(prompt + "\n")
    out.with_suffix(".cmd.txt").write_text(" ".join(cmd) + "\n")
    # mflux never overwrites: with the output present it writes <name>_1.png instead, so a forced
    # regeneration must move the old image out of the way first (kept as .prev.png until the new one exists)
    prev = out.with_suffix(".prev.png")
    if out.exists():
        out.replace(prev)
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    made = out.exists()
    if made:
        prev.unlink(missing_ok=True)
    elif prev.exists():
        prev.replace(out)                      # generation failed: put the old image back
    dt = time.time() - t
    if r.returncode != 0 or not made:
        raise RuntimeError(f"mflux failed for {out.name} (exit {r.returncode}): {r.stderr[-800:]}")
    return dt


def run(ep_dir, only=None, force=False):
    ep = Path(ep_dir)
    spec = json.loads((ep / "script" / "shots.json").read_text())
    cfg = _cfg()
    style = _style(spec.get("style", "watercolor_ink"))
    chars = spec.get("characters", {})
    kf = ep / "out" / "keyframes"
    done, skipped, failed, total = 0, 0, [], 0.0

    def report(name, dt):
        nonlocal done, total
        done += 1; total += dt
        print(f"{name}: {dt:.0f}s", flush=True)

    for shot in spec["shots"]:
        n = shot["n"]
        if only is not None and n not in only:
            continue
        base = kf / f"s{n:02d}.png"
        names = shot.get("characters", [])
        try:
            if force or not base.exists():
                descs = "; ".join(chars[c]["desc"] for c in names)
                prompt = shot["prompt"] + (". Characters: " + descs if descs else "") + ". " + style
                refs = [ep / chars[c]["ref"] for c in names]
                if refs:
                    prompt = ("Use the attached reference image(s) only for the character's face, skin, hair and costume; "
                              "paint a new scene. ") + prompt
                report(base.name, _generate(None, prompt, base, shot.get("seed", 1), cfg, refs or None))
            else:
                skipped += 1
            for pose in shot.get("poses", []):
                out = kf / f"s{n:02d}_{pose['id']}.png"
                if out.exists() and not force:
                    skipped += 1
                    continue
                prompt = ("Edit this exact painting. Keep the same background, camera framing, composition, colors, "
                          "painting style and character identity and costume. Change only the pose: "
                          + pose["edit"] + ". " + style)
                imgs = [base] + ([ep / chars[c]["ref"] for c in names] if cfg["pose_with_ref"] else [])
                report(out.name, _generate(None, prompt, out, shot.get("seed", 1), cfg, imgs, cfg["pose_guidance"]))
        except Exception as e:
            print(f"FAILED shot {n}: {e}", flush=True)
            failed.append(n)
    print(f"stills: {done} generated, {skipped} skipped, {len(failed)} failed shots {failed}, {total:.0f}s total")
    if failed:
        raise SystemExit(1)
