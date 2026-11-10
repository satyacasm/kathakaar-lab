#!/usr/bin/env bash
# Build the sound, render and QA an episode.
#   engine/render.sh <episode-folder-or-slug> [targets...] [--no-sound] [--draft]
# Targets: long-hi long-en short-hi short-en (default: all four). Hindi is the main language.
#   long-*  1920x1080 for YouTube (the cloth hangs on a patterned wall)
#   short-* 1080x1920 for Instagram Reels + YouTube Shorts
# Outputs <episode>/out/final/<target>.mp4 and <episode>/out/qa/<target>/report.md.
# --draft renders at half size into out/draft/ for quick review, without QA.
set -euo pipefail
ENGINE="$(cd "$(dirname "$0")" && pwd)"
LAB="$(dirname "$ENGINE")"
EP="$1"; shift
[[ -d "$EP" ]] || EP="$LAB/episodes/$EP"
EP="$(cd "$EP" && pwd)"
export KK_EP="$EP" TMPDIR="$LAB/tmp"
mkdir -p "$TMPDIR"
PY="$ENGINE/voice/.venv/bin/python"
ID="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['id'])" "$EP/episode.json")"

SOUND=1; DRAFT=0; TARGETS=()
for a in "$@"; do
  case "$a" in
    --no-sound) SOUND=0 ;;
    --draft) DRAFT=1 ;;
    *) TARGETS+=("$a") ;;
  esac
done
[[ ${#TARGETS[@]} -gt 0 ]] || TARGETS=(long-hi long-en short-hi short-en)

if [[ $SOUND == 1 ]]; then
  "$PY" "$ENGINE/audio/build_sound.py" | sed -n 3,5p
  "$PY" "$ENGINE/audio/build_sound_hi.py" | sed -n 3,5p
fi

cd "$ENGINE/app"
for T in "${TARGETS[@]}"; do
  if [[ $DRAFT == 1 ]]; then
    mkdir -p "$EP/out/draft"
    npx remotion render src/index.ts "$ID-$T" "$EP/out/draft/$T.mp4" --scale=0.5 --log=error | tail -1
    continue
  fi
  mkdir -p "$EP/out/final" "$EP/out/qa"
  npx remotion render src/index.ts "$ID-$T" "$EP/out/final/$T.mp4" --codec=h264 --crf=18 --audio-codec=aac --audio-bitrate=256k --log=error | tail -1
  SHOTS="$EP/shots.json"; [[ "$T" == *-hi ]] && SHOTS="$EP/shots_hi.json"
  rm -rf "$EP/out/qa/$T"
  "$PY" -I "$ENGINE/qa/short_qa.py" "$EP/out/final/$T.mp4" "$EP/out/qa/$T" "$SHOTS" | sed -n 2,4p
done
echo "done: $EP/out/final/"
