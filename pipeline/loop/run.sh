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
  # No Glob/Grep (they cannot be path-scoped): the run's facts are appended to the prompt instead of globbed.
  local today pack trends
  today="$(date +%Y-%m-%d)"
  local -a packs=("$LAB"/cache/analytics/review/pack_*.md) digests=("$LAB"/ideas/trends-*.md)   # globs sort lexically
  pack="${packs[${#packs[@]}-1]}"; trends="${digests[${#digests[@]}-1]}"
  [ -e "$pack" ] || pack="(none)"; [ -e "$trends" ] || trends="(none)"
  local facts
  facts="$(printf '\n## This run\n- Today: %s\n- Newest pack: %s\n- Newest trends digest: %s\n' \
    "$today" "${pack#"$LAB"/}" "${trends#"$LAB"/}")"
  perl -e 'alarm shift; exec @ARGV' 1800 \
    claude -p "$(cat "$prompt_file")$facts" \
      --model claude-sonnet-5-5 \
      --permission-mode dontAsk \
      --allowedTools \
        "Read(episodes/**)" "Read(ideas/**)" "Read(cache/analytics/review/**)" "Read(cache/analytics/thumbs/**)" \
        "Read(pipeline/**)" "Read(music-lab/**)" "Read(brand/**)" \
        "Bash(python3 pipeline/features.py auto*)" "Bash(python3 pipeline/features.py todo*)" \
        "Bash(python3 pipeline/features.py context *)" "Bash(python3 pipeline/features.py set *)" \
        "Bash(python3 pipeline/features.py table*)" \
        "Bash(python3 pipeline/analytics.py yt map*)" \
        "Bash(python3 pipeline/analytics.py yt status*)" \
        "Bash(python3 pipeline/analytics.py ig map*)" \
        "Bash(python3 pipeline/analytics.py ig status*)" \
        "Bash(python3 pipeline/review.py pack*)" \
        "Bash(python3 pipeline/trends.py digest*)" \
        "Bash(python3 pipeline/loop/inbox.py *)" \
        "Bash(python3 pipeline/loop/plan.py status*)" "Bash(python3 pipeline/loop/plan.py show*)" \
        "Bash(python3 pipeline/loop/plan.py next-week*)" "Bash(python3 pipeline/loop/plan.py new-fortnight*)" \
        "Bash(python3 pipeline/loop/vqueue.py list*)" \
        "Bash(python3 pipeline/loop/vqueue.py rejections*)" \
        "Edit(ideas/**)" \
      --disallowedTools "WebFetch" "WebSearch" "Bash(git *)" "Bash(rm *)" "Bash(sqlite3 *)" "Bash(curl *)" \
        "Read(secrets/**)" "Read(/$LAB/secrets/**)" "Read(~/.ssh/**)" "Read(~/.config/**)" "Read(~/.aws/**)" \
        "Bash(python3 pipeline/features.py set * --override*)" "Bash(*--out*)" "Bash(*--csv*)" "Bash(*--path*)" \
      --strict-mcp-config \
      --no-session-persistence \
      --output-format text < /dev/null
}

# perl (no gtimeout on stock macOS): run the command in its own process group; after <secs> TERM the whole group
# (stills, voice and ffmpeg children included), KILL it 30 s later, exit 142. Usage: perl -e "$DEADLINE_PL" secs cmd...
DEADLINE_PL='
  my $secs = shift;
  my $pid = fork() // die "fork: $!";
  if ($pid == 0) { setpgrp(0, 0); exec @ARGV or die "exec: $!"; }
  my $timed = 0;
  $SIG{ALRM} = sub { if ($timed++) { kill "KILL", -$pid } else { kill "TERM", -$pid; alarm 30 } };
  alarm $secs;
  while (waitpid($pid, 0) == -1 && $!{EINTR}) {}
  my $st = $?;
  if ($timed) { kill "KILL", -$pid; exit 142 }
  alarm 0;
  exit($st & 127 ? 128 + ($st & 127) : $st >> 8);
