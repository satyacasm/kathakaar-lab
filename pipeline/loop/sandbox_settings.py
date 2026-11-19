#!/usr/bin/env python3
"""The overnight producer's --settings JSON: Claude Code's Bash sandbox (macOS seatbelt) with file and network limits.

    python3 pipeline/loop/sandbox_settings.py <lab> <home>     (run.sh produce_settings)

Semantics, measured with probes against Claude Code 2.1.328 (cache/loop/sandbox-fix-report.md):
- denyRead / allowRead entries are directories applied recursively (seatbelt `subpath`). An allowRead inside a
  denyRead re-opens it; a denyRead inside an allowRead closes it again (the more specific path wins both ways).
- Python, bash and every tool call getcwd(), which on macOS opens the working directory itself: the lab root must be
  readable, not just its subfolders (the 2026-11-19 rehearsal crashed at interpreter start without it). Directory
  metadata (stat) is allowed everywhere by the runtime; there is no "list this directory but not its contents".
- `credentials.files` (mode deny) is a second, stronger deny: on macOS no allowRead re-opens it.
- Metal (MLX, mflux) never works inside the sandbox: the seatbelt profile allows no GPU IOKit clients and no
  setting adds them (allowMachLookup does not help). The two GPU stages are therefore excludedCommands: they run
  outside the sandbox, still behind the permission allowlist, as fixed code the producer cannot edit (pipeline/ and
  engine/ are write-denied and Edit-denied). Every other command stays sandboxed.
- excludedCommands use Bash permission-rule syntax; `*` matches anywhere (also mid-pattern). A call with `cd`, `$(..)`
  or a redirect always stays sandboxed, and each part of `a && b` needs its own match.
"""
import json
import os
import sys

# Fixed-code commands that need something the sandbox cannot give. Keep this list short.
EXCLUDED = [
    "python3 pipeline/loop/produce.py finish *",                 # private YouTube upload: secrets/ + the API
    "python3 pipeline/loop/produce.py voice *",                  # engine/kk.sh -> MLX TTS on Metal
    "pipeline/.venv/bin/python pipeline/reel.py * stills",       # mflux FLUX.2 on Metal
    "pipeline/.venv/bin/python pipeline/reel.py * stills --*",   # ... with --only N / --force
]

ALLOWED_DOMAINS = [
    "pixabay.com", "cdn.pixabay.com",                                   # library music (audio_pool fetch)
    "higgsfield.ai", "*.higgsfield.ai", "*.amazonaws.com", "*.cloudfront.net",
    "*.r2.cloudflarestorage.com", "storage.googleapis.com",           # Higgsfield media (produce fetch/put)
    "huggingface.co", "*.huggingface.co", "*.hf.co",                   # model cache revalidation (read only)
]


def _both(paths):
    """Each path and its resolved form (symlinked data dirs), sorted and unique."""
    return sorted({q for p in paths for q in (p, os.path.realpath(p))})


def credential_paths(lab, home):
    """Never readable from the sandbox, whatever allowRead says."""
    return [f"{lab}/secrets", f"{home}/.ssh", f"{home}/.cache/huggingface/token",
            f"{home}/.cache/huggingface/stored_tokens"]


def settings(lab, home):
    creds = credential_paths(lab, home)
    return {"sandbox": {
        "enabled": True, "failIfUnavailable": True,
        "autoAllowBashIfSandboxed": False,          # the allowlist still decides what may run
        "allowUnsandboxedCommands": False,          # no dangerouslyDisableSandbox escape
        "excludedCommands": list(EXCLUDED),
        "network": {"allowedDomains": list(ALLOWED_DOMAINS)},
        # Reads: deny the whole home folder, then allow back the lab (cwd) and what the stages read outside it (the uv
        # Python + tools behind the venvs and mflux, Hugging Face model files, fonts); then deny again, inside the
        # lab, secrets/ and the folders the producer has no business in. secrets/, ~/.ssh and the Hugging Face token
        # are also credentials.files denies, which no allowRead can re-open. Shell history, keychains, browser
        # profiles, ~/.config and ~/.aws stay under the home deny. Writes: the lab (cwd) minus code and secrets, plus
        # the Hugging Face model cache only.
        "filesystem": {
            "denyRead": _both([home, *creds] + [f"{lab}/{p}" for p in (".claude", ".git", ".remember", "archive",
                                                                     "downloads")]),
            "allowRead": _both([lab, f"{home}/.local/share/uv", f"{home}/.local/bin",
                                f"{home}/.cache/huggingface/hub", f"{home}/.cache/huggingface/xet",
                                f"{home}/Library/Fonts"]),
            "denyWrite": _both([f"{lab}/{p}" for p in ("pipeline", "engine", "brand", "sources", "secrets", ".git",
                                                       ".claude", "PIPELINE.md", "CLAUDE.md")]),
            "allowWrite": [f"{home}/.cache/huggingface/hub", f"{home}/.cache/huggingface/xet"]},
        "credentials": {"files": [{"path": p, "mode": "deny"} for p in _both(creds)]},
    }}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: sandbox_settings.py <lab> <home>")
    print(json.dumps(settings(sys.argv[1], sys.argv[2])))
