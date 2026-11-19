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
`reseal` (failed -> preview_ready) when the private preview still exists: it re-records the digests of the episode as it
is now and clears the slot and retry state, so the video needs a fresh approve; `requeue` (failed -> planned) only for
a record that never got a preview (it refuses with "use reseal" otherwise).
`rejected` is the archive: the CLI `reject` then deletes the private YouTube preview (best effort; done = `yt_deleted:
true`, a failure leaves an INBOX line "could not delete private preview <id>"). The episode folder stays on disk.
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

Edited the caption (or the video, title, song) after approving? The publisher refuses it (the digests no longer match)
and marks it `failed`. Run `python3 pipeline/loop/vqueue.py reseal <id>`, re-watch, then approve again.

## Pause and resume
```
touch cache/loop/PAUSE     # every job except `status` logs "paused" and exits 0
rm cache/loop/PAUSE        # resume
pipeline/loop/uninstall.sh # or remove the launchd agents altogether
```
`run.sh status` prints PAUSED while the file exists. An already-running job is not interrupted.

## Security notes
- The producer runs headless Claude in `--permission-mode dontAsk` inside a Bash sandbox (seatbelt): reads limited to
  the lab's working folders, writes denied on `pipeline/`, `engine/`, `brand/`, `secrets/`, `.git`; network limited to an
  allowlist of hosts (Pixabay, Higgsfield media, Hugging Face); no git, no raw sqlite3, no reading `secrets/`, no posting.
- The review job is allowlisted the same way (see above). Comments and web text are untrusted input.
- Only `publish.py` ever makes a video public, and only for a record `approve`d by Satyam; approve checks the private
  preview still exists. The queue, plan, metrics and approvals live in git-ignored `cache/` and `ideas/`.

## Installing the schedule
Installing needs Satyam's go: `pipeline/loop/install.sh --dry-run` first, then `pipeline/loop/install.sh`.
The plists point at the checkout the script is run from (`$LAB`), so run install.sh from the MAIN checkout
(`/Users/satyam/kathakaar-lab`) after the loop branch is merged, not from a worktree. Re-running is safe (agents are
booted out first). `uninstall.sh` removes all eight agents.
