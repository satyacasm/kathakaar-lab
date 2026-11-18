# Content Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce two varied videos a day overnight, let Satyam approve each one from his phone, and post the approved ones at 12:30 and 19:30 IST on YouTube and Instagram.

**Architecture:** A JSON queue (`cache/loop/queue.json`) is the single source of truth between four launchd jobs: `produce` (headless Claude, 01:00-06:00), `ask` (09:00), `publish` (12:30, 19:30) and the existing `pull`/`trends`/`review`. Small stdlib-Python modules in `pipeline/loop/` own the queue, the experiment plan, audio, credits and publishing; headless Claude only does the creative work (research, script, stills, hero clips, music) and calls those modules.

**Tech Stack:** Python 3.14 stdlib only (unittest, json, fcntl, zoneinfo, urllib), bash + launchd, ffmpeg, existing `pipeline/reel.py`, `engine/kk.sh`, `pipeline/youtube_publish.py`, `pipeline/instagram_publish.py`, `pipeline/analytics.py`, Claude Code `claude -p` with the Higgsfield MCP connector.

**Spec:** `docs/superpowers/specs/2026-11-18-content-loop-design.md`

## Global Constraints

- Nothing becomes public (YouTube public, or any Instagram post) without a `queue.py approve` for that video id. No approval → the slot is skipped.
- Slots: `12:30` and `19:30`, timezone `Asia/Kolkata`, computed with `zoneinfo`, never the system TZ. Late grace: 2 h; later than that, the video moves to the next free slot.
- Buffer target: 4 videos in `preview_ready`/`approved`; at most 4 produced per night; the producer stops at 06:00 IST.
- Credits: loop cap 150 for month `2026-11`, 300 for every later month; the existing 600/month cap still applies. Over cap → fall back to a 0-credit format or skip.
- Audio: popular songs only from `music-lab/pool/popular/`; library tracks only from Pixabay (host `pixabay.com` / `cdn.pixabay.com`) into `music-lab/pool/library/`, each recorded in `ASSETS.md`; original music via Higgsfield `generate_audio`.
- Popular-audio videos: Instagram is posted by Satyam in the app (`ig_mode = "manual"`); everything else posts through the API (`ig_mode = "api"`).
- Content rules: text-verified stories; no humour about the divine; Ravana never touches Sita in any frame; the art style is never named in public copy; one song per reel.
- Headless Claude: `--permission-mode dontAsk`, explicit allowlist, no raw `sqlite3`, no `Read(secrets/**)`, no git, never posts publicly.
- Public repo: queue, plan, metrics, approvals live only in git-ignored `cache/` and `ideas/`. Commit only code and docs.
- Tests: `python3 -m unittest discover -s pipeline/tests -v`; no network in tests (mock HTTP).
- Commits end with the two attribution lines: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01XKy34u9Q6KtTk1dGMjAigg`.

## Review Focus

1. Approving a video whose private YouTube upload no longer exists (deleted in Studio) → `approve` refuses it with a clear message; it never reaches `publish`. (Task 1 + Task 2 test)
2. More approvals than today's free slots, or approving after both slots passed → videos take the next free slots in order, never two videos in one slot. (Task 1 test)
3. Partial publish: YouTube switched to public but Instagram failed → the next run retries Instagram once without touching YouTube again, then raises an INBOX failure. (Task 8 test)
4. A rejection reason with newlines, `#`, `|` or a fake checklist line (`- [x] …`) → stored and written to INBOX/LEARNINGS as one escaped line. (Task 1 test)
5. A track that drew a claim twice keeps getting picked → `audio_pool.blocked` makes `list_tracks` skip it. (Task 4 test)
6. The Mac wakes at 15:10 after sleeping through 12:30 → that video moves to 19:30 (or the next free slot), and the actual post time is recorded. (Task 8 test)

---

### Task 1: Queue (state, slots, approve/reject CLI)

**Files:**
- Create: `pipeline/loop/queue.py`
- Create: `pipeline/tests/__init__.py`, `pipeline/tests/test_queue.py`
- Modify: `pipeline/loop/README.md` (add a "Queue" section: file, statuses, CLI)

