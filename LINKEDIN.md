# LinkedIn — Project entry + (optional) post

> A template for showcasing this project on your profile.
> Fill in the placeholders: `<you>` = your GitHub username.

---

## 1) Add to your Profile → "Projects" section

**How:** LinkedIn → your profile → **Add profile section** → **Recommended** / **Additional** → **Add projects**.

| Field | What to enter |
|---|---|
| **Project name** | Career Decision Board — a self-updating job-search command center |
| **Associated with** | (leave blank, or your school if you want) |
| **Currently working on it** | ✅ Yes (it runs daily) — or set a start month |
| **Start date** | (the month you started) |
| **Project URL** | **https://`<you>`.github.io/JobAppTracker-Gmail2Offers/** (the live demo — most clickable) |
| **Description** | *(paste below)* |
| **Contributors** | just you |

**Description (≈ fits LinkedIn's limit):**

```
A system I built to run my own job search like a data pipeline. A scheduled agent reads my
Gmail every hour, classifies each email (application, interview, rejection, job alert),
and de-duplicates it into a living pipeline — feeding both a spreadsheet and an interactive
web "decision board."

Beyond tracking, it computes what's actually working: interview-conversion rate by job
family, channel, and seniority, then ranks my next actions — active opportunities, offers,
stalled applications to re-engage, warm contacts to follow up, and new leads scored against
my strongest segments. It works on laptop and phone, with the phone view end-to-end
encrypted behind a password.

Engineering highlights: SQLite store with idempotent upserts, overlapping-window scans with
thread-ID de-duplication, a stage-progress guard (out-of-order emails can't regress a
stage), deterministic rules-based email classification with full unit-test coverage,
AES-GCM client-side encryption (PBKDF2-SHA256), and hands-off scheduling (launchd/cron/
systemd). Live demo uses synthetic sample data.
```

**Media to attach** (LinkedIn lets you add links/images to a project):
- The **https://`<you>`.github.io/JobAppTracker-Gmail2Offers/** link (renders a preview card)
- The **https://github.com/`<you>`/JobAppTracker-Gmail2Offers** link
- **Screenshots** (in the repo under `docs/screenshots/` — all synthetic data, safe to share):
  - Board: https://raw.githubusercontent.com/`<you>`/JobAppTracker-Gmail2Offers/main/docs/screenshots/board.png
  - Insights: https://raw.githubusercontent.com/`<you>`/JobAppTracker-Gmail2Offers/main/docs/screenshots/insights.png
  - Pipeline: https://raw.githubusercontent.com/`<you>`/JobAppTracker-Gmail2Offers/main/docs/screenshots/pipeline.png
  - Mobile: https://raw.githubusercontent.com/`<you>`/JobAppTracker-Gmail2Offers/main/docs/screenshots/mobile.png

> **If you post:** attach 2–4 of these images (image posts get more reach). Best combo: **board.png + insights.png**.

**Skills to tag on the project:** Python · JavaScript · Data Pipelines · SQLite · Automation · Web Crypto / Applied Cryptography · System Design · Problem Solving

---

## 2) (Optional) Post draft — you decide whether to publish

> You may just add it to your profile and skip posting — totally fine. If you *do*
> post, here's a draft. Keep it; don't feel obligated.

**Option A — concise / builder tone**

```
I got tired of losing track of my job search, so I built it a brain. 🧭

Career Decision Board reads my Gmail every hour, sorts applications / interviews /
rejections / job alerts into a living pipeline, and tells me what to do next —
not just a dashboard, a decision board.

It shows which kinds of roles actually convert for me, flags stalled applications,
surfaces warm contacts to follow up, and scores new leads against my strongest segments.
Laptop + phone, with the phone view fully encrypted behind a password.

A few things I'm proud of under the hood:
• SQLite store with idempotent upserts — safe re-runs, no duplicate records
• a stage-progress guard so out-of-order emails can't regress a stage
• deterministic, unit-tested email classification (61 tests, CI on 3.9–3.13)
• client-side AES-GCM encryption so a public URL never exposes private data
• 100% hands-off — scheduled scans keep it current

Live demo (synthetic data) 👉 https://<you>.github.io/JobAppTracker-Gmail2Offers/
Code 👉 https://github.com/<you>/JobAppTracker-Gmail2Offers

Built with Python, SQLite, vanilla JS + Web Crypto, and a scheduled Gmail scanner.
```

**Option B — short hook**

```
Job searching is a data problem disguised as an inbox problem — so I built a pipeline for it.

Career Decision Board: a scanner reads my Gmail hourly, tracks every application & interview,
shows what's actually converting, and ranks what to do next. Laptop + encrypted phone view,
fully self-updating.

Live demo (synthetic data) → https://<you>.github.io/JobAppTracker-Gmail2Offers/ · Code → https://github.com/<you>/JobAppTracker-Gmail2Offers
```

**Tips:** post Tue–Thu morning; add 3–5 hashtags (#buildinpublic #python #automation #jobsearch
#softwareengineering); the demo link as the first comment sometimes gets better reach than in-body.
