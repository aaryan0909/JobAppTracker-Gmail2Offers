#!/bin/bash
# Load (or reload) the Career Board launchd agents: always-on local server + periodic scan.
UID_=$(id -u)
LA="$HOME/Library/LaunchAgents"
for L in com.aaryan.careerboard.server com.aaryan.careerboard.scan; do
  launchctl bootout  "gui/$UID_/$L" 2>/dev/null
  launchctl bootstrap "gui/$UID_" "$LA/$L.plist" && echo "loaded $L" || echo "FAILED $L"
done
launchctl enable "gui/$UID_/com.aaryan.careerboard.server" 2>/dev/null
launchctl enable "gui/$UID_/com.aaryan.careerboard.scan" 2>/dev/null
echo "--- status ---"
launchctl list | grep careerboard || echo "(none listed yet)"
