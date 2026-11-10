#!/usr/bin/env bash
# Run an engine tool for one episode.
#   engine/kk.sh <episode-folder-or-slug> <tool> [args...]
# Tools: gen_takes hindi_takes review_takes fit_takes compare_voices (voice)  build_sound build_sound_hi (audio)
# Example: engine/kk.sh 001-markandeya-pralaya hindi_takes --takes 3
set -euo pipefail
ENGINE="$(cd "$(dirname "$0")" && pwd)"
LAB="$(dirname "$ENGINE")"
EP="$1"; TOOL="$2"; shift 2
[[ -d "$EP" ]] || EP="$LAB/episodes/$EP"
export KK_EP="$(cd "$EP" && pwd)"
export HF_HOME="$LAB/cache/hf" TMPDIR="$LAB/tmp"
mkdir -p "$TMPDIR"
for dir in voice audio qa; do
  if [[ -f "$ENGINE/$dir/$TOOL.py" ]]; then exec "$ENGINE/voice/.venv/bin/python" "$ENGINE/$dir/$TOOL.py" "$@"; fi
done
echo "unknown tool: $TOOL" >&2; exit 2
