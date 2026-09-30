# Setup guide

Get from zero to a live board in about 20 minutes. Two paths:

- **Try it (2 min):** sample data, no Gmail, no accounts. Proves the whole pipeline works.
- **Use it (20 min):** connect your Gmail, schedule scans, deploy the dashboard.

## Prerequisites

- Python 3.9+
- `pip install -r requirements.txt` — everything is optional except the stdlib core:
  - `openpyxl` → the `Job Tracker.xlsx` mirror (`xlsx` command)
  - `cryptography` → the encrypted phone deployment (`build` writes `data.enc.json`)
  - `google-api-python-client`, `google-auth-oauthlib` → Gmail API scans
  - IMAP scans need nothing beyond the stdlib.

## Path 1 — try it with sample data

```bash
git clone https://github.com/aaryan0909/JobAppTracker-Gmail2Offers.git
cd JobAppTracker-Gmail2Offers
python -m engine.cli seed      # loads clearly-labeled synthetic data
python -m engine.cli build    # rebuilds web/career_data.json
python3 -m http.server 8765 --directory web
# open http://localhost:8765/index.html#preview
```

You should see a full board: 90+ applications, a pipeline, insights, recommendations.
Everything labeled "Sample data" is synthetic (see `engine/seed_demo.py`).

Run the tests while you're here: `./careerboard test` (or `python -m unittest discover -s tests`).

## Path 2 — connect your Gmail

Two ingestion paths, same merge logic. Pick one.

### A. Gmail API (recommended — full fidelity)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project (any name).
2. **APIs & Services → Library** → enable **Gmail API**.
3. **APIs & Services → OAuth consent screen** → External → fill in app name/email → add scope `https://www.googleapis.com/auth/gmail.readonly` → add yourself as a test user.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID** → type **Desktop app** → download the JSON.
5. Save it as `engine/credentials.json` (git-ignored — never commit it).
6. Run `python -m engine.cli scan`. A browser window opens once for consent; the token is cached at `engine/token.json` (also git-ignored).

The scanner only requests **readonly** Gmail access and only searches job-related queries (see `config.json` → `gmail.queries`).

### B. IMAP + app password (no Cloud project)

1. Google Account → **Security** → enable **2-Step Verification**.
2. **Security → App passwords** → create one for "Mail" → copy the 16-character password.
3. Export it (per shell session, or add to your shell profile):
   ```bash
   export CAREERBOARD_IMAP_USER="you@gmail.com"
   export CAREERBOARD_IMAP_PASS="abcd efgh ijkl mnop"
   ```
4. Run `python -m engine.cli scan --imap`.

Notes: IMAP search is a rough translation of the Gmail queries (no thread ids, so de-dup falls back to company/title), and Gmail may throttle aggressive IMAP polling. The API path is more reliable for hourly scans.

### How a scan works

Every scan searches `after:(last_scan − overlap_days)` (default 2 days, `config.json`), so re-running is always safe. Each message is classified by `engine/classify.py` — deterministic keyword rules, no LLM required:

| Email looks like… | Event | Effect |
|---|---|---|
| "Thank you for applying" | application_confirmation | new application, stage `Applied` |
| "We'd like to schedule an interview" | interview | interview row + stage advances |
| "We are pleased to offer you…" | offer | stage `Offer` |
| "Unfortunately we've decided…" | rejection | stage `Rejected` (terminal) |
| recruiter cold outreach | recruiter_outreach | application + warm contact |
| LinkedIn/Indeed digests | job_alert | lead (not an application) |
| anything else | other | ignored |

Stage updates can only move **forward** (or to a terminal state like `Rejected`) — a late-arriving "Applied" email can never overwrite "Interview". Low-confidence records are flagged for review instead of being dropped.

**Optional LLM second pass:** if you have an agentic setup that extracts records (the old headless-scanner approach), have it write `engine/new_records.json` in the ingest schema — `scripts/run_scan.sh` merges it automatically before the API scan. A generalized prompt template lives in `docs/alternatives/llm-scan.md`.

