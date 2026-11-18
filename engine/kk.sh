#!/usr/bin/env bash
# Run an engine tool for one episode.
#   engine/kk.sh <episode-folder-or-slug> <tool> [args...]
# Tools: gen_takes hindi_takes review_takes fit_takes compare_voices make_timing clean_takes scan_takes (voice)
#        build_sound build_sound_hi (audio)  short_qa (qa)
# The episode must be a folder directly inside episodes/ (symlinks resolved); the tool must be one of the above.
# Example: engine/kk.sh 001-markandeya-pralaya hindi_takes --takes 3
set -euo pipefail
ENGINE="$(cd "$(dirname "$0")" && pwd)"
LAB="$(dirname "$ENGINE")"
TOOLS=" gen_takes hindi_takes review_takes fit_takes compare_voices make_timing clean_takes scan_takes build_sound build_sound_hi short_qa "
[[ $# -ge 2 ]] || { echo "usage: engine/kk.sh <episode> <tool> [args...]" >&2; exit 2; }
EP="$1"; TOOL="$2"; shift 2
if [[ ! "$TOOL" =~ ^[a-z_]+$ ]] || [[ "$TOOLS" != *" $TOOL "* ]]; then
  echo "unknown tool: $TOOL (one of:$TOOLS)" >&2; exit 2
fi
[[ -d "$EP" ]] || EP="$LAB/episodes/$EP"
[[ -d "$EP" ]] || { echo "no such episode: $EP" >&2; exit 2; }
EPISODES_REAL="$(cd "$LAB/episodes" && pwd -P)"
EP_REAL="$(cd "$EP" && pwd -P)"
if [[ "$(dirname "$EP_REAL")" != "$EPISODES_REAL" ]]; then
  echo "episode must be a folder directly inside $LAB/episodes: $EP" >&2; exit 2
fi
export KK_EP="$EP_REAL"
export HF_HOME="$LAB/cache/hf" TMPDIR="$LAB/tmp"
mkdir -p "$TMPDIR"
for dir in voice audio qa; do
  if [[ -f "$ENGINE/$dir/$TOOL.py" ]]; then exec "$ENGINE/voice/.venv/bin/python" "$ENGINE/$dir/$TOOL.py" "$@"; fi
done
echo "unknown tool: $TOOL" >&2; exit 2
