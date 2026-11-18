#!/bin/bash
# Single entry point for the Kathakaar feedback-loop automation (launchd calls this; you can too).
#
#   pipeline/loop/run.sh <job>        job = pull | trends | ig-refresh | review | produce | status
#
# Per job: PATH is set, cwd = the lab, a lock dir (cache/loop/locks/<job>.lock, stale after 3 h; produce 5.5 h)
# prevents overlap,
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
  # YouTube first; its result is kept even if Instagram fails (the job still exits non-zero then -> INBOX failure line).
  local yt_rc=0 ig_rc=0 fl_rc=0
  python3 pipeline/analytics.py yt pull || yt_rc=$?
  if [ -f "$LAB/secrets/instagram.json" ]; then
    python3 pipeline/analytics.py ig pull || ig_rc=$?
  else
    echo "secrets/instagram.json missing: skipping Instagram pull"
  fi
  # daily follower snapshot (no-op if today's rows exist); skips Instagram itself when secrets are missing
  python3 pipeline/analytics.py followers pull || fl_rc=$?
  [ "$yt_rc" -ne 0 ] && return "$yt_rc"
  [ "$ig_rc" -ne 0 ] && return "$ig_rc"
  return "$fl_rc"
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
        "Bash(python3 pipeline/analytics.py ig map*)" \
        "Bash(python3 pipeline/analytics.py ig status*)" \
        "Bash(python3 pipeline/review.py *)" \
        "Bash(python3 pipeline/trends.py digest*)" \
        "Bash(python3 pipeline/loop/inbox.py *)" \
        "Edit(ideas/**)" \
      --disallowedTools "WebFetch" "WebSearch" "Bash(git *)" "Bash(rm *)" "Bash(sqlite3 *)" "Bash(curl *)" "Read(secrets/**)" "Read(~/.ssh/**)" \
      --strict-mcp-config \
      --no-session-persistence \
      --output-format text < /dev/null
}

job_produce() {
  # Overnight producer (01:00 launchd): headless Claude follows produce_prompt.md, calling produce.py start until it
  # prints STOP (06:00 IST, buffer of 4, LOOP_MAX_VIDEOS, or no plan rows). Hard stop at the next 06:00 IST via a
  # perl alarm; afterwards `produce.py sweep` marks any video still "producing" failed (INBOX failure line).
  # caffeinate keeps the Mac awake (-i idle, -s on AC power). The Higgsfield MCP tools come from the claude.ai
  # connector, so no --strict-mcp-config here.
  local prompt_file="$LAB/pipeline/loop/produce_prompt.md"
  [ -f "$prompt_file" ] || { echo "missing $prompt_file"; return 1; }
  command -v claude >/dev/null || { echo "claude CLI not on PATH"; return 1; }
  local secs
  secs="$(python3 - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo("Asia/Kolkata"))
end = now.replace(hour=6, minute=0, second=0, microsecond=0)
if now >= end:
    end += timedelta(days=1)
print(0 if 6 <= now.hour < 12 else int((end - now).total_seconds()))
PY
)" || return 1
  if [ "$secs" -le 60 ]; then echo "06:00-12:00 IST: the producer does not run now"; return 0; fi
  LOOP_RUN_START="$(python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"))')"
  export LOOP_RUN_START
  export LOOP_MAX_VIDEOS="${LOOP_MAX_VIDEOS:-4}"
  echo "producer: run start $LOOP_RUN_START, max $LOOP_MAX_VIDEOS videos, hard stop in ${secs}s"
  caffeinate -i -s \
    perl -e 'alarm shift; exec @ARGV' "$secs" \
      claude -p "$(cat "$prompt_file")" \
        --model claude-opus-5-5 \
        --permission-mode dontAsk \
        --allowedTools "Read" "Glob" "Grep" "WebSearch" "WebFetch" \
          "Edit(episodes/**)" "Edit(ideas/**)" \
          "Bash(pipeline/.venv/bin/python pipeline/reel.py *)" \
          "Bash(pipeline/.venv/bin/python pipeline/reel/budget.py *)" \
          "Bash(pipeline/sources_search.py *)" \
          "Bash(engine/kk.sh *)" \
          "Bash(pipeline/new_reel.sh *)" \
          "Bash(pipeline/new_episode.sh *)" \
          "Bash(python3 pipeline/loop/produce.py *)" \
          "Bash(python3 pipeline/loop/narration.py *)" \
          "Bash(python3 pipeline/loop/audio_pool.py *)" \
          "Bash(python3 pipeline/loop/plan.py show*)" \
          "Bash(python3 pipeline/loop/plan.py next*)" \
          "Bash(python3 pipeline/loop/inbox.py *)" \
          "Bash(ffmpeg *)" "Bash(ffprobe *)" \
          "mcp__claude_ai_Higgsfield__generate_video" \
          "mcp__claude_ai_Higgsfield__generate_audio" \
          "mcp__claude_ai_Higgsfield__media_upload" \
          "mcp__claude_ai_Higgsfield__media_confirm" \
          "mcp__claude_ai_Higgsfield__jobs_wait" \
          "mcp__claude_ai_Higgsfield__show_generation_by_ids" \
          "mcp__claude_ai_Higgsfield__balance" \
        --disallowedTools "Bash(git *)" "Bash(rm *)" "Bash(sqlite3 *)" "Bash(curl *)" "Read(secrets/**)" \
        --no-session-persistence \
        --output-format text < /dev/null
  local rc=$?
  python3 pipeline/loop/produce.py sweep --reason "the producer run ended (exit $rc) before finish" || true
  if [ "$rc" -eq 142 ]; then echo "producer stopped by the 06:00 IST alarm"; return 0; fi
  return "$rc"
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
  pull|trends|ig-refresh|review|produce) ;;
  *) log "unknown job '$JOB'"; echo "usage: run.sh pull|trends|ig-refresh|review|produce|status" >&2
     inbox "loop job '$JOB' failed: unknown job name" failure; exit 2 ;;
esac

LOCK="$LOOP/locks/$JOB.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  STALE_MIN=180; [ "$JOB" = "produce" ] && STALE_MIN=330   # the producer legitimately runs 01:00-06:00
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +"$STALE_MIN" 2>/dev/null)" ]; then
    log "stale lock (>${STALE_MIN} min), taking over"; rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || { log "lock race, skipping"; exit 0; }
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
