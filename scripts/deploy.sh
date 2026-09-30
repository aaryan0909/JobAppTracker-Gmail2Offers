#!/bin/bash
# Deploy the dashboard's web/ directory to Vercel (production).
# No-op until you've run `vercel login` once. Safe to call from run_scan.sh.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="${CAREERBOARD_LOGDIR:-$REPO/logs}"
mkdir -p "$LOGDIR"
cd "$REPO/web" || exit 1
vercel whoami >/dev/null 2>&1 || {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] not logged into vercel; skipping deploy" >>"$LOGDIR/deploy.log"
  exit 0
}
vercel deploy --prod --yes >>"$LOGDIR/deploy.log" 2>&1
