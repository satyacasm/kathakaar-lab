#!/bin/zsh
# Install the launchd agents for the Kathakaar loop (~/Library/LaunchAgents/com.kathakaar.<job>.plist).
#
#   pipeline/loop/install.sh [--dry-run]     --dry-run prints the plists and installs nothing
#
# Schedule (Mac local time; this Mac is IST): pull hourly | trends daily 07:30 | ig-refresh Monday 08:00 |
# review Sunday 09:00 | produce daily 01:00 | ask daily 09:00 | publish-1 daily 12:30 | publish-2 daily 19:30
# (both publish agents run `run.sh publish`). launchd runs a calendar job that was missed while the Mac slept ONCE on wake; while the Mac is
# powered off nothing runs. Already-loaded agents are booted out first, so re-running is safe.
#
# Rehearsal gate: the new loop jobs (produce, ask, publish-1, publish-2) are installed only once cache/loop/REHEARSAL_OK
# exists, i.e. after a supervised `LOOP_WINDOW_OVERRIDE=1 LOOP_MAX_VIDEOS=1 pipeline/loop/run.sh produce` passed (see
# pipeline/loop/README.md, "Before installing the loop jobs"). Without it only pull, trends, ig-refresh and review are
# installed. --dry-run always prints all eight.
set -eu
LAB="${0:A:h:h:h}"
AGENTS="$HOME/Library/LaunchAgents"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

plist() {  # label, schedule-xml [, run.sh job (default = label)]
  cat <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.kathakaar.$1</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>$LAB/pipeline/loop/run.sh ${3:-$1}</string>
  </array>
  <key>WorkingDirectory</key><string>$LAB</string>
$2
  <key>StandardOutPath</key><string>$LAB/cache/loop/logs/launchd-$1.log</string>
  <key>StandardErrorPath</key><string>$LAB/cache/loop/logs/launchd-$1.log</string>
</dict>
</plist>
PL
}

cal() {  # [weekday] hour minute  (weekday 0=Sunday)
  local wd=""; [ $# -eq 3 ] && { wd="<key>Weekday</key><integer>$1</integer>"; shift; }
  echo "  <key>StartCalendarInterval</key><dict>$wd<key>Hour</key><integer>$1</integer><key>Minute</key><integer>$2</integer></dict>"
}

typeset -A SCHED
SCHED[pull]='  <key>StartInterval</key><integer>3600</integer>'
SCHED[trends]="$(cal 7 30)"
SCHED[ig-refresh]="$(cal 1 8 0)"
SCHED[review]="$(cal 0 9 0)"
SCHED[produce]="$(cal 1 0)"
SCHED[ask]="$(cal 9 0)"
SCHED[publish-1]="$(cal 12 30)"
SCHED[publish-2]="$(cal 19 30)"
JOBS=(pull trends ig-refresh review produce ask publish-1 publish-2)
runjob() { case "$1" in publish-*) echo publish ;; *) echo "$1" ;; esac; }

if [ $DRY -eq 1 ]; then
  for j in $JOBS; do echo "### $AGENTS/com.kathakaar.$j.plist"; plist $j "$SCHED[$j]" "$(runjob $j)"; echo; done
  exit 0
fi

mkdir -p "$AGENTS" "$LAB/cache/loop/logs"
if [ ! -e "$LAB/cache/loop/REHEARSAL_OK" ]; then
  echo "NOT installing produce, ask, publish-1, publish-2: no cache/loop/REHEARSAL_OK (the supervised producer"
  echo "rehearsal has not passed yet). Installing only the original jobs; see pipeline/loop/README.md."
  JOBS=(pull trends ig-refresh review)
fi
for j in $JOBS; do
  f="$AGENTS/com.kathakaar.$j.plist"
  launchctl bootout "gui/$(id -u)/com.kathakaar.$j" 2>/dev/null || true
  plist $j "$SCHED[$j]" "$(runjob $j)" > "$f"
  plutil -lint "$f" >/dev/null
  launchctl bootstrap "gui/$(id -u)" "$f"
  echo "installed com.kathakaar.$j"
done
echo "Done. Check with: pipeline/loop/run.sh status"