**Interfaces:**
- Produces:
  - `STATUSES = ("planned", "producing", "preview_ready", "approved", "posted", "rejected", "failed")`
  - `ALLOWED = {"planned": {"producing", "failed"}, "producing": {"preview_ready", "failed"}, "preview_ready": {"approved", "rejected"}, "approved": {"posted", "failed"}, "failed": {"planned"}}`
  - `SLOTS = ("12:30", "19:30")`, `TZ = ZoneInfo("Asia/Kolkata")`, `LATE_GRACE = timedelta(hours=2)`
  - Record (dict): `id` (episode slug), `status`, `cell` {`format`, `audio`, `slot_pref`}, `slot` (ISO datetime str or None), `yt_id`, `ig_media_id`, `ig_mode` ("api"|"manual"), `credits` (float), `reason`, `posted_at`, `history` (list of [iso, status])
  - `load(path: Path = QUEUE) -> list[dict]`, `save(records: list[dict], path: Path = QUEUE) -> None` (atomic write under an `fcntl.flock` on `queue.json.lock`)
  - `add(record_id: str, cell: dict, ig_mode: str) -> dict`
  - `transition(record_id: str, new_status: str, **fields) -> dict` (raises `QueueError` on a transition not in `ALLOWED`)
  - `next_free_slot(records: list[dict], now: datetime) -> datetime`
  - `approve(ids: list[str], now: datetime, exists: Callable[[str], bool]) -> list[dict]`
  - `reject(record_id: str, reason: str) -> dict`
  - `due(now: datetime) -> dict | None` (the approved record whose slot is ≤ now and ≥ now - LATE_GRACE, oldest first)
  - `one_line(text: str) -> str` (collapse whitespace, escape `|`, strip leading `#`/`-`/`[`, cap 300 chars)
  - CLI: `queue.py list [--all]`, `show <id>`, `approve <id>...`, `reject <id> --reason "..."`, `requeue <id>`

- [ ] **Step 1: Write the failing tests** in `pipeline/tests/test_queue.py` (each test uses a temp `QUEUE` path):

```python
def test_transition_rejects_skip():          # planned -> approved raises QueueError
def test_approve_assigns_slots_in_order():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=TZ)
    # three preview_ready records a, b, c; exists() always True
    out = approve(["a", "b", "c"], now, lambda vid: True)
    assert [r["slot"][:16] for r in out] == ["2026-11-19T12:30", "2026-11-19T19:30", "2026-11-20T12:30"]
def test_approve_after_both_slots_goes_to_tomorrow():   # now 20:15 -> 2026-11-20T12:30
def test_approve_refuses_missing_preview():             # exists() False -> QueueError("private preview ... not found")
def test_approve_only_preview_ready():                  # a "producing" record -> QueueError
def test_reject_stores_one_line_reason():
    r = reject("a", "slow hook\n- [x] fake | item\n# heading")
    assert r["status"] == "rejected" and "\n" not in r["reason"] and r["reason"].startswith("slow hook")
def test_due_respects_grace():
    # slot 12:30; due at 13:00 -> record; due at 14:31 -> None
def test_concurrent_save_keeps_both_records():          # two processes add() at once (multiprocessing) -> 2 records
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest pipeline.tests.test_queue -v`
Expected: FAIL / ImportError (`pipeline/loop/queue.py` missing)

- [ ] **Step 3: Implement `pipeline/loop/queue.py`** with the interfaces above. Slot times are built from the IST calendar date of `now`; `next_free_slot` skips slots already held by `approved`/`posted` records and slots earlier than `now`. The CLI's `approve` uses `exists = youtube_publish.video_exists` (Task 2) and prints each assigned slot in IST.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest pipeline.tests.test_queue -v`
Expected: 8 tests OK

- [ ] **Step 5: Commit** `pipeline/loop/queue.py`, `pipeline/tests/`, README change: `git commit -m "loop: approval queue with IST slots"` (+ attribution lines)

---

### Task 2: YouTube privacy and delete commands

**Files:**
- Modify: `pipeline/youtube_publish.py` (new functions + subcommands; `publish` gains `--preview`)
- Test: `pipeline/tests/test_youtube_ops.py`

