#!/usr/bin/env python3
"""classify.py — deterministic email → structured-record classification.

Pure functions (no I/O, no network), driven entirely by config.json.
This is the rules-based half of ingestion: it turns a Gmail message
(subject, sender, snippet/body) into a typed event and extracts
company / title / source. An LLM pass can refine these records later,
but the pipeline never *depends* on one.

All functions are unit-tested in tests/test_classify.py.
"""
import re

# ---------------------------------------------------------------- normalization

def normalize(s):
    """Lowercase, '&' → 'and', strip punctuation → single-spaced. Used for
    de-duplication keys so 'R&D' and 'R and D' collapse together."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower().replace("&", " and ")).strip()


def app_key(company, title, date=""):
    """De-dup key for an application.

    Placeholder/unknown titles are disambiguated by date so that distinct
    real applications with an unknown title are NOT collapsed together.
    """
    t = normalize(title)
    raw = (title or "").strip()
    if (not t) or ("unknown" in t) or raw.startswith("["):
        # placeholder title: key on date only, so same-day scans of the same
        # record collapse but distinct real applications never do
        return (normalize(company), "", (date or "")[:10])
    return (normalize(company), t)


# ---------------------------------------------------------------- categorization

def job_family(title, cfg):
    """Map a job title to a job family using config keyword rules."""
    t = (title or "").lower()
    rules = cfg["classification"]["families"]
    for fam in rules:
        if any(k.lower() in t for k in fam["keywords"]):
            return fam["name"]
    for fb in cfg["classification"].get("family_fallbacks", []):
        if fb["match"].lower() in t:
            return fb["family"]
    return "Other"


def seniority(title, cfg):
    """Map a job title to a seniority band using config keyword rules."""
    t = (title or "").lower()
    for band in cfg["classification"]["seniority"]:
        if any(k.lower() in t for k in band["keywords"]):
            return band["name"]
    return "Mid"


def sector(company, cfg):
    """Exact-match company → sector lookup from config; 'Other' if unmapped."""
    return cfg["classification"].get("sectors", {}).get((company or "").strip(), "Other")


def detect_source(sender_email, cfg):
    """Map a sender domain to an application channel (ATS) name from config."""
    email = (sender_email or "").lower()
    for domain, name in cfg["classification"].get("sources", {}).items():
        if domain.lower() in email:
            return name
    if "linkedin" in email:
        return "LinkedIn"
    if "indeed" in email:
        return "Indeed"
    return "Direct"


# ---------------------------------------------------------------- email events

# Order matters: first matching event wins. Rejection/offer checked before
# generic interview keywords because those emails often mention interviews.
EVENT_PRIORITY = [
    "rejection",
    "offer",
    "interview",
    "application_confirmation",
    "recruiter_outreach",
    "job_alert",
]


def classify_email(subject, sender, body, cfg):
    """Classify a Gmail message into an event type.

    Returns one of: rejection, offer, interview, application_confirmation,
    recruiter_outreach, job_alert, other.
    """
    text = f"{subject or ''}\n{sender or ''}\n{body or ''}".lower()
    rules = cfg.get("email_events", {})
    for event in EVENT_PRIORITY:
        for kw in rules.get(event, []):
            if kw.lower() in text:
                return event
    return "other"


def event_to_stage(event, cfg):
    """Map a classified email event to a canonical application stage."""
    return cfg["stages"].get("event_to_stage", {}).get(event)


# ---------------------------------------------------------------- extraction

_ATS_MARKERS = [
    "via greenhouse", "via lever", "via workday", "via ashby", "via bamboohr",
    "via smartrecruiters", "via workable", "via icims", "via taleo",
    "greenhouse", "lever", "workday", "ashby", "bamboohr",
]

_SUBJECT_PATTERNS = [
    # (regex, company_group, title_group)
    re.compile(r"your application to (.+?)(?:\s*[-–|]\s*(.+))?$", re.I),
    re.compile(r"thank you for applying to (.+?)(?:\s+for\s+the\s+(.+?))?(?:\s+position)?$", re.I),
    re.compile(r"application received[,:]?\s*(.+?)(?:\s*[-–|]\s*(.+))?$", re.I),
    re.compile(r"^(.+?)\s*[-–|]\s*(.+?)\s+application$", re.I),
]

_TITLE_PATTERNS = [
    re.compile(r"(?:application|applying) for (?:the |a )?(.+?)(?:\s+position|\s+role|\s+at\s+|$)", re.I),
    re.compile(r"interview (?:for|re:?)\s*(?:the |a )?(.+?)(?:\s+position|\s+role|\s+at\s+|$)", re.I),
    re.compile(r"^(.+?)\s+at\s+.+$", re.I),  # "Data Analyst at Acme" (last resort)
]


def _clean_company(raw):
    if not raw:
        return ""
    c = raw.strip().strip(" -–|:\"'").strip()
    # strip "via <ats>" tails: "Acme via Greenhouse" → "Acme"
    low = c.lower()
    for marker in _ATS_MARKERS:
        if low.endswith(marker):
            c = c[: -len(marker)].strip(" -–|:")
            break
    # strip email-ish tails
    c = re.sub(r"\s*<[^>]+>\s*$", "", c).strip()
    return c


def extract_company(subject, sender_name, sender_email, body, cfg=None):
    """Best-effort company extraction.

    Order: subject patterns (most specific) → sender display name carrying a
    company signal ("Acme via Greenhouse", "Acme Careers") → sender domain
    (skipping ATS/mailer domains). A bare person's name ("Jane Doe") is never
    trusted as a company — the domain fallback handles those.
    """
    for pat in _SUBJECT_PATTERNS:
        m = pat.search(subject or "")
        if m:
            c = _clean_company(m.group(1))
            if c and len(c) > 1:
                return c
    name = (sender_name or "").strip().strip('"')
    if name:
        low = name.lower()
        via = next((mk for mk in _ATS_MARKERS if mk in low), None)
        core = _clean_company(name)
        if via and core and len(core) > 1:
            return core  # "Acme via Greenhouse" → "Acme"
        # "Acme Careers" / "Acme Talent" → "Acme" (only when a signal word exists)
        stripped = re.sub(
            r"(?i)\b(careers|talent acquisition|talent|hiring|recruiting|"
            r"staffing|jobs|hr|people|team)\b\.?$", "", core).strip(" -–|:")
        if stripped != core and len(stripped) > 1:
            return stripped
        # otherwise: probably a person's name — fall through to the domain
    # domain fallback, skipping known ATS / mailer domains
    email = (sender_email or "").lower()
    dom_match = re.search(r"@([\w.-]+)", email)
    if dom_match:
        dom = dom_match.group(1)
        skip = ("greenhouse", "lever.co", "myworkday", "ashbyhq", "bamboohr",
                "smartrecruiters", "workablemail", "jobvite", "icims",
                "successfactors", "taleo", "gmail.com", "googlemail.com")
        if not any(s in dom for s in skip):
            base = dom.split(".")[0]
            if base and len(base) > 1:
                return base.replace("-", " ").title()
    return ""


def extract_title(subject, body, company=""):
    """Best-effort job-title extraction from subject, then body."""
    for pat in _TITLE_PATTERNS:
        m = pat.search(subject or "")
        if m:
            t = m.group(1).strip().strip(" -–|:\"'")
            # guard: the "X at Y" pattern must not return the company itself
            if t and normalize(t) != normalize(company):
                return t
    # body fallback: first "Job Title: ..." / "Position: ..." line
    m = re.search(r"(?im)^(?:job title|position|role)\s*:\s*(.+)$", body or "")
    if m:
        return m.group(1).strip()
    return ""


def email_to_record(message, cfg):
    """Turn one Gmail message dict into a structured record.

    message: {"id", "thread_id", "subject", "sender_name", "sender_email",
              "date", "snippet", "body"}
    Returns a record dict compatible with the ingest schema:
    {"thread_id", "company", "title", "date", "stage", "source",
     "event", "reply", "interview", "flag", "notes"}
    """
    subject = message.get("subject", "")
    sender_name = message.get("sender_name", "")
    sender_email = message.get("sender_email", "")
    body = message.get("body") or message.get("snippet", "")

    event = classify_email(subject, f"{sender_name} {sender_email}", body, cfg)
    company = extract_company(subject, sender_name, sender_email, body, cfg)
    title = extract_title(subject, body, company)
    stage = event_to_stage(event, cfg) or "Applied"

    # skip-list: pure newsletters / platform nudges
    skip = any(s.lower() in (sender_email or "").lower()
               for s in cfg["gmail"].get("skip_senders", []))
    flag = skip or not company or event == "other"

    return {
        "thread_id": message.get("thread_id", ""),
        "company": company,
        "title": title or "[unknown title]",
        "date": (message.get("date") or "")[:10],
        "stage": stage,
        "source": detect_source(sender_email, cfg),
        "event": event,
        "reply": True,
        "interview": event in ("interview", "offer"),
        "flag": flag,
        "notes": "Auto-classified from Gmail" + (" (review: low confidence)" if flag else ""),
    }


def split_records(records):
    """Split classified records into the ingest schema buckets
    (applications / interviews / contacts / leads)."""
    out = {"applications": [], "interviews": [], "contacts": [], "leads": []}
    for r in records:
        event = r.get("event", "other")
        if event == "job_alert":
            out["leads"].append({
                "company": r["company"], "title": r["title"],
                "source": r["source"], "date": r["date"], "url": "",
            })
        elif event == "interview":
            out["interviews"].append({
                "thread_id": r["thread_id"], "company": r["company"],
                "title": r["title"], "date": r["date"],
                "round": "Interview", "interviewer": "", "details": "",
            })
            out["applications"].append(_as_application(r))
        elif event in ("application_confirmation", "rejection", "offer",
                       "recruiter_outreach"):
            out["applications"].append(_as_application(r))
        # "other" is dropped: not job-search mail
    return out


def _as_application(r):
    return {
        "thread_id": r["thread_id"], "company": r["company"], "title": r["title"],
        "date_applied": r["date"], "stage": r["stage"], "source": r["source"],
        "reply": r["reply"], "interview": r["interview"], "flag": r["flag"],
        "notes": r["notes"],
    }
