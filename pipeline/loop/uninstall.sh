#!/bin/zsh
# Boot out and remove the Kathakaar launchd agents. Logs and status in cache/loop are kept.
for j in pull trends ig-refresh review; do
  launchctl bootout "gui/$(id -u)/com.kathakaar.$j" 2>/dev/null && echo "booted out com.kathakaar.$j"
  rm -f "$HOME/Library/LaunchAgents/com.kathakaar.$j.plist"
done
echo "Uninstalled."