**Interfaces:**
- Produces:
  - `video_exists(video_id: str) -> bool` (`videos.list?part=status&id=`; True iff one item returned)
  - `set_privacy(video_id: str, privacy: str) -> str` (`videos.update?part=status`, keeps `selfDeclaredMadeForKids=False`, `embeddable=True`; returns the new privacyStatus; privacy in {"private","unlisted","public"})
  - `delete_video(video_id: str) -> None` (`videos.delete`; a 404 counts as done)
  - CLI: `youtube_publish.py privacy <video_id> <private|public>`, `youtube_publish.py delete <video_id>`
  - `publish <episode> --preview`: uploads with privacy `private`, logs `published.youtube_preview = {id, url, uploaded}` in episode.json (not `published.youtube`), needs no `--yes-publish` (a private upload is not publishing). Prints the id on the last line as `preview_id=<id>`.

- [ ] **Step 1: Write the failing tests** with `yt.http` patched (`unittest.mock.patch.object`):

```python
def test_video_exists_true_and_false()        # items [..] -> True; [] -> False
def test_set_privacy_sends_status_body()      # captured body["status"]["privacyStatus"] == "public", url has part=status
def test_delete_404_is_ok()                   # http raising the module's HTTP error with code 404 -> no exception
def test_preview_logs_youtube_preview_not_youtube()  # episode.json gets published.youtube_preview, not published.youtube
```
(`http()` currently calls `sys.exit` on errors; refactor it to raise `YTError(code, body)` and let `main()` print and exit, so tests and `delete` can catch 404.)

- [ ] **Step 2: Run** `python3 -m unittest pipeline.tests.test_youtube_ops -v` → FAIL
- [ ] **Step 3: Implement** the functions, the `YTError` refactor, the subcommands and `--preview`.
- [ ] **Step 4: Run** the new tests and `python3 -m unittest pipeline.tests.test_queue -v` → all OK; `pipeline/youtube_publish.py check` → `analytics: OK`
- [ ] **Step 5: Commit** `git commit -m "youtube: private previews, privacy switch, delete"` (+ attribution)

---

### Task 3: Credit caps for the loop

**Files:**
- Modify: `pipeline/reel/config.json` (add `"loop_credits": {"2026-11": 150, "default": 300}`)
- Modify: `pipeline/reel/budget.py`
- Test: `pipeline/tests/test_budget.py`

**Interfaces:**
- Consumes: the existing ledger `episodes/credits.json` (`entries[].date`, `episode`, `credits`)
- Produces:
  - `loop_cap(month: str) -> float` (`"2026-11"` → 150, other months → 300)
  - `loop_spent(month: str, loop_ids: set[str]) -> float` (sum of ledger entries in that month whose `episode` is in `loop_ids`)
  - `can_spend(amount: float, month: str, loop_ids: set[str]) -> tuple[bool, str]` (False if either the loop cap or the existing `credits_per_month` would be exceeded; the str says which)
  - CLI: `pipeline/.venv/bin/python -m pipeline.reel.budget loop-status` prints spent/cap for this month (loop ids = ids in the queue)

- [ ] **Step 1: Failing tests:** `test_cap_november_150`, `test_cap_december_300`, `test_can_spend_blocks_on_loop_cap` (spent 145 + 6 > 150 → False, "loop cap"), `test_can_spend_blocks_on_global_cap` (global 598 + 4 > 600 → False, "monthly cap")
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** in `budget.py`; `reel.py <ep> hero-plan` also calls `can_spend` when the episode id is in the queue.
- [ ] **Step 4: Run** → OK; `pipeline/.venv/bin/python pipeline/reel.py 008-krishna-vishwaroop check` still passes
- [ ] **Step 5: Commit** `git commit -m "budget: monthly loop credit cap"` (+ attribution)

---

### Task 4: Audio pool (popular, library from Pixabay, original)

**Files:**
- Create: `pipeline/loop/audio_pool.py`
- Modify: `.gitignore` is already ignoring `music-lab/`; verify `music-lab/pool/` stays ignored (`git check-ignore`)
- Modify: `ASSETS.md` (new "Loop audio" table header if absent)
- Test: `pipeline/tests/test_audio_pool.py`

