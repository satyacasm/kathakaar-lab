#!/usr/bin/env bash
# Run one heavy (GPU / large-memory) command at a time on this 16 GB Mac.
#   pipeline/gpu_lock.sh <command> [args...]
# Waits its turn, runs the command, releases the lock, returns the command's exit code.
# First come, first served: each caller takes a numbered ticket in tmp/gpu.queue/ and only tries for the lock
# when its ticket is the oldest live one, so a long batch cannot starve a single job that arrived in between.
# The lock is a directory (mkdir is atomic). Locks and tickets whose owner process is gone are removed.
set -uo pipefail
LAB="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$LAB/tmp/gpu.lock"
QUEUE="$LAB/tmp/gpu.queue"
mkdir -p "$QUEUE"
TICKET="$QUEUE/$(date +%s)$(printf '%05d' $((RANDOM % 100000))).$$"
: > "$TICKET"
cleanup() { rm -f "$TICKET"; [[ "$(cat "$LOCK/pid" 2>/dev/null)" == "$$" ]] && rm -rf "$LOCK"; }
trap cleanup EXIT INT TERM

my_turn() {                       # true when no older ticket belongs to a live process
  local f pid
  for f in "$QUEUE"/*; do
    [[ "$f" == "$TICKET" ]] && return 0
    pid="${f##*.}"
    if kill -0 "$pid" 2>/dev/null; then return 1; else rm -f "$f"; fi
  done
  return 0
}

waited=0
while true; do
  if my_turn && mkdir "$LOCK" 2>/dev/null; then break; fi
  owner="$(cat "$LOCK/pid" 2>/dev/null || true)"
  if [[ -n "$owner" ]] && ! kill -0 "$owner" 2>/dev/null; then rm -rf "$LOCK"; continue; fi
  (( waited % 60 == 0 )) && echo "gpu_lock: waiting (held by pid ${owner:-?})" >&2
  sleep 2; waited=$((waited + 2))
done
echo $$ > "$LOCK/pid"
"$@"
