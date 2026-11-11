# Kathakaar content pipeline

Two products from one engine:
- **Reel / Short** (30–60 s, 1080×1920): posted to **Instagram (Hindi)** and **YouTube Shorts (Hindi)** at the same time.
- **Long video** (5–12 min, 1920×1080): **YouTube only**. Hindi is the main audio; the English narration is added as a second audio track.

On YouTube, captions are **separate tracks, never drawn on the picture**. They are uploaded as Hindi and English caption tracks and also embedded in the MP4 as switchable subtitle streams.

Satyam decides at five gates. Nothing is published without his explicit "publish" for that episode.

```
 idea ──► 1 RESEARCH ──► [GATE 1: pick idea + angle]
          market scan (YT Shorts, IG Reels) · uniqueness verdict · verification in primary texts
      ──► 2 SCRIPT (Hindi + English, plain words, cited) ──► [GATE 2: approve story + dialogue]
      ──► 3 VOICE (Hindi D, English A2; 3 takes per line, auto-scored) ──► [GATE 3: listen (quick)]
      ──► 4 STORYBOARD + SCENES (house style kit) ──► draft render ──► [GATE 4: watch draft]
      ──► 5 FINAL: render 4 targets · QA · captions · English track · thumbnail · metadata ──► [GATE 5: "publish"]
      ──► 6 PUBLISH: Short → Instagram + YouTube · Long → YouTube; log the post IDs in episode.json
```

## Stage details

### 1 Research (the most research-intensive step)
Input: Satyam's idea or theme, or "suggest ideas".
1. **Market scan.** Search YouTube for existing Shorts and long videos on the story in Hindi and English (YouTube Data API `search.list`, last 24 months, by views), and search the web for Instagram Reels on the same story (Instagram has no public search API). Record titles, channels, views and the angle each one takes.
2. **Uniqueness verdict.** What has been done to death, what is missing, and the angle that makes ours different. If the idea isn't distinctive, say so and propose alternatives.
3. **Verification in primary texts.** Locate the story in the authentic sources: Bhagavad Gita, Ramayana (Valmiki), Mahabharata (critical edition and Ganguli), the Puranas (Bhagavata, Vishnu, Matsya, Markandeya, Shiva and others), with book, chapter and verse. Quote the passages, note differences between texts, and separate scripture from later folk additions. Local library: `sources/` (offline; `pipeline/sources_search.py` searches it and cites book › section › line). The full procedure is the `kathakaar-research` skill.
4. Output: `episodes/<slug>/script/RESEARCH.md`, containing the scan table, verdict, citations and 2–3 storyline options with hooks.

### 2 Script
Hindi and English versions. Everyday words, no heavy Sanskritised Hindi or ornate English. A hook in the first 2 seconds, a clear cause → turn → payoff, short punchy dialogue, nothing vague. Every line is tied to a source citation, and dramatic licence is listed openly. Writes `script/SCRIPT.md`, `SCRIPT_HI.md` and `lines.json` (`en`, `hi`, `pause_after`).

### 3 Voice
`engine/kk.sh <ep> hindi_takes --takes 3` and `engine/kk.sh <ep> gen_takes --takes 3`, then `review_takes` / `fit_takes` → `voice/picks_hi.json`, `voice/picks_en.json`.

### 4 Storyboard and scenes
Line timings become `timing.json` and the storyboard. Claude writes `engine/app/src/episodes/<id>/` from the Pattachitra kit (multiplane layers and house transitions, see `brand/STYLE.md`) and the sound cue sheet. Draft: `engine/render.sh <ep> short-hi --draft`.

### 5 Final package
`engine/render.sh <ep>` renders long-hi, long-en, short-hi and short-en with QA. Packaging adds:
- `captions_hi.srt` and `captions_en.srt`, timed from the takes
- the English narration placed on the Hindi picture's timing, as the extra YouTube audio track
- MP4s with embedded soft subtitles
- a thumbnail
- titles, descriptions and hashtags in Hindi and English

### 6 Publish (only after Gate 5)
**Integrations resumed 8 Nov 2026** (one-time account setup: `PUBLISHING_SETUP.md`). Until that's done, the pipeline prepares an upload-ready package in `out/package/` (videos, caption files, titles, descriptions, hashtags, English audio track, step-by-step upload notes) and Satyam uploads by hand.