## Scheduling

### macOS — launchd (recommended)

```bash
bash scripts/install_launchd.sh   # hourly scan + always-on local server
./careerboard start|stop|status    # control panel
```

This installs `com.careerboard.scan` (hourly) and `com.careerboard.server` (serves `web/` at `http://localhost:8765`). Logs land in `logs/`.

### Linux / macOS without launchd — cron

```bash
crontab -e
# paste the line from scheduler/cron.example (hourly scan)
# serve the dashboard: python3 -m http.server 8765 --directory web
```

### Linux — systemd

```bash
# replace __REPO__ with your repo path in scheduler/systemd/careerboard-scan.service
sudo cp scheduler/systemd/careerboard-scan.* /etc/systemd/system/
sudo sed -i "s|__REPO__|$PWD|" /etc/systemd/system/careerboard-scan.service
sudo systemctl enable --now careerboard-scan.timer
```

### Windows

Use Task Scheduler → Create Task → run `scripts/run_scan.sh` via Git Bash/WSL hourly. (Not automated by a script yet — PRs welcome.)

## Deploying the dashboard

The dashboard is a single static `web/index.html`. Three ways to serve it:

1. **Local (private):** the launchd server agent, or `python3 -m http.server 8765 --directory web` → open `index.html#preview` (reads plaintext `career_data.json`, never deployed anywhere).

2. **GitHub Pages (public demo):** this repo serves `docs/` — a copy of the dashboard plus anonymized `demo-data.json`. Enable it in repo Settings → Pages → Deploy from branch → `main` / `docs`. Refresh the demo with `python -m engine.cli demo` (synthetic) or `python engine/anonymize_demo.py` (scrubbed from your real store).

3. **Vercel:**
   - One-click (deploys the public demo): [![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Faaryan0909%2FJobAppTracker-Gmail2Offers) — when prompted, set the **Root Directory** to `web`.
   - CLI: `cd web && vercel --prod` (after `vercel login`).
   - **Private phone deployment:** `python -m engine.cli build` writes `web/data.enc.json` (AES-256-GCM, PBKDF2-SHA256 200k iterations). Deploy `web/` — the public URL only serves the encrypted blob; it decrypts in your browser with the password in `engine/.passphrase` (change the default!). Plaintext never leaves your machine.

## Configuration

Everything lives in **`config.json`** — no code changes needed to adapt the board:

- `gmail.queries` — the five Gmail searches (edit to match your inbox)
- `gmail.overlap_days` — scan overlap window
- `classification.families / .seniority / .sectors / .sources` — keyword rules and lookup maps
- `email_events` — keywords that classify an email into an event
- `stages.order / .terminal / .aliases / .event_to_stage` — your pipeline's canonical stages
- `thresholds` — stale days, momentum target, networking gap, etc.
- `templates` — outreach templates shown in the dashboard
- `low_value_channels` — sources excluded from "best channel" recommendations

Validate after editing: `python -c "from engine import config; config.load()"`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `config error: …` | `config.json` is missing a required key — the error names it. |
| Gmail API: `Missing engine/credentials.json` | Follow step A above; the file is git-ignored by design. |
| Gmail API consent "unverified app" | Normal for a personal OAuth client in testing mode — click Advanced → Go to (your app). |
| IMAP login fails | Use an **app password**, not your Google password; IMAP must be enabled in Gmail settings. |
| `encryption skipped` on build | `pip install cryptography` — local plaintext still works without it. |
| Dashboard shows "No board data yet" | Run `python -m engine.cli seed && python -m engine.cli build` first. |
| A scan changed nothing | Expected when the inbox has nothing new — the merge is idempotent. Check `logs/scan-*.log`. |
| Wrong company/title extracted | Records are flagged (`flag: true`, yellow in the spreadsheet). Tune `config.json` or correct the record — the next scan won't overwrite filled fields with blanks. |
