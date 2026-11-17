#!/bin/zsh
# Install the launchd agents for the Kathakaar loop (~/Library/LaunchAgents/com.kathakaar.<job>.plist).
#
#   pipeline/loop/install.sh [--dry-run]     --dry-run prints the plists and installs nothing
#
# Schedule (Mac local time; this Mac is IST): pull hourly | trends daily 07:30 | ig-refresh Monday 08:00 |
# review Sunday 09:00. launchd runs a calendar job that was missed while the Mac slept ONCE on wake; while the Mac is
# powered off nothing runs. Already-loaded agents are booted out first, so re-running is safe.
set -eu
LAB="${0:A:h:h:h}"
AGENTS="$HOME/Library/LaunchAgents"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

plist() {  # job, schedule-xml
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
    <string>$LAB/pipeline/loop/run.sh $1</string>
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
JOBS=(pull trends ig-refresh review)

if [ $DRY -eq 1 ]; then
  for j in $JOBS; do echo "### $AGENTS/com.kathakaar.$j.plist"; plist $j "$SCHED[$j]"; echo; done
  exit 0
fi

mkdir -p "$AGENTS" "$LAB/cache/loop/logs"
for j in $JOBS; do
  f="$AGENTS/com.kathakaar.$j.plist"
  launchctl bootout "gui/$(id -u)/com.kathakaar.$j" 2>/dev/null || true
  plist $j "$SCHED[$j]" > "$f"
  plutil -lint "$f" >/dev/null
  launchctl bootstrap "gui/$(id -u)" "$f"
  echo "installed com.kathakaar.$j"
done
echo "Done. Check with: pipeline/loop/run.sh status"
