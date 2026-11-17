#!/bin/bash
# Single entry point for the Kathakaar feedback-loop automation (launchd calls this; you can too).
#
#   pipeline/loop/run.sh <job>        job = pull | trends | ig-refresh | review | status
#
# Per job: PATH is set, cwd = the lab, a lock dir (cache/loop/locks/<job>.lock, stale after 3 h) prevents overlap,
# output goes to cache/loop/logs/<job>-<YYYY-MM>.log with timestamps, and cache/loop/status.json records
# {last_run, exit, duration_s}. A non-zero exit raises a macOS notification and an INBOX failure line.
# A job that finds its lock held logs "skipped" and exits 0 (not a failure).
#
# launchd note: a calendar job missed while the Mac slept runs once on wake; nothing runs while the Mac is off.
set -u

export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export TZ="${TZ:-Asia/Kolkata}"
LAB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$LAB" || exit 1

JOB="${1:-}"
LOOP="$LAB/cache/loop"
mkdir -p "$LOOP/locks" "$LOOP/logs"
STATUS="$LOOP/status.json"
LOG="$LOOP/logs/${JOB:-none}-$(date +%Y-%m).log"

log() { printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$JOB" "$*" >> "$LOG"; }
inbox() { python3 "$LAB/pipeline/loop/inbox.py" add "$1" --kind "$2" >> "$LOG" 2>&1; }

record_status() {  # job exit duration
  python3 - "$STATUS" "$1" "$2" "$3" <<'PY'
import json, sys, datetime, os
path, job, code, dur = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
try: d = json.load(open(path))
except Exception: d = {}
d[job] = {"last_run": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "exit": code, "duration_s": dur}
tmp = path + ".tmp"; json.dump(d, open(tmp, "w"), indent=2); os.replace(tmp, path)
PY
}

# ---------------------------------------------------------------- jobs
job_pull() {
  python3 pipeline/analytics.py yt pull || return $?
  # --- HOOK: Instagram metrics pull goes here once the Instagram API credentials exist
  # (e.g. python3 pipeline/analytics.py ig pull). Not implemented yet.
}

job_trends() {
  python3 pipeline/trends.py scan || return $?   # "already scanned today" exits 0 = success
  # digest rewrites today's file and would wipe a "Fit for Kathakaar" section Claude already filled: skip then
  local f="$LAB/ideas/trends-$(date +%Y-%m-%d).md"
  if [ -f "$f" ] && [ -n "$(sed -n '/^## Fit for Kathakaar/,$p' "$f" | sed 1d | tr -d '[:space:]')" ]; then
    echo "today's digest already has a filled Fit section: not regenerating"
    return 0
  fi
  python3 pipeline/trends.py digest
}

job_ig_refresh() {
  if [ ! -f "$LAB/secrets/instagram.json" ]; then
    echo "secrets/instagram.json missing: Instagram not set up yet, nothing to refresh"
    return 0
  fi
  python3 pipeline/instagram_publish.py refresh
}

job_review() {
  python3 pipeline/review.py pack || return $?
  local prompt_file="$LAB/pipeline/loop/review_prompt.md"
  [ -f "$prompt_file" ] || { echo "missing $prompt_file"; return 1; }
  command -v claude >/dev/null || { echo "claude CLI not on PATH"; return 1; }
  # Sandbox: dontAsk = anything not allow-listed is denied (no prompts in headless mode). No web, no git, no MCP.
  # 1800 s timeout via perl alarm (no gtimeout on stock macOS); alarm survives exec.
  perl -e 'alarm shift; exec @ARGV' 1800 \
    claude -p "$(cat "$prompt_file")" \
      --model claude-sonnet-5-5 \
      --permission-mode dontAsk \
      --allowedTools "Read" "Glob" "Grep" \
        "Bash(python3 pipeline/features.py *)" \
        "Bash(python3 pipeline/analytics.py yt map*)" \
        "Bash(python3 pipeline/analytics.py yt status*)" \
        "Bash(python3 pipeline/review.py *)" \
        "Bash(python3 pipeline/trends.py digest*)" \
        "Bash(python3 pipeline/loop/inbox.py *)" \
        "Bash(sqlite3 -readonly cache/analytics/*)" \
        "Edit(ideas/**)" \
      --disallowedTools "WebFetch" "WebSearch" "Bash(git *)" "Bash(rm *)" \
      --strict-mcp-config \
      --no-session-persistence \
      --output-format text < /dev/null
}

job_status() {
  echo "== $STATUS"
  cat "$STATUS" 2>/dev/null || echo "(no runs recorded yet)"
  echo
  echo "== launchd jobs (com.kathakaar.*)"
  local out; out="$(launchctl list 2>/dev/null | grep com.kathakaar || true)"
  echo "${out:-(none loaded; run pipeline/loop/install.sh to install)}"
}

# ---------------------------------------------------------------- main
if [ "$JOB" = "status" ]; then job_status; exit 0; fi

case "$JOB" in
  pull|trends|ig-refresh|review) ;;
  *) log "unknown job '$JOB'"; echo "usage: run.sh pull|trends|ig-refresh|review|status" >&2
     inbox "loop job '$JOB' failed: unknown job name" failure; exit 2 ;;
esac

LOCK="$LOOP/locks/$JOB.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then
    log "stale lock (>3h), taking over"; rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || { log "lock race, skipping"; exit 0; }
  else
    log "skipped: already running (lock $LOCK)"; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

START=$(date +%s)
log "start"
fn="job_${JOB//-/_}"
"$fn" >> "$LOG" 2>&1
CODE=$?
DUR=$(( $(date +%s) - START ))
log "end exit=$CODE duration=${DUR}s"
record_status "$JOB" "$CODE" "$DUR"
if [ "$CODE" -ne 0 ]; then
  inbox "loop job '$JOB' failed (exit $CODE) - see cache/loop/logs/${JOB}-$(date +%Y-%m).log" failure
fi
exit "$CODE"