'

produce_window() {  # seconds the producer may run now: 0 outside 00:30-05:30 IST, else min(5 h, until 06:00)
  python3 pipeline/loop/produce.py window-seconds
}

produce_settings() {  # --settings JSON: Bash sandbox (seatbelt) with file and network limits
  python3 - "$LAB" "$HOME" <<'PY'
import json, os, sys
lab, home = sys.argv[1], sys.argv[2]
both = lambda paths: sorted({q for p in paths for q in (p, os.path.realpath(p))})   # symlinked data dirs too
print(json.dumps({"sandbox": {
    "enabled": True, "failIfUnavailable": True,
    "autoAllowBashIfSandboxed": False,          # the allowlist still decides what may run
    "allowUnsandboxedCommands": False,          # no dangerouslyDisableSandbox escape
    # the private upload needs secrets/ and the YouTube API; the command is fixed and allow-listed
    "excludedCommands": ["python3 pipeline/loop/produce.py finish *"],
    "network": {"allowedDomains": [
        "pixabay.com", "cdn.pixabay.com",                                  # library music (audio_pool fetch)
        "higgsfield.ai", "*.higgsfield.ai", "*.amazonaws.com", "*.cloudfront.net",
        "*.r2.cloudflarestorage.com", "storage.googleapis.com",          # Higgsfield media (produce fetch/put)
        "huggingface.co", "*.huggingface.co", "*.hf.co"]},                 # model cache revalidation (read only)
    # Reads: deny the whole home folder, then allow back only what the stages read (the lab's working folders, the
    # uv Python + tools behind the venvs and mflux, Hugging Face model files, fonts). secrets/, ~/.ssh, credentials,
    # shell history, keychains, browser profiles and ~/.cache/huggingface/token stay unreadable. Writes: the lab (cwd)
    # minus code and secrets, plus the Hugging Face model cache only.
    "filesystem": {
        "denyRead": both([home, f"{lab}/secrets", f"{home}/.cache/huggingface/token",
                          f"{home}/.cache/huggingface/stored_tokens"]),
        "allowRead": both([f"{lab}/{p}" for p in ("episodes", "ideas", "music-lab", "sources", "brand", "pipeline",
                                                  "engine", "models", "cache", "tmp", "tools", "vendor",
                                                  "ASSETS.md", "PIPELINE.md")]
                          + [f"{home}/.local/share/uv", f"{home}/.local/bin", f"{home}/.cache/huggingface/hub",
                             f"{home}/.cache/huggingface/xet", f"{home}/Library/Fonts"]),
        "denyWrite": both([f"{lab}/{p}" for p in ("pipeline", "engine", "brand", "sources", "secrets", ".git",
                                                  ".claude", "PIPELINE.md", "CLAUDE.md")]),
        "allowWrite": [f"{home}/.cache/huggingface/hub", f"{home}/.cache/huggingface/xet"]},
}}))
PY
}

