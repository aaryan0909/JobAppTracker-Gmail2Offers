#!/bin/bash
# Career Decision Board — unattended scan + rebuild.
# Invoked by launchd / cron / systemd, or manually:  bash scripts/run_scan.sh
#
# What it does: scan Gmail (Gmail API) → merge into the SQLite store →
# rebuild career_data.json (+ encrypted blob) → rebuild the xlsx mirror.
# Safe to re-run: scans use an overlapping window and the merge is idempotent.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="${CAREERBOARD_LOGDIR:-$REPO/logs}"
LOCKDIR="$REPO/engine/.scan.lockdir"
RECORDS="$REPO/engine/new_records.json"   # optional: drop an LLM-scan file here
mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d)"
LOG="$LOGDIR/scan-$STAMP.log"
say(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# single-instance lock via atomic mkdir (works on macOS + Linux).
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
cd "$REPO" || exit 1
command -v python3 >/dev/null || { say "ERROR: python3 not on PATH"; exit 1; }

# Optional LLM second pass: if new_records.json exists (e.g. produced by the
# prompt in docs/alternatives/llm-scan.md), merge it first.
if [ -s "$RECORDS" ]; then
  if python3 -c "import json; json.load(open('$RECORDS'))" 2>>"$LOG"; then
    say "merging LLM records…"
    python3 -m engine.cli ingest "$RECORDS" >>"$LOG" 2>&1 || say "ERROR during LLM ingest"
    mkdir -p "$REPO/engine/archive"
    mv "$RECORDS" "$REPO/engine/archive/records-$(date +%Y%m%d-%H%M%S).json"
  else
    say "ERROR: $RECORDS is not valid JSON; leaving it for inspection."
  fi
fi

say "scanning Gmail…"
if python3 -m engine.cli scan >>"$LOG" 2>&1; then
  say "gmail scan merged."
else
  say "gmail scan reported an error (see above); rebuilding from existing data."
  python3 -m engine.cli build >>"$LOG" 2>&1
fi

say "rebuilding spreadsheet…"
python3 -m engine.cli xlsx >>"$LOG" 2>&1 || say "xlsx step reported an error"

if [ -x "$REPO/scripts/deploy.sh" ]; then
  say "deploying…"; "$REPO/scripts/deploy.sh" >>"$LOG" 2>&1 || say "deploy step reported an error"
fi

say "── scan end ──"
