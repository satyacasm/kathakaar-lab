#!/usr/bin/env bash
# Scaffold a new episode folder.
#   pipeline/new_episode.sh <nnn-slug> <short|long>
# Creates episodes/<nnn-slug>/ with episode.json, script/ templates and empty voice/audio/out folders,
# plus engine/app/src/episodes/e<nnn>_<name>/ for the scene code. Register the episode in
# engine/app/src/episodes/index.ts once its Story.tsx exists.
set -euo pipefail
LAB="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="$1"; FORMAT="${2:-short}"
[[ "$SLUG" =~ ^[0-9]{3}-[a-z0-9-]+$ ]] || { echo "slug must look like 002-savitri-satyavan" >&2; exit 2; }
[[ "$FORMAT" == short || "$FORMAT" == long ]] || { echo "format must be short or long" >&2; exit 2; }
EP="$LAB/episodes/$SLUG"
[[ ! -e "$EP" ]] || { echo "exists: $EP" >&2; exit 1; }
NUM="${SLUG%%-*}"; NAME="${SLUG#*-}"; APPDIR="e${NUM}_${NAME//-/_}"
mkdir -p "$EP"/{script,voice,audio,out/final,out/qa} "$LAB/engine/app/src/episodes/$APPDIR"
cat > "$EP/episode.json" <<JSON
{
 "id": "E$NUM",
 "slug": "$SLUG",
 "title_en": "",
 "title_hi": "",
 "format": "$FORMAT",
 "app_dir": "$APPDIR",
 "languages": {"primary": "hi", "extra_audio": ["en"]},
 "sources": [],
 "status": "research",
 "hi_pacing": "own",
 "published": {}
}
JSON
cat > "$EP/script/lines.json" <<'JSON'
{"en": [], "hi": [], "pause_after": {}}
JSON
cat > "$EP/script/RESEARCH.md" <<'MD'
# Research

## 1. Market scan (YouTube Shorts / long videos, Instagram Reels)
| Platform | Title | Channel | Views | Date | Angle taken | Link |
|---|---|---|---|---|---|---|

## 2. Uniqueness verdict
What's overdone · what's missing · our angle (one sentence).

## 3. Verification in primary texts
| Claim / beat | Source (text, book.chapter.verse) | Passage (quote) | Notes (variants, later additions) |
|---|---|---|---|

## 4. Storyline options (2–3), each with the hook line
MD
cat > "$EP/ASSETS.md" <<'MD'
# Assets and licences
House style, narrators, models and sound engine: see `brand/` (all own work or permissive licences).
List any episode-specific asset here with source and licence.
MD
echo "created $EP and engine/app/src/episodes/$APPDIR (status: research)"
