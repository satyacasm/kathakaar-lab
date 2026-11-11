#!/usr/bin/env bash
# Scaffold a music-reel episode folder.
#   pipeline/new_reel.sh <nnn-slug>
# Creates episodes/<nnn-slug>/ with episode.json (kind "music_reel"), script/shots.json and script/edit.json
# templates, and refs/, audio/, out/{keyframes,hero_raw,clips,final} folders. Then:
#   pipeline/.venv/bin/python pipeline/reel.py <nnn-slug> check
# See pipeline/REEL_PIPELINE.md.
set -euo pipefail
LAB="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-}"
[[ "$SLUG" =~ ^[0-9]{3}-[a-z0-9-]+$ ]] || { echo "usage: new_reel.sh <nnn-slug>   (slug like 007-hanuman-leap)" >&2; exit 2; }
EP="$LAB/episodes/$SLUG"
[[ ! -e "$EP" ]] || { echo "exists: $EP" >&2; exit 1; }
NUM="${SLUG%%-*}"
mkdir -p "$EP"/{script,refs,audio,out/keyframes,out/hero_raw,out/clips,out/final}
cat > "$EP/episode.json" <<JSON
{
 "id": "E$NUM",
 "slug": "$SLUG",
 "title_en": "",
 "title_hi": "",
 "format": "music_reel",
 "kind": "music_reel",
 "narration": false,
 "resolution": "1080x1920",
 "layout": "inset",
 "languages": {"primary": "hi", "extra_audio": []},
 "sources": [],
 "status": "research",
 "hi_pacing": "own",
 "published": {},
 "platforms": ["instagram"],
 "song": {"title": "", "artist": "", "segment": "", "add_in_app": true, "instagram_start": ""},
 "higgsfield": {"credits_spent": 0},
 "outputs": {"preview": "out/final/reel_with_song.mp4", "upload_master": "out/final/reel_SILENT.mp4",
             "cover": "out/final/cover.jpg"}
}
JSON
cat > "$EP/script/shots.json" <<'JSON'
{
  "style": "watercolor_ink",
  "characters": {},
  "shots": [
    {"n": 1,
     "prompt": "",
     "characters": [],
     "seed": 101,
     "source": "local",
     "motion": {"type": "drift", "camera": {"move": "push_in", "amount": 0.05, "ease": "in_out"}, "parallax": 0.5},
     "fx": []}
  ]
}
JSON
cat > "$EP/script/edit.json" <<'JSON'
{
  "song": "audio/song.wav", "song_in": 0.0, "song_out": 60.0, "fade_out": 1.6,
  "size": [1080, 1920], "fps": 30,
  "layout": "inset",
  "end_card": {"text": "Kathakaar", "sub": "animated stories", "hold": 2.5},
  "bars": [0.0, 2.5],
  "shots": [
    {"n": 1, "clip": "out/clips/c01.mp4", "from_bar": 0, "to_bar": 1, "in": 0.0}
  ],
  "captions": [],
  "transitions": [],
  "grade": {}
}
JSON
echo "created $EP (music reel). Fill script/shots.json and script/edit.json, put the song in audio/, then run:"
echo "  pipeline/.venv/bin/python pipeline/reel.py $SLUG check"
