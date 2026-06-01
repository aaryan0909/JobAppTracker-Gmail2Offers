#!/bin/bash
export PATH="/usr/bin:/bin:/opt/homebrew/bin:$HOME/.nvm/versions/node/v24.15.0/bin:/usr/local/bin"
cd "$HOME/career-tracker/web" || exit 1
# no-op until you've run `vercel login` once
vercel whoami >/dev/null 2>&1 || { echo "[$(date)] not logged into vercel; skipping deploy" >>"$HOME/career-tracker/logs/deploy.log"; exit 0; }
vercel deploy --prod --yes >>"$HOME/career-tracker/logs/deploy.log" 2>&1
