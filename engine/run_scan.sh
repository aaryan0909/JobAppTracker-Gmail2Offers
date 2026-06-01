#!/bin/bash
# Career tracker — unattended scan + update. Invoked by launchd (and manually).
# Scans Gmail via headless claude, merges results, refreshes Job Tracker.xlsx + dashboard.

export HOME="/Users/aaaryanchawla"
# /usr/bin first so `python3` = system python (which has cryptography); claude/node still found later.
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$HOME/.nvm/versions/node/v24.15.0/bin:/usr/local/bin"
PYTHON="/usr/bin/python3"   # pinned: the python that has openpyxl + cryptography

ENG="$HOME/career-tracker/engine"
LOGDIR="$HOME/career-tracker/logs"
PROMPT="$ENG/scan_prompt.md"
RECORDS="$ENG/new_records.json"
LOCKDIR="$ENG/.scan.lockdir"
mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d)"
LOG="$LOGDIR/scan-$STAMP.log"
say(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# single-instance lock via atomic mkdir (macOS has no flock).
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  if [ -n "$(find "$LOCKDIR" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    rmdir "$LOCKDIR" 2>/dev/null; mkdir "$LOCKDIR" 2>/dev/null || { say "lock busy; exiting."; exit 0; }
    say "removed stale lock and continued."
  else
    say "another scan is running; exiting."; exit 0
  fi
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

say "── scan start ──"
command -v claude >/dev/null || { say "ERROR: claude CLI not on PATH"; exit 1; }

rm -f "$RECORDS"

say "invoking claude scanner…"
claude -p "$(cat "$PROMPT")" --permission-mode bypassPermissions >> "$LOG" 2>&1
say "claude exit=$?"

if [ ! -s "$RECORDS" ]; then
  say "no new_records.json produced — nothing to merge (ok if inbox had nothing)."
  "$PYTHON" "$ENG/career_lib.py" build >> "$LOG" 2>&1
  "$PYTHON" "$ENG/career_lib.py" xlsx  >> "$LOG" 2>&1
  say "── scan end (no changes) ──"; exit 0
fi

if ! "$PYTHON" -c "import json; json.load(open('$RECORDS'))" 2>>"$LOG"; then
  say "ERROR: new_records.json is not valid JSON; leaving it for inspection."; exit 1
fi

say "merging records…"
"$PYTHON" "$ENG/career_lib.py" ingest "$RECORDS" >> "$LOG" 2>&1 && \
"$PYTHON" "$ENG/career_lib.py" xlsx >> "$LOG" 2>&1
if [ $? -ne 0 ]; then say "ERROR during ingest/xlsx"; exit 1; fi

mkdir -p "$ENG/archive"
mv "$RECORDS" "$ENG/archive/records-$(date +%Y%m%d-%H%M%S).json"

# optional deploy (Phase B): push to Vercel so the phone link updates.
if [ -x "$ENG/deploy.sh" ]; then
  say "deploying…"; "$ENG/deploy.sh" >> "$LOG" 2>&1 || say "deploy step reported an error"
fi

say "── scan end (updated) ──"