job_produce() {
  # Overnight producer (launchd 01:00): headless Claude follows produce_prompt.md, calling produce.py start until it
  # prints STOP (06:00 IST, buffer of 4, LOOP_MAX_VIDEOS, no plan rows). Starts only 00:30-05:30 IST; runs at most
  # 5 h and never past 06:00 (the whole process group is stopped); then `produce.py sweep` fails any video still
  # "producing" and reports an unreconciled Higgsfield balance. caffeinate keeps the Mac awake (-i idle, -s on AC).
  # Permission boundary: dontAsk + explicit allowlist (reads scoped to the lab, edits to episodes/ and ideas/, fixed
  # commands only: no ffmpeg/kk.sh/curl/git of its own) + the Bash sandbox from produce_settings (writes and network
  # limited; LOOP_PRODUCE_SANDBOX=0 turns it off for diagnosis only). Higgsfield comes from the claude.ai connector,
  # so no --strict-mcp-config.
  local prompt_file="$LAB/pipeline/loop/produce_prompt.md"
  [ -f "$prompt_file" ] || { echo "missing $prompt_file"; return 1; }
  command -v claude >/dev/null || { echo "claude CLI not on PATH"; return 1; }
  local secs settings
  secs="$(produce_window)" || return 1
  if [ "$secs" -le 60 ]; then echo "outside night window (00:30-05:30 IST): not starting"; return 0; fi
  if [ "${LOOP_PRODUCE_SANDBOX:-1}" = "0" ]; then
    settings='{}'; echo "WARNING: Bash sandbox off (LOOP_PRODUCE_SANDBOX=0)"
    inbox "producer ran WITHOUT the Bash sandbox (LOOP_PRODUCE_SANDBOX=0): for diagnosis only; unset it" info
  else settings="$(produce_settings)" || return 1; fi
  LOOP_RUN_START="$(python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"))')"
  export LOOP_RUN_START
  export LOOP_MAX_VIDEOS="${LOOP_MAX_VIDEOS:-4}"
  echo "producer: run start $LOOP_RUN_START, max $LOOP_MAX_VIDEOS videos, hard stop in ${secs}s"
  local rc=0
  caffeinate -i -s perl -e "$DEADLINE_PL" "$secs" \
      claude -p "$(cat "$prompt_file")" \
        --model claude-opus-5-5 \
        --permission-mode dontAsk \
        --settings "$settings" \
        --allowedTools \
          "Read(episodes/**)" "Read(ideas/**)" "Read(music-lab/**)" "Read(sources/**)" "Read(brand/**)" \
          "Read(pipeline/**)" "Read(PIPELINE.md)" "Read(~/.claude/skills/kathakaar-research/SKILL.md)" \
          "WebSearch" "WebFetch" \
          "Edit(episodes/**)" "Edit(ideas/**)" \
          "Bash(pipeline/.venv/bin/python pipeline/reel.py *)" \
          "Bash(pipeline/.venv/bin/python pipeline/reel/budget.py *)" \
          "Bash(pipeline/sources_search.py *)" \
          "Bash(python3 pipeline/loop/produce.py *)" \
          "Bash(python3 pipeline/loop/narration.py *)" \
          "Bash(python3 pipeline/loop/audio_pool.py *)" \
          "Bash(python3 pipeline/loop/plan.py show*)" \
          "Bash(python3 pipeline/loop/plan.py next*)" \
          "Bash(python3 pipeline/loop/inbox.py *)" \
          "mcp__claude_ai_Higgsfield__generate_video" \
          "mcp__claude_ai_Higgsfield__generate_audio" \
          "mcp__claude_ai_Higgsfield__estimate_video_cost" \
          "mcp__claude_ai_Higgsfield__estimate_audio_cost" \
          "mcp__claude_ai_Higgsfield__media_upload" \
          "mcp__claude_ai_Higgsfield__media_confirm" \
          "mcp__claude_ai_Higgsfield__jobs_wait" \
          "mcp__claude_ai_Higgsfield__show_generation_by_ids" \
          "mcp__claude_ai_Higgsfield__balance" \
        --disallowedTools "Bash(git *)" "Bash(rm *)" "Bash(sqlite3 *)" "Bash(curl *)" \
          "Read(secrets/**)" "Read(/$LAB/secrets/**)" "Read(~/.ssh/**)" "Read(~/.config/**)" "Read(~/.aws/**)" \
          "Edit(episodes/credits.json)" "Edit(/$LAB/episodes/credits.json)" \
          "Edit(pipeline/**)" "Edit(engine/**)" "Edit(secrets/**)" \
        --no-session-persistence \
        --output-format text < /dev/null || rc=$?
  python3 pipeline/loop/produce.py sweep --reason "the producer run ended (exit $rc) before finish" || true
  case "$rc" in
    0) ;;
    142) echo "producer stopped at its deadline (06:00 IST or 5 h)"; rc=0 ;;
    *) echo "producer exited $rc" ;;
  esac
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
