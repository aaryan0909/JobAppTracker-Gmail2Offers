#!/usr/bin/env python3
"""ingest_gmail.py — Gmail API ingestion for the Career Decision Board.

Replaces the personal "headless agent reads my inbox" setup with a
reproducible path anyone can run:

1. Enable the Gmail API + create an OAuth desktop client (docs/SETUP.md).
2. Save the client secret as engine/credentials.json (git-ignored).
3. Run:  python -m engine.cli scan
   A browser window opens once for consent; the token is cached as
   engine/token.json (git-ignored) for future runs.

Each scan searches `after:(last_scan - overlap_days)` so re-running is
safe, classifies every message with engine/classify.py (deterministic,
config-driven), and returns records in the ingest schema. The LLM scan
prompt in docs/alternatives/llm-scan.md remains an optional second pass
for harder inboxes — it is not required.

Requires: google-api-python-client, google-auth-oauthlib
  pip install -r requirements.txt
"""
import base64
import os
from datetime import datetime, timedelta, timezone

from engine import classify

HERE = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS = os.path.join(HERE, "credentials.json")
TOKEN = os.path.join(HERE, "token.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_service(credentials_path=CREDENTIALS, token_path=TOKEN):
    """Build an authorized Gmail API service (OAuth desktop flow)."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise SystemExit(
            "Gmail API libraries are not installed.\n"
            "Run:  pip install google-api-python-client google-auth-oauthlib"
        )
    if not os.path.exists(credentials_path):
        raise SystemExit(
            f"Missing {credentials_path}.\n"
            "Follow docs/SETUP.md (Gmail API setup) to create an OAuth client "
            "and save it as engine/credentials.json."
        )
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        os.chmod(token_path, 0o600)
    return build("gmail", "v1", credentials=creds)


def _header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_part(part):
    data = (part.get("body") or {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "===" ).decode("utf-8", "replace")
    except Exception:
        return ""


def _body_text(payload):
    """Extract readable text from a Gmail message payload (prefer plain text)."""
    mime = payload.get("mimeType", "")
    if mime.startswith("text/"):
        return _decode_part(payload)
    texts = []
    for part in payload.get("parts", []) or []:
        pmime = part.get("mimeType", "")
        if pmime == "text/plain":
            texts.append(_decode_part(part))
        elif pmime.startswith("multipart/"):
            texts.append(_body_text(part))
    if not texts:  # fall back to html stripped of tags
        for part in payload.get("parts", []) or []:
            if part.get("mimeType") == "text/html":
                html = _decode_part(part)
                texts.append(__import__("re").sub(r"<[^>]+>", " ", html))
    return "\n".join(t for t in texts if t).strip()


def fetch_message(service, msg_id):
    """Fetch + normalize one Gmail message into the classifier's input shape."""
    m = service.users().messages().get(
        userId="me", id=msg_id, format="full").execute()
    headers = m.get("payload", {}).get("headers", [])
    subject = _header(headers, "Subject")
    from_raw = _header(headers, "From")
    date_raw = _header(headers, "Date")
    sender_name, sender_email = "", ""
    if "<" in from_raw:
        sender_name = from_raw.split("<")[0].strip().strip('"')
        sender_email = from_raw.split("<")[1].split(">")[0].strip()
    else:
        sender_email = from_raw.strip()
    try:
        internal_ms = int(m.get("internalDate", 0)) // 1000
        date = datetime.fromtimestamp(internal_ms, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError):
        date = ""
    body = _body_text(m.get("payload", {}))
    return {
        "id": msg_id,
        "thread_id": m.get("threadId", ""),
        "subject": subject,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "date": date,
        "snippet": m.get("snippet", ""),
        "body": body[:8000],  # cap: snippets carry the signal
        "_date_raw": date_raw,
    }


def search_ids(service, query, after_ymd, max_results=50):
    """All message ids matching `query after:YYYY/MM/DD`, paginated."""
    q = f"{query} after:{after_ymd}"
    ids, page_token = [], None
    while True:
        resp = service.users().messages().list(
            userId="me", q=q, maxResults=min(max_results, 500),
            pageToken=page_token).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        page_token = resp.get("nextPageToken")
        if not page_token or len(ids) >= max_results:
            break
    return ids[:max_results]


def scan(cfg, service=None, progress=None):
    """Run one Gmail scan. Returns records in the ingest schema:

    {"scanned_at", "applications", "interviews", "contacts", "leads"}
    """
    service = service or get_service()
    gcfg = cfg["gmail"]
    overlap = gcfg.get("overlap_days", 2)
    max_n = gcfg.get("max_results_per_query", 50)
    after = (datetime.now(timezone.utc).date()
             - timedelta(days=overlap)).strftime("%Y/%m/%d")

    seen, records = set(), []
    for name, query in gcfg["queries"].items():
        ids = search_ids(service, query, after, max_n)
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            try:
                msg = fetch_message(service, mid)
            except Exception as e:  # one bad message must not kill the scan
                if progress:
                    progress(f"  ! failed to fetch {mid}: {e}")
                continue
            rec = classify.email_to_record(msg, cfg)
            if rec["event"] != "other":
                records.append(rec)
                if progress:
                    progress(f"  + [{rec['event']}] {rec['company']} — {rec['title']}")
    buckets = classify.split_records(records)
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "applications": buckets["applications"],
        "interviews": buckets["interviews"],
        "contacts": _contacts_from(records),
        "leads": buckets["leads"],
    }


def _contacts_from(records):
    """Warm contacts: distinct senders from interview/recruiter mail."""
    out, seen = [], set()
    for r in records:
        if r["event"] not in ("interview", "recruiter_outreach", "offer"):
            continue
        key = (r["company"] or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({
            "name": "", "title": "", "company": r["company"], "email": "",
            "warmth": "warm", "last_touch": r["date"],
            "context": f"From {r['event']} email ({r['date']})",
            "linkedin": "",
        })
    return out
