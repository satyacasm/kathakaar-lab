# Feedback-loop automation (Phase 5)

Runs the existing loop scripts on a schedule via launchd. Code only: no metrics or comments live here.

| job | schedule (Mac local, IST) | does |
|---|---|---|
| `pull` | hourly | `analytics.py yt pull` (hook for Instagram pull left in `run.sh`) |
| `trends` | daily 07:30 | `trends.py scan` + `digest` (already scanned today = success; a digest with a filled "Fit" section is not regenerated) |
| `ig-refresh` | Monday 08:00 | `instagram_publish.py refresh` if `secrets/instagram.json` exists, else a logged skip |
| `review` | Sunday 09:00 | `review.py pack`, then the headless Claude review below |
| `produce` | daily 01:00 | headless Claude (sandboxed) makes videos until the buffer holds 4; stops at 06:00 IST or the credit cap; uploads each privately |
| `ask` | daily 09:00 | if videos await approval: macOS notification + INBOX decision with their private links |
| `publish` | daily 12:30 and 19:30 (`com.kathakaar.publish-1` / `-2`, both run `run.sh publish`) | posts the approved video whose slot is due: YouTube public + Instagram Reel (popular audio: Instagram handed to Satyam) |

launchd runs a calendar job missed while the Mac slept once on wake; nothing runs while it is off.

