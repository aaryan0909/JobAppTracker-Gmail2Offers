# LinkedIn — Project entry + (optional) post

> Fill in the two links once the repo is live:
> - **https://github.com/aaryan0909/JobAppTracker-Gmail2Offers** = `https://github.com/<you>/JobAppTracker-Gmail2Offers`
> - **https://aaryan0909.github.io/JobAppTracker-Gmail2Offers/** = `https://<you>.github.io/JobAppTracker-Gmail2Offers/`

---

## 1) Add to your Profile → "Projects" section

**How:** LinkedIn → your profile → **Add profile section** → **Recommended** / **Additional** → **Add projects**.

| Field | What to enter |
|---|---|
| **Project name** | Career Decision Board — a self-updating job-search command center |
| **Associated with** | (leave blank, or your school if you want) |
| **Currently working on it** | ✅ Yes (it runs daily) — or set a start month |
| **Start date** | (the month you started) |
| **Project URL** | **https://aaryan0909.github.io/JobAppTracker-Gmail2Offers/** (the live demo — most clickable) |
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

Engineering highlights: idempotent overlapping-window scans with thread-ID de-duplication,
LLM-for-extraction + deterministic-Python-for-truth, AES-GCM client-side encryption
(PBKDF2-SHA256), and fully hands-off macOS launchd automation. Live demo uses anonymized data.

Stack: Python, vanilla JS + Web Crypto, Gmail (MCP) via headless Claude, launchd, Vercel.

Live demo: https://aaryan0909.github.io/JobAppTracker-Gmail2Offers/   ·   Code: https://github.com/aaryan0909/JobAppTracker-Gmail2Offers
```

**Media to attach** (LinkedIn lets you add links/images to a project):
- The **https://aaryan0909.github.io/JobAppTracker-Gmail2Offers/** link (renders a preview card)
- The **https://github.com/aaryan0909/JobAppTracker-Gmail2Offers** link
- **Screenshots** (in the repo — download from `~/career-tracker/docs/screenshots/` or these raw links, then upload as project media). All use anonymized data, safe to share:
  - Board: https://raw.githubusercontent.com/aaryan0909/JobAppTracker-Gmail2Offers/main/docs/screenshots/board.png
  - Insights: https://raw.githubusercontent.com/aaryan0909/JobAppTracker-Gmail2Offers/main/docs/screenshots/insights.png
  - Pipeline: https://raw.githubusercontent.com/aaryan0909/JobAppTracker-Gmail2Offers/main/docs/screenshots/pipeline.png
  - Mobile: https://raw.githubusercontent.com/aaryan0909/JobAppTracker-Gmail2Offers/main/docs/screenshots/mobile.png

> **If you post:** attach 2–4 of these images (image posts get more reach). Best combo: **board.png + insights.png**.

**Skills to tag on the project:** Python · JavaScript · Data Pipelines · Automation · Web Crypto / Applied Cryptography · Product Thinking · System Design · Problem Solving

---

## 2) (Optional) Post draft — you decide whether to publish

> You said you may just add it to your profile and skip posting — totally fine. If you *do*
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
• idempotent, overlapping email scans with thread-ID de-dup (no missed emails, safe re-runs)
• LLM for messy extraction, deterministic Python for the source of truth
• client-side AES-GCM encryption so a public URL never exposes private data
• 100% hands-off — a scheduled agent keeps it current

Live demo (anonymized data) 👉 https://aaryan0909.github.io/JobAppTracker-Gmail2Offers/
Code 👉 https://github.com/aaryan0909/JobAppTracker-Gmail2Offers

Built with Python, vanilla JS + Web Crypto, and a scheduled headless agent on Gmail.
```

**Option B — short hook**

```
Job searching is a data problem disguised as an inbox problem — so I built a pipeline for it.

Career Decision Board: an agent reads my Gmail hourly, tracks every application & interview,
shows what's actually converting, and ranks what to do next. Laptop + encrypted phone view,
fully self-updating.

Live demo (anonymized) → https://aaryan0909.github.io/JobAppTracker-Gmail2Offers/ · Code → https://github.com/aaryan0909/JobAppTracker-Gmail2Offers
```

**Tips:** post Tue–Thu morning; add 3–5 hashtags (#buildinpublic #python #automation #jobsearch
#softwareengineering); the demo link as the first comment sometimes gets better reach than in-body.
```
