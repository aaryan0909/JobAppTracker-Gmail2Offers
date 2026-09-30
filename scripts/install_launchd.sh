#!/bin/bash
# Install (or reinstall) the Career Board launchd agents: always-on local
# server + hourly Gmail scan. Fills the plist templates in launchd/ with
# the current user's HOME and this repo's path. macOS only.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LA="$HOME/Library/LaunchAgents"
UID_=$(id -u)
mkdir -p "$LA" "$REPO/logs"

for L in server scan; do
  SRC="$REPO/launchd/com.careerboard.$L.plist"
  DST="$LA/com.careerboard.$L.plist"
  sed -e "s|@HOME@|$HOME|g" -e "s|@REPO@|$REPO|g" "$SRC" > "$DST"
  launchctl bootout "gui/$UID_/com.careerboard.$L" 2>/dev/null
  if launchctl bootstrap "gui/$UID_" "$DST" 2>/dev/null; then
    echo "loaded com.careerboard.$L"
  else
    echo "FAILED to load com.careerboard.$L"
  fi
done
launchctl enable "gui/$UID_/com.careerboard.server" 2>/dev/null
launchctl enable "gui/$UID_/com.careerboard.scan" 2>/dev/null
echo "--- status ---"
launchctl list | grep careerboard || echo "(none listed yet)"
echo "dashboard: http://localhost:8765/index.html#preview"