**Interfaces:**
- Produces:
  - `POOL = LAB / "music-lab/pool"`; kinds `popular`, `library`, `original`
  - `list_tracks(kind: str) -> list[Path]` (audio files: .mp3 .wav .m4a .flac)
  - `fetch_library(url: str, title: str, artist: str, licence_url: str) -> Path` — refuses any host other than `pixabay.com`/`cdn.pixabay.com` (after redirects), any non-audio content type, files > 25 MB; saves to `pool/library/<slug>.<ext>`; appends a row `| date | title | artist | url | licence | loop library |` to `ASSETS.md`
  - `register_original(path: Path, job_id: str, prompt: str) -> Path` — copies a Higgsfield audio file into `pool/original/`, records job id and prompt in `ASSETS.md`
  - `use_count(path: Path) -> int` (from queue records' `cell.audio_file`) — the producer prefers least-used tracks
  - `flag(path: Path, kind: str, note: str) -> int` — kind in {"claim", "mute"}; appends to `music-lab/pool/flags.json`; returns the track's flag count
  - `blocked(path: Path) -> bool` — True at 2+ flags (spec §6.7: stop using that track); `list_tracks` excludes blocked tracks
  - CLI: `audio_pool.py list <kind>`, `fetch <url> --title --artist --licence`, `register <file> --job --prompt`, `flag <file> --kind claim|mute --note "…"`

- [ ] **Step 1: Failing tests:** `test_two_flags_block_track` (two `flag` calls → `blocked` True and `list_tracks` omits it), `test_fetch_refuses_other_hosts` (`https://example.com/a.mp3` → `PoolError`), `test_fetch_refuses_redirect_off_pixabay` (mocked redirect to another host → `PoolError`), `test_fetch_records_assets_row` (mocked 200 audio/mpeg → file saved and one ASSETS row with the URL), `test_list_ignores_non_audio`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** (urllib with a redirect handler that checks each hop's host).
- [ ] **Step 4: Run** → OK
- [ ] **Step 5: Commit** `git commit -m "loop: audio pool with Pixabay-only fetch and licence log"` (+ attribution)

---

### Task 5: Narration track for the reel pipeline

**Files:**
- Create: `pipeline/loop/narration.py`
- Test: `pipeline/tests/test_narration.py`

**Interfaces:**
- Consumes: voice picks produced by `engine/kk.sh <ep> hindi_takes` + `review_takes`/`fit_takes` (`voice/picks_hi.json`, clean takes under `voice/clean_hi/`), `timing_hi.json` (`{"lead_in", "total", "lines": [{"line", "start", "end", "pause_after"}]}`), `script/lines.json` (`{"hi": [...], "en": [...]}`)
- Produces:
  - `build_mix(ep: Path, bed: Path | None, bed_db: float = -18.0) -> Path` — writes `audio/narration_mix.wav` (voice at 0 dB, bed looped/trimmed to the voice length plus 1.5 s tail, ducked to `bed_db`, 0.4 s fade-out) with ffmpeg
  - `captions_from_timing(ep: Path, lang: str = "en") -> list[dict]` — `[{"text", "t0", "t1"}]` in the `edit.json` caption shape, one per line, `t1` = line end + min(pause_after, 0.3)
  - `wire_edit(ep: Path) -> None` — sets `edit.json` `song` = `audio/narration_mix.wav`, `song_in` = 0, `song_out` = mix duration, `captions` = `captions_from_timing(...)`, and the last bar ≤ mix duration, so the unchanged assembler produces the narrated reel
  - CLI: `narration.py mix <ep> [--bed FILE]`, `narration.py wire <ep>`

- [ ] **Step 1: Failing tests** (fixtures generated with ffmpeg `sine` sources in a temp episode): `test_mix_length_is_voice_plus_tail` (voice 10.0 s → mix 11.5 ± 0.05 s), `test_captions_follow_timing` (two lines → t0/t1 from timing.json), `test_wire_edit_passes_check` (after `wire_edit`, `pipeline/reel/shots.py` validation reports no "song" errors)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → OK
- [ ] **Step 5: Commit** `git commit -m "loop: narration mix and captions for narrated reels"` (+ attribution)

---

### Task 6: Experiment plan generator

**Files:**
- Create: `pipeline/loop/plan.py`
- Test: `pipeline/tests/test_plan.py`

**Interfaces:**
- Consumes: `queue.load()`; optional scores from `pipeline/review.py` (`score_all()` → `{video_id: float}`) and the features table to map videos to cells
- Produces:
  - `FORMATS = ("music", "narrated", "claim", "shloka", "dialogue")`
  - `AUDIO = {"music": ("popular", "library", "original"), "shloka": ("library", "original"), "dialogue": ("popular",), "narrated": ("bed",), "claim": ("bed",)}`
  - `CREDIT_EST = {"music": 10, "shloka": 4, "dialogue": 6, "narrated": 0, "claim": 0}`; audio `original` adds 3
  - Row (dict): `day` (YYYY-MM-DD), `slot` ("12:30"|"19:30"), `format`, `audio`, `topic_source`, `locked` (bool), `id` (filled when the producer takes it)
  - `fortnight(start: date, existing: list[dict], credits_left: float) -> list[dict]` — 28 rows; every (format, audio) cell and both slots reach n≥3 counting existing loop videos; each format alternates slots; total `CREDIT_EST` ≤ `credits_left` (drop the costliest surplus rows to 0-credit formats); no two consecutive rows share a format
  - `exploit_week(start: date, cell_scores: dict[tuple, float], credits_left: float) -> list[dict]` — 14 rows, ~70% (10 rows) from the top-scoring cells in proportion to score, 4 rows from cells with n<3 or the lowest n
  - `read(path) -> list[dict]` / `write(rows, path)` for `ideas/experiment_plan.md` as a markdown table; rows marked `locked` in the file are preserved by `write` when regenerating
  - `next_row(rows, queue_records) -> dict | None` — earliest row without an `id`
  - CLI: `plan.py new-fortnight [--start DATE]`, `plan.py next-week`, `plan.py show`, `plan.py next`

- [ ] **Step 1: Failing tests:** `test_fortnight_has_28_rows`, `test_every_cell_reaches_three` (the 8 (format, audio) cells in `AUDIO` each ≥ 3; each slot ≥ 12), `test_budget_respected` (credits_left 150 → sum of `CREDIT_EST` ≤ 150; credits_left 40 → the costliest rows become `narrated`/`claim`), `test_no_back_to_back_format`, `test_locked_rows_survive_rewrite`, `test_exploit_week_split` (10 rows from top cells, 4 exploratory)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** with a greedy balancer: repeatedly pick the cell with the largest remaining deficit whose format differs from the previous row and whose cost fits the budget; assign slots alternating per format.
- [ ] **Step 4: Run** → OK
- [ ] **Step 5: Commit** `git commit -m "loop: experiment plan generator (fortnight + 70/30 weeks)"` (+ attribution)

---

### Task 7: Follower snapshots and the weekly scoreboard

**Files:**
- Modify: `pipeline/analytics.py` (table `followers(day TEXT, platform TEXT, count INTEGER, PRIMARY KEY(day, platform))`; command `followers pull`)
- Modify: `pipeline/review.py` (new first section "Scoreboard"; per-cell table)
- Modify: `pipeline/loop/run.sh` (`pull` job runs `analytics.py followers pull`; it is a no-op if today's rows exist)
- Test: `pipeline/tests/test_scoreboard.py`

**Interfaces:**
- Produces:
  - `analytics.followers_pull(con) -> dict[str, int]` (YouTube `channels?part=statistics&mine=true` `subscriberCount`; Instagram `/<ig_user_id>?fields=followers_count`)
  - `review.week_over_week(rows: list[tuple[str, str, int]], today: date) -> dict[str, dict]` → per platform `{"now", "week_ago", "delta", "pct"}`; missing week-ago data → `delta` None
  - `review.views_wow(con, today) -> dict[str, dict]` (sum of daily views per platform for the last 7 days vs the 7 before)
  - `review.cell_table(con) -> list[dict]` (format × audio × slot: n, median score, followers gained per 1k views)

- [ ] **Step 1: Failing tests:** `test_wow_delta` (rows 1000 → 1100 → delta 100, pct 10.0), `test_wow_missing_week_ago` (delta None), `test_followers_pull_idempotent` (second call same day inserts nothing; HTTP mocked)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**; the pack's Scoreboard section shows followers and views WoW per platform first, then the cell table.
- [ ] **Step 4: Run** → OK; `python3 pipeline/analytics.py followers pull` live → two counts printed; `python3 pipeline/review.py pack --no-record` shows "Scoreboard" first
- [ ] **Step 5: Commit** `git commit -m "loop: follower snapshots and weekly scoreboard"` (+ attribution)

---

### Task 8: Publisher (slots, late rule, Instagram hand-off)

**Files:**
- Create: `pipeline/loop/publish.py`
- Test: `pipeline/tests/test_publish.py`

**Interfaces:**
- Consumes: `queue.due`, `queue.transition`, `queue.next_free_slot`; `youtube_publish.set_privacy`; `instagram_publish` publish flow (`cmd_publish` refactored to `publish_reel(ep: Path, video: str) -> dict` returning `{media_id, permalink}`); `inbox.add`
- Produces:
  - `run_slot(now: datetime) -> str` — one of `"posted"`, `"handed_off"`, `"nothing_due"`, `"moved"`, `"ig_retry_pending"`, `"failed"`
  - Behaviour:
    1. Approved records whose slot is older than `now - LATE_GRACE` and not posted → moved to `next_free_slot`, INBOX info line; result `"moved"`.
    2. `due(now)` record: YouTube `set_privacy(yt_id, "public")` unless `yt_public` already true (store `yt_public=True` immediately after success).
    3. `ig_mode == "api"`: `publish_reel(ep, "reel_with_song.mp4")`; on success status `posted`, `posted_at`, `ig_media_id`; on failure set `ig_retry=1` and leave status `approved` (result `"ig_retry_pending"`); a second failure at the next slot run → status `failed`, INBOX failure.
    4. `ig_mode == "manual"`: status `posted` for YouTube, `ig_manual_pending=True`; INBOX decision "Post on Instagram by hand: <title> — file <ep>/out/final/reel_SILENT.mp4, song <title> from <start>"; macOS notification; result `"handed_off"`.
  - CLI: `publish.py slot` (uses now), `publish.py slot --dry-run` (prints what it would do)

- [ ] **Step 1: Failing tests** (YouTube/IG calls mocked):

```python
def test_posts_due_api_record()                 # -> "posted"; set_privacy called once with "public"
def test_ig_failure_then_retry_without_youtube_again()
    # 1st run: IG raises -> "ig_retry_pending", set_privacy called once
    # 2nd run: IG ok -> "posted", set_privacy NOT called again
def test_second_ig_failure_marks_failed_and_inbox()
def test_late_by_more_than_grace_moves_to_next_slot()
    # slot 12:30, now 15:10 -> "moved", new slot 19:30 same day (if free)
def test_manual_mode_hands_off()                # -> "handed_off", INBOX text contains "reel_SILENT.mp4"
def test_nothing_due()                          # -> "nothing_due"
```
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** `publish.py` and the `publish_reel` refactor in `instagram_publish.py` (existing CLI behaviour unchanged).
- [ ] **Step 4: Run** → OK; `pipeline/instagram_publish.py publish 008-krishna-vishwaroop --dry-run` still prints the dry run
- [ ] **Step 5: Commit** `git commit -m "loop: slot publisher with late rule and IG hand-off"` (+ attribution)

---

### Task 9: Daily ask (approval request)

**Files:**
- Create: `pipeline/loop/ask.py`
- Test: `pipeline/tests/test_ask.py`

**Interfaces:**
- Consumes: `queue.load`, `inbox.add` (kind `decision`, fires the macOS notification)
- Produces:
  - `compose(records: list[dict]) -> str | None` — None if nothing is `preview_ready`; else one message: per video `id · format/audio · title · https://youtu.be/<yt_id> (private) · IG: api|by hand · credits`, then the reply forms: `approve <id> …` / `reject <id> --reason "…"` (as `python3 pipeline/loop/queue.py …` commands Satyam's session runs)
  - `run(now) -> bool` — adds the INBOX decision once per day per set of ids (no duplicate when the set is unchanged)
  - CLI: `ask.py` (run), `ask.py --print`

- [ ] **Step 1: Failing tests:** `test_compose_none_when_empty`, `test_compose_lists_private_links` (contains `https://youtu.be/abc` and `(private)`), `test_run_no_duplicate_same_set`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → OK
- [ ] **Step 5: Commit** `git commit -m "loop: daily approval request"` (+ attribution)

---

### Task 10: Producer (headless Claude + helper)

**Files:**
- Create: `pipeline/loop/produce.py` (deterministic helper the producer calls)
- Create: `pipeline/loop/produce_prompt.md` (instructions only, no data)
- Modify: `pipeline/loop/run.sh` (job `produce`)
- Test: `pipeline/tests/test_produce.py`

**Interfaces:**
- Consumes: `plan.next_row`, `queue.add/transition`, `budget.can_spend`, `audio_pool.*`, `narration.*`, `youtube_publish publish --preview`
- Produces:
  - `produce.py start` → takes `plan.next_row`; if the buffer already holds 4 (`preview_ready`+`approved`) or it is past 06:00 IST, prints `STOP <reason>` and exits 0; else picks the episode number (next free `NNN` in `episodes/`), scaffolds with `pipeline/new_reel.sh` (music/shloka/dialogue) or `pipeline/new_episode.sh <slug> short` (narrated/claim), adds the queue record (`ig_mode` = "manual" iff audio == "popular"), status `producing`, prints `START <id> <format> <audio> <topic_source>`
  - `produce.py finish <id>` → requires `out/final/reel_with_song.mp4` and `out/package/youtube.md` + `caption_instagram.txt`; runs the frame check list (writes `out/qa/frames.png`, a contact sheet of 1 frame/s, for Claude to inspect); uploads with `youtube_publish.py publish <id> --video reel_with_song.mp4 --preview`; sets `yt_id`, status `preview_ready`; prints `READY <id> <yt_id>`
  - `produce.py fail <id> --reason "…"` → status `failed`, INBOX failure
  - `produce_prompt.md`: loop until `produce.py start` says STOP: for each START, follow the kathakaar-research skill steps 0b-4 for the row's topic source (Opus-quality research with citations into `script/RESEARCH.md`, pick the best storyline yourself, never invent beats), write the script/shots/edit per format (music: `pipeline/REEL_PIPELINE.md`; narrated/claim: `engine/kk.sh <ep> hindi_takes --takes 3`, `review_takes`, `fit_takes`, then `narration.py mix/wire`), stills via `reel.py stills`, hero clips only after `budget.can_spend` and `reel.py hero-plan`, original music via Higgsfield `generate_audio` + `audio_pool.py register`, library via `audio_pool.py fetch` (Pixabay only), `reel.py motion/finish/assemble`, package files, inspect `out/qa/frames.png` against the content rules (Ravana and Sita never touching; no humour about the divine; no style name in copy), then `produce.py finish` or `produce.py fail`. Per-video timeout 75 min.
  - `run.sh produce`: `caffeinate -i -s` around `claude -p "$(cat pipeline/loop/produce_prompt.md)" --model claude-opus-5-5 --permission-mode dontAsk --allowedTools <list> --disallowedTools "Bash(git *)" "Bash(rm *)" "Bash(sqlite3 *)" "Bash(curl *)" "Read(secrets/**)" --no-session-persistence --output-format text`, alarm at 06:00 IST; allowlist: Read, Glob, Grep, WebSearch, WebFetch, `Edit(episodes/**)`, `Edit(ideas/**)`, `Bash(pipeline/.venv/bin/python pipeline/reel.py *)`, `Bash(pipeline/sources_search.py *)`, `Bash(engine/kk.sh *)`, `Bash(pipeline/new_reel.sh *)`, `Bash(pipeline/new_episode.sh *)`, `Bash(python3 pipeline/loop/produce.py *)`, `Bash(python3 pipeline/loop/narration.py *)`, `Bash(python3 pipeline/loop/audio_pool.py *)`, `Bash(python3 pipeline/loop/plan.py show*)`, `Bash(python3 pipeline/loop/inbox.py *)`, `Bash(ffmpeg *)`, `Bash(ffprobe *)`, and the Higgsfield tools `mcp__claude_ai_Higgsfield__generate_video`, `__generate_audio`, `__media_upload`, `__media_confirm`, `__jobs_wait`, `__show_generation_by_ids`, `__balance`

- [ ] **Step 1: Failing tests:** `test_start_stops_when_buffer_full` (4 preview_ready → `STOP buffer`), `test_start_stops_after_six` (now 06:05 IST → `STOP time`), `test_start_sets_manual_for_popular` (row audio popular → record `ig_mode == "manual"`), `test_finish_requires_package` (missing caption file → error, status unchanged)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** `produce.py`, write `produce_prompt.md`, add the `produce` job to `run.sh`.
- [ ] **Step 4: Run** tests → OK. Then a real rehearsal: put one 0-credit `narrated` row in the plan, run `pipeline/loop/run.sh produce` by hand (it stops after the buffer target or 06:00; for the rehearsal set `LOOP_MAX_VIDEOS=1`), confirm: queue record `preview_ready`, a private YouTube video exists (`youtube_publish.py` `video_exists` True, privacy private), `out/qa/frames.png` exists, no files changed outside `episodes/`, `ideas/`, `cache/`, `music-lab/pool/` (`git status`).
- [ ] **Step 5: Commit** `git commit -m "loop: overnight producer"` (+ attribution)

---

### Task 11: Weekly review drives the plan; rejections feed learnings

**Files:**
- Modify: `pipeline/loop/review_prompt.md` (steps: read Scoreboard; append the week's rejections to `ideas/LEARNINGS.md` "## Rejections" with ids and reasons; on the Sunday that ends the fortnight run `plan.py next-week`, otherwise `plan.py new-fortnight` only if no plan exists; never touch `locked` rows)
- Modify: `pipeline/loop/run.sh` (review allowlist adds `Bash(python3 pipeline/loop/plan.py *)`, `Bash(python3 pipeline/loop/queue.py list*)`)
- Modify: `pipeline/loop/queue.py` (`rejections_since(day: date) -> list[dict]`)
- Test: `pipeline/tests/test_queue.py` (`test_rejections_since`)

- [ ] **Step 1: Failing test** `test_rejections_since` (two rejected records, one before the date → one returned)
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** and update the prompt/allowlist.
- [ ] **Step 4: Run** tests → OK; `pipeline/loop/run.sh review` by hand → INBOX "Weekly review ready" line, LEARNINGS has a "Rejections" section (empty is fine), `ideas/experiment_plan.md` exists
- [ ] **Step 5: Commit** `git commit -m "loop: review updates plan and learns from rejections"` (+ attribution)

---

### Task 12: Schedule, docs, end-to-end dry run

**Files:**
- Modify: `pipeline/loop/install.sh` (jobs `produce` 01:00 daily, `ask` 09:00 daily, `publish` 12:30 and 19:30 daily as `com.kathakaar.publish-1`/`-2` calling `run.sh publish`)
- Modify: `pipeline/loop/run.sh` (jobs `ask` → `python3 pipeline/loop/ask.py`, `publish` → `python3 pipeline/loop/publish.py slot`)
- Modify: `pipeline/loop/README.md` (daily rhythm table from spec §6.1; how Satyam approves from Remote Control: "approve <id>" → `queue.py approve`; how to pause: `uninstall.sh` or `touch cache/loop/PAUSE`, which every new job honours by exiting 0)
- Modify: `PIPELINE.md` (one paragraph: the loop replaces per-episode Gates 1-4 with self-checks for loop videos; Gate 5 is the daily approval)

- [ ] **Step 1:** `bash -n pipeline/loop/run.sh` and `zsh -n pipeline/loop/install.sh` → no output
- [ ] **Step 2:** `pipeline/loop/install.sh --dry-run` → 8 plists printed; `plutil -lint` on each → OK
- [ ] **Step 3:** End-to-end dry run with the rehearsal video from Task 10: `python3 pipeline/loop/ask.py --print` shows its private link; `python3 pipeline/loop/queue.py approve <id>` assigns the next slot; `python3 pipeline/loop/publish.py slot --dry-run` at that slot time (pass `--now`) prints "would set public … would post IG"; `touch cache/loop/PAUSE` → `run.sh publish` logs "paused" and exits 0
- [ ] **Step 4:** Full test suite: `python3 -m unittest discover -s pipeline/tests -v` → all OK
- [ ] **Step 5: Commit** `git commit -m "loop: schedule produce/ask/publish jobs"` (+ attribution). Installing the new launchd jobs (`pipeline/loop/install.sh`) waits for Satyam's go.