## Where things are
- Logs: `cache/loop/logs/<job>-<YYYY-MM>.log` (launchd's own stdout: `launchd-<job>.log`)
- Status: `cache/loop/status.json` (job -> last_run, exit, duration_s); `run.sh status` also lists loaded agents
- Locks: `cache/loop/locks/<job>.lock` (stale after 3 h; a held lock = logged skip, exit 0)
- INBOX: `ideas/INBOX.md`. Failures and decisions land under "## Open" and fire a macOS notification. Tick `[ ]` to `[x]`.
  `python3 pipeline/loop/inbox.py add "text" --kind decision|failure|info`, `inbox.py list`.

## Install / run
```
pipeline/loop/install.sh --dry-run   # print the plists
pipeline/loop/install.sh             # write ~/Library/LaunchAgents/com.kathakaar.<job>.plist and bootstrap them
pipeline/loop/uninstall.sh
pipeline/loop/run.sh pull            # run any job by hand (pull|trends|ig-refresh|review|produce|ask|publish|status)
```

## Headless review sandbox
`review_prompt.md` (instructions only) is passed to `claude -p --model claude-sonnet-5-5 --permission-mode dontAsk`,
so anything not allow-listed is denied without prompting. Allowed: Read, Glob, Grep; Bash only for
`python3 pipeline/features.py *`, `analytics.py yt map*|status*`, `review.py *`, `trends.py digest*`,
`pipeline/loop/inbox.py *`; Edit (which covers Write) only under `ideas/**`. Denied: raw `sqlite3` (its `.shell` dot-command runs arbitrary commands; comments are untrusted input), curl, git, rm, web tools, reading `secrets/`.
WebFetch, WebSearch, git, rm and MCP servers are off. It never publishes, edits code or commits. 30 min timeout.
Note: `features.py`, `analytics.py yt map --set` and `review.py` write under `cache/` and `episodes/` by design.

## Queue
`pipeline/loop/vqueue.py` (not `queue.py`, which would shadow the stdlib module) holds every video's state in
`cache/loop/queue.json` (git-ignored; atomic writes under an flock on `queue.json.lock`).

Statuses: `planned -> producing -> preview_ready -> approved -> posted`, with `rejected` (from preview_ready) and
`failed` (from planned/producing/approved). Any other jump raises an error. Recovery from `failed`:
`reseal` (failed -> preview_ready) only when the private preview still exists, the record is not already public on
YouTube (`yt_public`: use the Instagram retry path), and the video files (`reel_with_song.mp4`, `reel_SILENT.mp4`),
`youtube.md` and the titles (`title_en`, `title_hi`) are unchanged since the preview was uploaded. Only Instagram-side
edits (`caption_instagram.txt`, the song fields of episode.json) can be resealed; anything else needs a new preview. Reseal re-records the digests and clears the slot and retry state, so the video needs a fresh approve; `requeue` (failed -> planned) only for
a record that never got a preview (it refuses with "use reseal" otherwise).
`rejected` is the archive: the CLI `reject` then deletes the private YouTube preview (best effort; done = `yt_deleted:
true`, a failure leaves an INBOX line "could not delete private preview <id>"). It deletes only while YouTube reports
the video `private` and the record is not `yt_public`; otherwise INBOX "refused to delete <id>: not private". The episode folder stays on disk.
Slots are 12:30 and 19:30 Asia/Kolkata; `approve` gives each video the next free slot and refuses unless the
private YouTube preview still exists. A video later than 2 h past its slot is no longer due. Nothing is public
without an approve.

```
python3 pipeline/loop/vqueue.py list [--all]
python3 pipeline/loop/vqueue.py show <id>
python3 pipeline/loop/vqueue.py approve <id>...      # prints each slot in IST
python3 pipeline/loop/vqueue.py reject <id> --reason "slow hook"   # also deletes the private preview
python3 pipeline/loop/vqueue.py reseal <id>          # failed, preview still there: back to preview_ready
python3 pipeline/loop/vqueue.py requeue <id>         # failed, never uploaded: back to planned
```

## The daily rhythm (IST)
```
07:30  trends    trends.py scan + digest
hourly pull      analytics yt + ig pull, daily follower snapshot
01:00  produce   plan -> research -> script -> stills -> hero/audio -> assemble -> private YouTube upload (until 4 buffered)
09:00  ask       notification + INBOX decision listing the videos that await approval
any    approve   Satyam, from his phone in a Remote Control session
12:30  publish   slot 1: oldest approved video -> YouTube public + Instagram Reel
19:30  publish   slot 2: same
Sun 09 review    weekly scoreboard + plan update
```

## Approving from Remote Control
The 09:00 INBOX decision lists each video with its private YouTube link. Watch them, then in any Claude Code
Remote Control session in this repo say "approve 1 and 2" or "reject 3: slow hook". Claude runs, from the lab:
```
python3 pipeline/loop/vqueue.py approve <id> [<id>...]      # prints each slot (IST); refuses if the private preview is gone
python3 pipeline/loop/vqueue.py reject <id> --reason "slow hook"   # reason feeds the next review
```
Nothing becomes public without an approve for that video: no approval means the slot is skipped. A video not posted
within 2 h of its slot moves to the next free slot.

Edited the Instagram caption (or the song credit) after approving? The publisher refuses it (the digests no longer
match) and marks it `failed`. Run `python3 pipeline/loop/vqueue.py reseal <id>`, re-check, then approve again.
Changed the video, `youtube.md` or a title? reseal refuses: the private preview is the old upload, so it needs a new
preview; the record stays `failed` (today `produce.py finish` only takes a `producing` record, so this means producing
the episode again).

## Pause and resume
```
touch cache/loop/PAUSE     # every job except `status` logs "paused" and exits 0
rm cache/loop/PAUSE        # resume
pipeline/loop/uninstall.sh # or remove the launchd agents altogether
```
`run.sh status` prints PAUSED while the file exists. An already-running job is not interrupted.

## Security notes
- The producer runs headless Claude in `--permission-mode dontAsk` inside a Bash sandbox (seatbelt), configured in
  `pipeline/loop/sandbox_settings.py`: the home folder is read-denied; the lab (the working directory: Python's
  getcwd() must open it) and the uv Python, Hugging Face model and font folders are allowed back; inside the lab
  `secrets/`, `.git`, `.claude`, `.remember`, `downloads/`, `archive/` are denied again (a deny inside an allow wins).
  `secrets/`, `~/.ssh` and the Hugging Face token are also `credentials.files` denies, which no allowRead re-opens.
  Writes denied on `pipeline/`, `engine/`, `brand/`, `sources/`, `secrets/`, `.git`; network limited to an allowlist
  of hosts (Pixabay, Higgsfield media, Hugging Face); no git, no raw sqlite3, no posting.
- Metal (MLX, mflux) cannot work inside the seatbelt sandbox (no GPU IOKit access, not configurable), so the two GPU
  stages run outside it as `excludedCommands`: `produce.py voice ...` and `reel.py <id> stills [--only N|--force]`,
  next to `produce.py finish ...` (secrets + YouTube). They are fixed code the producer cannot edit and still need
  their allowlist entry; any other command, a compound with `cd`, `$(...)` or a redirect stays sandboxed. Run the
  stills stage on its own: `reel.py <id> all` would run stills inside the sandbox and fail.
- The review job is allowlisted the same way (see above). Comments and web text are untrusted input.
- Residual risk (accepted): WebFetch is unrestricted for the producer (research needs arbitrary sites) and it can read
  `ideas/` (LEARNINGS, the INBOX with private preview ids). A prompt injection in a fetched page could make a run send
  that text to a URL. Nothing there is a credential, and a preview id alone does not make a video public.
- Known gap: copyright watch (Content ID claims on the private previews and the public videos) is not wired into the
  loop yet; check YouTube Studio by hand before approving a popular-audio video.
- Only `publish.py` ever makes a video public, and only for a record `approve`d by Satyam; approve checks the private
  preview still exists. The queue, plan, metrics and approvals live in git-ignored `cache/` and `ideas/`.

## Before installing the loop jobs: supervised rehearsal
The headless producer has NOT yet run for real. Until one supervised rehearsal has passed, `install.sh` installs only
the original four jobs (pull, trends, ig-refresh, review) and refuses produce, ask, publish-1 and publish-2 (it checks
for `cache/loop/REHEARSAL_OK`; `--dry-run` still prints all eight). Rehearse in the daytime, watching:
```
LOOP_WINDOW_OVERRIDE=1 LOOP_MAX_VIDEOS=1 pipeline/loop/run.sh produce
```
It must verify, from the log (`cache/loop/logs/produce-<YYYY-MM>.log`) and the result:
1. The Bash sandbox (seatbelt) lets the stages work: mflux/MLX stills and the voice venv (Metal, both run as
   excludedCommands), ffmpeg/onnxruntime motion inside the sandbox; nothing needs a path outside the allowRead list.
   Probed 2026-11-19 (cache/loop/sandbox-fix-report.md): every helper starts from the lab root, a real stills run
   used Metal, secrets/ and ~/.ssh are unreadable.
2. `--permission-mode dontAsk` read scope: every Read the prompt needs is allowed (no silent denials in the log).
3. `excludedCommands` matches `produce.py finish ...` even when Claude writes it as part of a compound command
   (`cd ... && python3 ...`); the private upload succeeds.
4. The Higgsfield MCP tool names in the allowlist are the ones the connector really exposes (a wrong name = denied).
5. The Higgsfield upload/result hosts actually used, read from the sandbox network log: then replace the broad
   `*.amazonaws.com`, `*.cloudfront.net`, `*.r2.cloudflarestorage.com`, `storage.googleapis.com` entries in
   `ALLOWED_DOMAINS` (pipeline/loop/sandbox_settings.py) with those exact hosts.
6. The video ends `preview_ready` with a private YouTube link, nothing public, credits recorded.
When all pass: `touch cache/loop/REHEARSAL_OK`, then install.

## Installing the schedule
Installing needs Satyam's go: `pipeline/loop/install.sh --dry-run` first, then `pipeline/loop/install.sh` (the loop
jobs only after the rehearsal above).
The plists point at the checkout the script is run from (`$LAB`), so run install.sh from the MAIN checkout
(`/Users/satyam/kathakaar-lab`) after the loop branch is merged, not from a worktree. Re-running is safe (agents are
booted out first). `uninstall.sh` removes all eight agents.
