# Feedback-loop automation (Phase 5)

Runs the existing loop scripts on a schedule via launchd. Code only: no metrics or comments live here.

| job | schedule (Mac local, IST) | does |
|---|---|---|
| `pull` | hourly | `analytics.py yt pull` (hook for Instagram pull left in `run.sh`) |
| `trends` | daily 07:30 | `trends.py scan` + `digest` (already scanned today = success; a digest with a filled "Fit" section is not regenerated) |
| `ig-refresh` | Monday 08:00 | `instagram_publish.py refresh` if `secrets/instagram.json` exists, else a logged skip |
| `review` | Sunday 09:00 | `review.py pack`, then the headless Claude review below |

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
pipeline/loop/run.sh pull            # run any job by hand (pull|trends|ig-refresh|review|status)
```

## Headless review sandbox
`review_prompt.md` (instructions only) is passed to `claude -p --model claude-sonnet-5-5 --permission-mode dontAsk`,
so anything not allow-listed is denied without prompting. Allowed: Read, Glob, Grep; Bash only for
`python3 pipeline/features.py *`, `analytics.py yt map*|status*`, `review.py *`, `trends.py digest*`,
`pipeline/loop/inbox.py *`; Edit (which covers Write) only under `ideas/**`. Denied: raw `sqlite3` (its `.shell` dot-command runs arbitrary commands; comments are untrusted input), curl, git, rm, web tools, reading `secrets/`.
WebFetch, WebSearch, git, rm and MCP servers are off. It never publishes, edits code or commits. 30 min timeout.
Note: `features.py`, `analytics.py yt map --set` and `review.py` write under `cache/` and `episodes/` by design.
