# Kathakaar lab

Indian mythology stories as Pattachitra-style animated Reels, Shorts and long YouTube videos, with Hindi narration first. Everything runs locally on this Mac at no cost.

| Folder | What it holds |
|---|---|
| `PIPELINE.md` | The content pipeline: stages, approval gates, publishing, build status. **Start here.** |
| `brand/` | Final house style (`STYLE.md`), narrators and sound theme (`VOICES.md`), narrator reference voices |
| `engine/` | Shared production code: `app/` (Remotion; `src/kit` = style kit, `src/episodes/<id>` = scene code, `src/episodes/index.ts` = registry), `voice/` (TTS takes and scoring, `.venv`), `audio/` (score, SFX, mix, Hindi retime), `qa/`, `render.sh`, `kk.sh`, `kk.py` |
| `episodes/<nnn-slug>/` | One folder per episode: `episode.json`, `script/` (research, scripts, `lines.json`), `voice/` (takes, picks), `audio/` (mixes, stems), `timing*.json`, `shots*.json`, `out/final` (videos), `out/qa` |
| `pipeline/` | Episode scaffolding, captions, packaging, publishing tools |
| `sources/` | Offline library of authentic texts (`texts/`, `INDEX.md` with translator, year and use rule, `variants.json` spellings); refresh with `pipeline/fetch_sources.py` |
| `models/` | Local TTS models: `qwen3-tts-1.7b-base` (English), `chatterbox-multilingual-v3` (Hindi); `fetch_hf.sh` re-downloads with SHA checks |
| `cache/` | Hugging Face cache (tokenizers) · `tools/` Chrome for rendering · `vendor/` read-only references |
| `archive/` | Finished experiments, kept for reference (the story-test: own-voice and puppet cuts, style frames, voice candidates, old workflow and lessons) |
| `secrets/` | API credentials (created during publishing setup, chmod 600; never commit or share) |

## Everyday commands
```bash
pipeline/new_episode.sh 002-<slug> short          # scaffold an episode
engine/kk.sh 002-<slug> hindi_takes --takes 3      # Hindi narration takes
engine/kk.sh 002-<slug> gen_takes --takes 3        # English narration takes
engine/kk.sh 002-<slug> review_takes               # score English takes → voice/review_en
engine/render.sh 002-<slug> short-hi --draft        # quick half-size draft
engine/render.sh 002-<slug>                         # final: long-hi long-en short-hi short-en + QA
pipeline/sources_search.py markandeya banyan child  # find and cite a story in the source texts
```

## Rules carried forward
- **Spending:** zero by default. No paid services or GPU rental without Satyam's approval.
- **Voices:** clone only Satyam's voice; the narrators are designed synthetic voices. No celebrity or real-person voices.
- **Assets:** only CC0 or properly licensed assets, recorded in the episode's `ASSETS.md`. No MathWorks resources.
- **Publishing:** only after Satyam says "publish" for that episode (Gate 5).
- **Content:** mythology is verified against primary texts; no humour about the divine; deities drawn as traditional Pattachitra figures (see `brand/STYLE.md`).
