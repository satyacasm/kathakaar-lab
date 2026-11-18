# Content loop: research → make → approve → post, twice a day (design)

Date: 2026-11-18 · Owner: Satyam · Status: draft for approval (builder-checked; answers folded in)

## 1. Intent and why

Kathakaar (Hindi/English Indian-mythology Reels and Shorts) already has a working *learning* loop: analytics from
YouTube and Instagram every hour, per-video tags, a weekly review that writes `ideas/LEARNINGS.md`, a daily trend scout,
and a research skill that reads the learnings. What it lacks is a *making* loop. Today every video is produced by hand
in a Claude session, a few per week, so the learning loop has too little data and too little contrast to learn from.

Satyam wants the repo to **produce and post two videos a day, on YouTube and Instagram, with deliberate variety**
(formats, audio sources, hooks, topics, slots), so the analytics can tell what works, and the loop can shift toward it.
He stays in the loop only once a day, from his phone through Claude Code Remote Control, where he **watches each
video** (as a private YouTube upload) and approves or rejects it.

**Success (Satyam's words): follower growth and views going up week over week**, on both platforms.

## 2. Goals, non-goals, anti-goals

Goals
- Two finished, approved videos posted per day at fixed slots, on YouTube (Short) and Instagram (Reel).
- A 2-day buffer of rendered, privately uploaded videos, so a bad night or a rejection doesn't empty a slot.
- A written experiment plan that varies one thing at a time, so every format and audio source has ≥3 videos within
  about 14 days (28 videos).
- After the exploration fortnight, about 70% of slots go to current winners and 30% keep exploring.
- Weekly scoreboard: week-over-week change in followers (YouTube subscribers, Instagram followers) and total views.
- Rejections carry a reason that becomes learning input.

Non-goals
- Long-form (16:9, 5-12 min) videos. The long-video pipeline stays manual.
- TikTok or other platforms.
- Replacing the existing analytics, features, review, trends or inbox code; this builds on them.
- Paid promotion.

Anti-goals (a failure even if it technically works)
- **Anything public without Satyam's approval for that specific video.** A silent day means nothing posts.
- Story claims not checked against the texts (the research skill's verification step is not skipped to hit volume).
- Breaking the standing content rules (below).
- Running over the credit budget, or silently starving the hand-made episodes (e.g. 009 Kalabhairav) of credits.
- A copyright strike (as opposed to a Content ID claim) because a risky track was posted repeatedly after a warning.
- Secrets or channel performance data in the public git repo.

## 3. Constraints

- **Machine:** M5 Air, 16 GB, fanless. One heavy model at a time (`pipeline/gpu_lock.sh`). Local still = 2-3 min
  (FLUX.2 klein 4B, 4-bit, 4 steps). Local video models are too slow; motion is local Ken-Burns/parallax
  (`pipeline/reel/motion.py`) plus bought hero clips. Production runs only while the Mac is on; launchd runs a missed
  calendar job once on wake.
- **Credits:** Higgsfield 600/month total (`pipeline/reel/config.json`, ledger `episodes/credits.json`). This loop gets
  **150 credits for the rest of November 2026** (balance was 257.78 on 18 Nov) and **300/month from December**
  (configurable), leaving the rest for hand-made episodes such as 009 Kalabhairav. Higgsfield is reached only
  through Claude's MCP tools (the `hero` stage is done by Claude), and also offers `generate_audio` for original music.
- **YouTube:** OAuth client in `secrets/`, upload works and lands public directly (the unaudited-project private lock
  did not apply on 2026-11-18; the design must not depend on that either way). Daily quota 10,000 units: an upload is
  ~100 (`videos.insert`; captions 400 each), the trend scout spends ~810/day. `videos.update` (privacy change) ~50.
- **Instagram:** Unified Login token (`secrets/instagram.json`, route "facebook", graph.facebook.com). No draft/scheduled
  posting through the API, so posting happens at the slot from the Mac. API limit 100 published posts / 24 h. Music
  from Instagram's library can't be attached through the API: any song must be baked into the file.
- **Content rules (fixed):** stories verified in primary texts (research skill §3); no humour about the divine; Ravana
  never touches Sita in any frame (check video frames for drift); the art style is never named in public copy
  (`brand/STYLE.md`); one song per reel, no mashups (`music-lab` rule).
- **Security:** headless Claude runs read untrusted text (comments, web pages); every headless job runs in
  `--permission-mode dontAsk` with an allowlist, no raw `sqlite3`, no reading `secrets/` (see `pipeline/loop/README.md`).
  The repo is public: plans, approvals and metrics live in git-ignored `ideas/` and `cache/`.

## 4. Approaches considered

- **A. Scheduled jobs on the Mac + approvals through Remote Control (chosen).** A daily producer job (headless Claude)
  makes videos into a queue and uploads them privately; Satyam approves from his phone in any Remote Control session,
  which records the decision in the queue; a publisher job posts approved videos at the slots. Robust to restarts,
  reuses launchd, inbox, ledger, analytics. Chosen by Satyam.
- B. One long-running Claude session that does everything. Simplest, but production stops whenever the session or the
  Mac restarts, and a chat session is a poor host for hours of renders.
- C. Plan-and-prep automation, rendering in a session Satyam starts. Closer control, but not the hands-off loop he wants.
- Cloud scheduled agents were ruled out: tokens, GPU and the credit ledger are local.

## 5. Decisions made with Satyam

1. Approval is daily, from his phone via Claude Code Remote Control. Nothing posts without his yes for that video.
2. He watches each video first: the preview is a **private YouTube upload**; Instagram posts only after approval.
3. Two posts a day at fixed slots (proposed and accepted as default: **12:30 and 19:30 IST**).
4. Variety is deliberate, across formats, audio, hooks, titles, topics and slots. All three audio sources are in the
   mix: popular copyrighted songs (accepting claims, checking for muting), royalty-free/library tracks, and original
   music generated with Higgsfield.
5. Success = followers and views up week over week. After the exploration fortnight, ~70/30 exploit/explore.
6. **Popular-song Reels on Instagram are posted by Satyam in the Instagram app** (silent file + song added in the app,
   the path the Jatayu reel took). At slot time the loop sends him the silent file, the song name and start time;
   YouTube still posts automatically. Library and original audio are baked in and post automatically on both.
7. **Audio pool:** Satyam drops popular songs into `music-lab/pool/popular/` (git-ignored). The producer may download
   royalty-free tracks from **Pixabay Music only** (licence allows commercial use without attribution), saving them to
   `music-lab/pool/library/` and recording each track (title, artist, URL, licence, date) in `ASSETS.md`. It downloads
   from no other site.
8. **The Mac stays plugged in overnight.** The producer runs 01:00-06:00 under `caffeinate`.
9. **Credits:** 150 for the loop this month, 300/month afterwards (constraint above).

## 6. The design

### 6.1 The daily rhythm
```
07:30  trends   (existing)  trends.py scan + digest
hourly pull     (existing)  analytics yt + ig pull; new: daily follower snapshot
01:00  produce  (new)       headless Claude: plan → research → script → stills → hero/audio → assemble → private YT upload
                            until the buffer holds 2 days of videos (4); stops at 06:00 or the credit cap; caffeinate
09:00  ask      (new)       if videos await approval: notification + INBOX decision listing them
any    approve  (new)       Satyam, in a Remote Control session: "approve 1 and 2" / "reject 3: slow hook"
12:30  publish  (new)       oldest approved video for slot 1 → YT public + IG Reel (popular audio: IG handed to Satyam); log IDs
19:30  publish  (new)       same for slot 2
Sun 09 review   (existing)  + weekly scoreboard (followers, views WoW) + plan update (exploit/explore)
```

### 6.2 The queue (`cache/loop/queue.json`, plus a small CLI)
One record per video: id (= episode slug), status (`planned → researching → producing → preview_ready → approved →
scheduled → posted`, or `rejected`/`failed`), experiment cell (see 6.3), slot assigned, YouTube video id (private),
Instagram media id, rejection reason, timestamps, credits spent. A CLI `pipeline/loop/queue.py` with `list`, `show`,
`approve <id…>`, `reject <id> --reason "…"`, `requeue`, used by Satyam's Remote Control session and by the jobs. State
transitions are validated; `approve` only works on `preview_ready`.

On approve: the video is assigned the next free slot. On reject: the private YouTube video is deleted, the episode is
archived with the reason, and the reason is appended to a "Rejections" section of `ideas/LEARNINGS.md`.

### 6.3 The experiment plan (`ideas/experiment_plan.md`, git-ignored, human-editable)
A 14-day rotation table, one row per planned video: format, audio source, hook type, title style, topic source, slot.
Built so each video changes **one** variable from the current best-known recipe (the "control"), and each value of
each variable reaches n≥3 within the fortnight. Variables and values:

- **format:** music reel · narrated Short · "what the texts say" claim Short · shloka reel · dialogue reel
- **audio source** (music, shloka and dialogue reels): popular song (`audio_src=popular`) · royalty-free/library
  (`library`) · Higgsfield original (`original`)
- **hook type / title style:** from `pipeline/features_vocab.json` (hook_type, title language, claim vs question)
- **topic source:** trend gap (trends digest "Our gap") · festival (`ideas/festival_calendar.json`) · comment request ·
  untold detail from the texts · song-story pairing (`music-lab/SONG_STORY_CATALOGUE.md`) · dialogue catalogue
- **slot:** 12:30 vs 19:30

**Scope of the first fortnight (builder's call, approved with the doc):** testing every variable one at a time would
need ~60 videos, so the fortnight *controls* only **format, audio source and slot**; hook type, title style and topic
source still vary and are tagged (features vocab) but are analysed as secondary. Starting recipe ("control") per format:
the best performer so far in that format (music reel: the Jatayu recipe; narrated: the bold-claim Hindi Short recipe);
until a format has data, its first three videos *are* its baseline. Audio applies to music/shloka/dialogue reels only;
dialogue reels use popular audio only. If a cell can't reach n≥3 in 14 days, it carries into the next fortnight.

The weekly review rewrites the next week's rows: during the exploration fortnight it fills gaps toward n≥3; afterwards
~70% of rows copy the current winning recipe (by the score below) and ~30% try untested or weak cells. The plan is a
file Satyam can edit; the producer never overrides a row he has edited (marked `locked`).

### 6.4 Formats (what the producer can make)
| Format | How it's made (existing parts) | Hero credits | Audio |
|---|---|---|---|
| Music reel | `pipeline/reel.py` stages (stills, motion, hero, finish, assemble), song-timed, EN captions | ≤10 | song (3 sources) |
| Narrated Short | research → Hindi script → voice engine (`engine/voice`, Hindi voice D) → reel pipeline assemble with the narration as the audio bed + soft music; local stills, no hero clips by default | 0 | narration + bed |
| Claim Short | same as narrated, script built around one checkable claim from the text (H1), quote on screen | 0 | narration + bed |
| Shloka reel | the verse (quote-allowed source per `sources/INDEX.md`) on screen with meaning captions, 3-6 stills, slow motion, chant/ambient bed | 0-4 | original or library bed |
| Dialogue reel | `music-lab/DIALOGUE_REEL_CATALOGUE.md` line + music (as 008) | 2-6 | popular |

The narrated formats must not depend on writing a new Remotion episode per video (too slow to automate); they reuse
the reel pipeline's stills/motion/assemble with a narration track. If the reel pipeline can't take a narration track
today, adding that is part of this work.

### 6.5 The producer (headless Claude, `pipeline/loop/produce_prompt.md`)
Runs `claude -p` (model: Opus for research/script quality, configurable) with an allowlist covering: the research
skill's tools (`sources_search.py`, WebSearch/WebFetch for research only), `reel.py` stages, the voice engine, the
queue CLI, `inbox.py`, the YouTube private upload, Read/Edit under `episodes/` and `ideas/`, and the Higgsfield MCP
tools needed for hero clips and `generate_audio`. It never posts publicly, never edits pipeline code, never commits,
never reads `secrets/`. Per video it follows the existing gates as self-checks: research with citations (RESEARCH.md),
script, stills, frame check against content rules, hero clips within the per-reel and monthly caps (`reel.py
hero-plan` refuses over cap), assemble, package (`out/package/youtube.md`, `caption_instagram.txt`), private upload.
Failures mark the queue record `failed` with the reason and add an INBOX `failure` line; the next run continues with
the next video.

Audio: popular songs only from `music-lab/pool/popular/` (Satyam supplies; when a planned song is missing the producer
adds an INBOX decision "supply audio for X" and picks another cell); library tracks from `music-lab/pool/library/`,
topped up from Pixabay Music only, with licence records in `ASSETS.md`; original music via Higgsfield
`generate_audio` within the credit caps. Verified 18 Nov: headless `claude -p` can call the Higgsfield MCP tools.

Model use (builder's call): Opus for research and script (quality matters most there), Sonnet for production steps,
packaging and checks; at most 4 videos per night; per-video timeout. This runs on Satyam's Claude subscription
overnight, when he isn't using it.

### 6.6 Approval through Remote Control
At 09:00 (and when the buffer gains new videos), `ask` writes one INBOX decision and fires a notification: for each
`preview_ready` video, the private YouTube link, title, IG caption first line, experiment cell, credits used. Satyam
opens any Claude session (Remote Control on his phone) and says what he wants; that session runs `queue.py approve` /
`reject`. Approvals made after a slot has passed go to the next free slot. If nothing is approved for a slot, the slot is
skipped. **Late slot (Mac asleep, builder's call):** a slot job that fires up to 2 h late still posts; later than
that, the video moves to the next slot (and the actual post time is recorded, so the slot variable stays honest).

### 6.7 The publisher (no Claude needed)
At each slot, `run.sh publish` takes the oldest approved video assigned to that slot: YouTube `videos.update` to public
(using the existing upload's id), then for library/original audio `instagram_publish.py publish`; for popular audio it
sends Satyam the silent file, the song and its start time (notification + INBOX + the file via Remote Control) and marks
the IG side "posting by hand", recording the reel when it appears in the hourly pull. Otherwise (resumable upload to the returned `uri`), logs IDs
in `episode.json`, marks it `posted`, and notifies. If the Instagram post fails, YouTube stays public and the IG post is
retried at the next slot once, then raised in the INBOX. After posting, the existing hourly pull picks both up
(episode.json carries the IDs), so 1 h/6 h/24 h snapshots exist for every loop video.

Copyright watch: 24 h after posting a `popular` audio video, the pull job checks for an Instagram mute (the reel's
audio status if exposed, else Satyam is asked once in the INBOX) and YouTube claim signals if available; results are
tagged on the video so the review can count them. Two or more claims on the same track: stop using that track.

### 6.8 Scoreboard and score
- New daily snapshot: YouTube `channels.list statistics.subscriberCount` and Instagram `followers_count`, stored with
  the date (analytics DB).
- Weekly review (existing Sunday job) leads with: followers WoW per platform, total views WoW, best/worst videos, and
  the per-cell table (format × audio, etc.) with n.
- Default video score until Satyam writes his own `score()`: followers gained per 1k views (YouTube subscribersGained;
  Instagram follows if available, else omitted) weighted with views relative to the channel median; skip rate (IG) and
  3 s retention (YT) as secondary signals. Rates from videos under 300 views are treated as typical (existing rule).

### 6.9 Budget enforcement
`config.json` gains `loop_credits_per_month` (default 300). The producer checks both the loop cap and the existing
monthly cap before any purchase (hero clip or `generate_audio`); over cap → that video falls back to a 0-credit format
or is skipped, and an INBOX info line says so.

## 7. Left to the builder
- Exact queue schema, file locking between jobs, and CLI flags.
- How the narration track enters the reel pipeline (new `edit.json` field vs a separate assemble mode).
- The producer's allowlist details, per-video timeout, and how many videos it attempts per run.
- How `generate_audio` output is selected (one or several candidates) and length-fit to the cut.
- Whether `ask` and `publish` are new `run.sh` jobs or one job with modes; launchd plist additions.
- The experiment-plan generator's exact balancing method, as long as it varies one thing at a time and reaches n≥3.