- **Short:** Instagram Reel through the Graph API (resumable upload to `rupload.facebook.com`), plus a YouTube Short (`videos.insert`, then `captions.insert` for Hindi and English).
- **Long:** YouTube (`videos.insert`, `captions.insert` for Hindi and English, localized English title and description). **The English audio track is a manual step in YouTube Studio** (Languages → Add language → Add audio track): the API has no endpoint for it. The pipeline prepares the file and the exact steps.
- **Logging:** post IDs and URLs go into `episode.json`.

## Music reels (song-timed, low cost)
One-minute reels cut to a song, about 10 Higgsfield credits each (600 a month). Stills and most motion are made locally; a few "hero" clips are bought. Full contract, JSON formats and machine rules: `pipeline/REEL_PIPELINE.md`.

Scaffold: `pipeline/new_reel.sh <nnn-slug>`. Then, with `R="pipeline/.venv/bin/python pipeline/reel.py <slug>"`:
- `$R check`: validate `script/shots.json` and `script/edit.json`; print shot lengths, hero seconds, credit estimate vs caps.
- `$R stills` / `$R motion`: local stills, then local animation of `local` shots (`--only 3,5`, `--force`).
- `$R hero-plan`: print what to buy for hero shots (refuses over the per-reel or monthly cap). `$R hero-log --n 2 --credits 2 --job <id>`: record a purchase in `episodes/credits.json`.
- `$R finish`: upscale and retime the hero clips in `out/hero_raw/`.
- `$R assemble`: cut to bars, transitions, grade, captions, end card, then `out/final/reel_SILENT.mp4` (upload master), `reel_with_song.mp4` (preview) and `cover.jpg`. `--captions` redoes only the caption pass.
- `$R all`: check, stills, motion, finish, assemble; stops and lists any hero clips still missing.

## Platform facts that shape the design
- **YouTube API uploads from a new, unaudited Google Cloud project are forced to private.** Until the free API audit passes, the pipeline uploads as private and Satyam switches the video to public.
- `captions.insert` costs 400 quota units, against a default of 10,000 per day.
- **Instagram:** a professional account, a Meta app with `instagram_business_content_publish`, and a long-lived token (renew it every 60 days). Limit: 100 API posts per 24 h.
- **Secrets** live only in `~/kathakaar-lab/secrets/` (chmod 600). They are never printed and never written into docs or code.

## Build status
| Piece | Status |
|---|---|
| Engine (voice, sound, render, QA) per episode via `KK_EP` | done; reproduces episode 001 bit for bit |
| House style kit (Pattachitra, layers, transitions) | done; extend per episode |
| `pipeline/new_episode.sh` scaffold | done |
| Captions (`pipeline/captions.py`: Hindi + English SRT on the Hindi timing) | done (ep 002); English *audio* track on the Hindi timing for long videos: next |
| Research tooling | done: `sources/` (19 texts, offline, `INDEX.md`, `variants.json`), `pipeline/fetch_sources.py`, `pipeline/sources_search.py` (cited search), playbook skill `kathakaar-research`; market scan by web search until a YouTube API key exists |
| Instagram publisher (`pipeline/instagram_publish.py`: setup/check/refresh/publish) | built, untested; waiting for the account setup in `PUBLISHING_SETUP.md` (resumed 8 Nov 2026) |
| YouTube publisher (`pipeline/youtube_publish.py`: setup/check/publish; Hindi metadata, English localization, Hindi + English captions, `--publish-at`, `--dry-run`) | built 8 Nov 2026, dry-run tested; waiting for the OAuth client in `PUBLISHING_SETUP.md` |
| QA shot lists (`pipeline/shots_json.py` from `shots_spec.json`) | done |
| Per-episode sound cue sheet (`episodes/<ep>/sound_cues.py`) | done |
| Voice-first timing (`make_timing`, `pipeline/lines_ts.py`, `hi_pacing: own`), take QA (`scan_takes`, `clean_takes`) | done |
| Figure and place kit (`kit/people.tsx` articulated figures, `kit/places.tsx`, `kit/cloth.tsx`) | done; extend per episode |
| Widescreen scene layouts for long videos | before the first long video |
