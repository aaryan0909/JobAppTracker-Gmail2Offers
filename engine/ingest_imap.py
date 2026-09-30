#!/usr/bin/env python3
"""ingest_imap.py — Gmail ingestion via IMAP + app password (no Google Cloud
project needed).

For users who would rather not set up a Gmail API OAuth client: create an
App Password (Google Account → Security → 2-Step Verification → App passwords),
then run:

    python -m engine.cli scan --imap

Credentials come from env vars (never from the repo):
    CAREERBOARD_IMAP_USER  your Gmail address
    CAREERBOARD_IMAP_PASS  the 16-character app password

Stdlib only (imaplib + email). Returns the same records schema as the
Gmail API scanner, so the merge path is identical.
"""
import email
import email.header
import email.utils
import imaplib
import os
from datetime import datetime, timedelta, timezone

from engine import classify

IMAP_HOST = "imap.gmail.com"


def _decode(value):
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", "replace"))
        else:
            out.append(text)
    return "".join(out)


def _body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8",
                                          "replace")[:8000]
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    text = payload.decode(msg.get_content_charset() or "utf-8", "replace")
    if msg.get_content_type() == "text/html":
        import re
        text = re.sub(r"<[^>]+>", " ", text)
    return text[:8000]


def _gmail_query(config_query, after):
    """Translate a Gmail search query to a rough IMAP SEARCH. IMAP can't do
    Gmail's subject:(a OR b) syntax, so we OR the quoted phrases manually."""
    import re
    phrases = re.findall(r'"([^"]+)"', config_query)
    criteria = []
    for p in phrases[:10]:  # cap: IMAP OR chains get slow
        criteria += ["OR", "SUBJECT", f'"{p}"', "BODY", f'"{p}"']
    if not criteria:
        return f'SINCE {after.strftime("%d-%b-%Y")}'
    # fold the OR chain: OR a b OR c d ...  (left-associative is fine)
    q = criteria[:3]
    for i in range(3, len(criteria), 3):
        q = ["OR"] + q + criteria[i:i + 3]
    return f'({" ".join(q)}) SINCE {after.strftime("%d-%b-%Y")}'


def scan(cfg, user=None, app_password=None, progress=None):
    """IMAP scan. Returns records in the ingest schema."""
    user = user or os.environ.get("CAREERBOARD_IMAP_USER")
    app_password = app_password or os.environ.get("CAREERBOARD_IMAP_PASS")
    if not user or not app_password:
        raise SystemExit(
            "IMAP scan needs CAREERBOARD_IMAP_USER and CAREERBOARD_IMAP_PASS.\n"
            "Create an app password: Google Account → Security → 2-Step "
            "Verification → App passwords. See docs/SETUP.md."
        )
    gcfg = cfg["gmail"]
    overlap = gcfg.get("overlap_days", 2)
    max_n = gcfg.get("max_results_per_query", 50)
    after = datetime.now(timezone.utc).date() - timedelta(days=overlap)

    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(user, app_password)
    imap.select("INBOX", readonly=True)

    seen_ids, records = set(), []
    try:
        for name, query in gcfg["queries"].items():
            try:
                typ, data = imap.search(None, _gmail_query(query, after))
            except imaplib.IMAP4.error as e:
                if progress:
                    progress(f"  ! search failed ({name}): {e}")
                continue
            if typ != "OK":
                continue
            for num in data[0].split()[-max_n:]:
                key = f"{name}:{num.decode()}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                typ, mdata = imap.fetch(num, "(RFC822)")
                if typ != "OK" or not mdata or not mdata[0]:
                    continue
                msg = email.message_from_bytes(mdata[0][1])
                subject = _decode(msg.get("Subject"))
                from_raw = _decode(msg.get("From"))
                sender_name, sender_email = email.utils.parseaddr(from_raw)
                try:
                    dt = email.utils.parsedate_to_datetime(msg.get("Date"))
                    date = dt.date().isoformat()
                except (TypeError, ValueError):
                    date = ""
                rec = classify.email_to_record({
                    "thread_id": key,  # IMAP has no thread ids; uid key dedupes
                    "subject": subject, "sender_name": sender_name,
                    "sender_email": sender_email, "date": date,
                    "snippet": "", "body": _body_text(msg),
                }, cfg)
                if rec["event"] != "other":
                    records.append(rec)
                    if progress:
                        progress(f"  + [{rec['event']}] {rec['company']} — {rec['title']}")
    finally:
        try:
            imap.close(); imap.logout()
        except Exception:
            pass

    buckets = classify.split_records(records)
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "applications": buckets["applications"],
        "interviews": buckets["interviews"],
        "contacts": [],
        "leads": buckets["leads"],
    }
