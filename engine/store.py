#!/usr/bin/env python3
"""store.py — the structured store (SQLite) for the Career Decision Board.

Replaces the old flat store.json blob with a real schema: applications,
interviews, contacts, leads, templates, scan history, and a scan cursor.
All merge logic lives here:

- applications upsert by Gmail thread_id, falling back to a normalized
  (company, title[, date]) key;
- stage updates are guarded by config.should_advance so out-of-order or
  overlapping scans can never regress a stage (e.g. a late "Applied"
  email overwriting "Interview");
- interviews dedupe by thread_id or (company, title, date, round).

Stdlib only (sqlite3). Safe to re-run: every write is idempotent.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

from engine import classify
from engine import config as config_mod

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id     TEXT NOT NULL DEFAULT '',
    company       TEXT NOT NULL DEFAULT '',
    title         TEXT NOT NULL DEFAULT '',
    url           TEXT NOT NULL DEFAULT '',
    stage         TEXT NOT NULL DEFAULT 'Applied',
    date_applied  TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT 'Direct',
    reply         INTEGER NOT NULL DEFAULT 0,
    interview     INTEGER NOT NULL DEFAULT 0,
    flag          INTEGER NOT NULL DEFAULT 0,
    notes         TEXT NOT NULL DEFAULT '',
    app_key       TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_apps_thread
    ON applications(thread_id) WHERE thread_id <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_apps_key ON applications(app_key);

CREATE TABLE IF NOT EXISTS interviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   TEXT NOT NULL DEFAULT '',
    company     TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    date        TEXT NOT NULL DEFAULT '',
    round       TEXT NOT NULL DEFAULT '',
    interviewer TEXT NOT NULL DEFAULT '',
    details     TEXT NOT NULL DEFAULT '',
    dedup_key   TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_iv_thread
    ON interviews(thread_id) WHERE thread_id <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_iv_key ON interviews(dedup_key);

CREATE TABLE IF NOT EXISTS contacts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL DEFAULT '',
    title      TEXT NOT NULL DEFAULT '',
    company    TEXT NOT NULL DEFAULT '',
    email      TEXT NOT NULL DEFAULT '',
    phone      TEXT NOT NULL DEFAULT '',
    warmth     TEXT NOT NULL DEFAULT 'warm',
    last_touch TEXT NOT NULL DEFAULT '',
    context    TEXT NOT NULL DEFAULT '',
    linkedin   TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_contacts_email
    ON contacts(email) WHERE email <> '';

CREATE TABLE IF NOT EXISTS leads (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    company   TEXT NOT NULL DEFAULT '',
    title     TEXT NOT NULL DEFAULT '',
    source    TEXT NOT NULL DEFAULT 'Job alert',
    date      TEXT NOT NULL DEFAULT '',
    url       TEXT NOT NULL DEFAULT '',
    dedup_key TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_key ON leads(dedup_key);

CREATE TABLE IF NOT EXISTS templates (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    audience  TEXT NOT NULL DEFAULT '',
    when_to_use TEXT NOT NULL DEFAULT '',
    body      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS processed_threads (
    thread_id    TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT NOT NULL DEFAULT 'ok',
    apps_added       INTEGER NOT NULL DEFAULT 0,
    interviews_added INTEGER NOT NULL DEFAULT 0,
    leads_added      INTEGER NOT NULL DEFAULT 0,
    note             TEXT NOT NULL DEFAULT ''
);
"""

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "careerboard.db")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _bool(v):
    return 1 if v else 0


class Store:
    """SQLite-backed store. Use as a context manager."""

    def __init__(self, path=None):
        self.path = path or os.environ.get("CAREERBOARD_DB", DEFAULT_DB)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.conn.commit()
        self.conn.close()

    # ------------------------------------------------------------ applications
    def upsert_application(self, rec, cfg):
        """Merge one application record.

        Returns (action, id) where action is one of:
          added | stage_advanced | updated | noop
        """
        company = (rec.get("company") or "").strip()
        title = (rec.get("title") or "").strip() or "[unknown title]"
        date_applied = (rec.get("date_applied") or "")[:10]
        thread_id = (rec.get("thread_id") or "").strip()
        new_stage = config_mod.canonical_stage(rec.get("stage") or "Applied", cfg)
        key = "|".join(classify.app_key(company, title, date_applied))

        row = None
        if thread_id:
            row = self.conn.execute(
                "SELECT * FROM applications WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        if row is None:
            row = self.conn.execute(
                "SELECT * FROM applications WHERE app_key = ?", (key,)
            ).fetchone()

        now = _now()
        if row is None:
            cur = self.conn.execute(
                """INSERT INTO applications
                   (thread_id, company, title, url, stage, date_applied, source,
                    reply, interview, flag, notes, app_key, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (thread_id, company, title, rec.get("url", ""), new_stage,
                 date_applied, rec.get("source", "Direct"), _bool(rec.get("reply")),
                 _bool(rec.get("interview")), _bool(rec.get("flag")),
                 rec.get("notes", ""), key, now, now),
            )
            return "added", cur.lastrowid

        updates = []
        # Stage: only forward progress or terminal outcomes — never regress.
        if config_mod.should_advance(row["stage"], new_stage, cfg):
            updates.append(("stage", new_stage))
        # Fill in blanks opportunistically, but never clobber real values.
        for field in ("url", "notes"):
            if not row[field] and rec.get(field):
                updates.append((field, rec[field]))
        if rec.get("interview") and not row["interview"]:
            updates.append(("interview", 1))
        if rec.get("reply") and not row["reply"]:
            updates.append(("reply", 1))
        if rec.get("flag") and not row["flag"]:
            updates.append(("flag", 1))
        if not row["thread_id"] and thread_id:
            updates.append(("thread_id", thread_id))
        if not row["date_applied"] and date_applied:
            updates.append(("date_applied", date_applied))

        action = "noop"
        if updates:
            sets = ", ".join(f"{f} = ?" for f, _ in updates)
            self.conn.execute(
                f"UPDATE applications SET {sets}, updated_at = ? WHERE id = ?",
                [v for _, v in updates] + [now, row["id"]],
            )
            action = "stage_advanced" if updates[0][0] == "stage" else "updated"
        return action, row["id"]

    def list_applications(self):
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM applications ORDER BY id").fetchall()]

    # ------------------------------------------------------------- interviews
    @staticmethod
    def _interview_key(rec):
        return "|".join([
            classify.normalize(rec.get("company")),
            classify.normalize(rec.get("title")),
            (rec.get("date") or "")[:10],
            classify.normalize(rec.get("round")),
        ])

    def add_interview(self, rec):
        """Insert an interview unless it duplicates an existing one."""
        thread_id = (rec.get("thread_id") or "").strip()
        if thread_id:
            exists = self.conn.execute(
                "SELECT id FROM interviews WHERE thread_id = ?", (thread_id,)
            ).fetchone()
            if exists:
                return "noop", exists["id"]
        key = self._interview_key(rec)
        exists = self.conn.execute(
            "SELECT id FROM interviews WHERE dedup_key = ?", (key,)
        ).fetchone()
        if exists:
            return "noop", exists["id"]
        cur = self.conn.execute(
            """INSERT INTO interviews
               (thread_id, company, title, date, round, interviewer, details, dedup_key)
               VALUES (?,?,?,?,?,?,?,?)""",
            (thread_id, (rec.get("company") or "").strip(),
             (rec.get("title") or "").strip(), (rec.get("date") or "")[:10],
             rec.get("round", ""), rec.get("interviewer", ""),
             rec.get("details", ""), key),
        )
        return "added", cur.lastrowid

    def list_interviews(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM interviews ORDER BY date DESC, id DESC").fetchall()]

    # --------------------------------------------------------------- contacts
    def add_contact(self, rec):
        email = (rec.get("email") or "").strip().lower()
        if email:
            exists = self.conn.execute(
                "SELECT id FROM contacts WHERE email = ?", (email,)).fetchone()
            if exists:
                return "noop", exists["id"]
        else:
            exists = self.conn.execute(
                "SELECT id FROM contacts WHERE name = ? AND company = ?",
                (rec.get("name", ""), rec.get("company", ""))).fetchone()
            if exists:
                return "noop", exists["id"]
        cur = self.conn.execute(
            """INSERT INTO contacts
               (name, title, company, email, phone, warmth, last_touch, context, linkedin)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (rec.get("name", ""), rec.get("title", ""), rec.get("company", ""),
             email, rec.get("phone", ""), rec.get("warmth", "warm"),
             (rec.get("last_touch") or "")[:10], rec.get("context", ""),
             rec.get("linkedin", "")),
        )
        return "added", cur.lastrowid

    def list_contacts(self):
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()]

    # ------------------------------------------------------------------ leads
    def add_lead(self, rec):
        key = "|".join([classify.normalize(rec.get("company")),
                        classify.normalize(rec.get("title"))])
        if not classify.normalize(rec.get("title")):
            return "noop", None
        exists = self.conn.execute(
            "SELECT id FROM leads WHERE dedup_key = ?", (key,)).fetchone()
        if exists:
            return "noop", exists["id"]
        cur = self.conn.execute(
            "INSERT INTO leads (company, title, source, date, url, dedup_key)"
            " VALUES (?,?,?,?,?,?)",
            ((rec.get("company") or "").strip(), (rec.get("title") or "").strip(),
             rec.get("source", "Job alert"), (rec.get("date") or "")[:10],
             rec.get("url", ""), key),
        )
        return "added", cur.lastrowid

    def list_leads(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM leads ORDER BY date DESC, id DESC").fetchall()]

    # --------------------------------------------------------------- templates
    def seed_templates(self, templates):
        if self.conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"]:
            return
        for t in templates:
            self.conn.execute(
                "INSERT INTO templates (name, audience, when_to_use, body)"
                " VALUES (?,?,?,?)",
                (t.get("name", ""), t.get("audience", ""),
                 t.get("when", ""), t.get("body", "")),
            )

    def list_templates(self):
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM templates ORDER BY id").fetchall()]

    # ------------------------------------------------------------------ cursor
    def get_cursor(self):
        row = self.conn.execute(
            "SELECT value FROM kv WHERE key = 'last_scan_iso'").fetchone()
        return {
            "last_scan_iso": row["value"] if row else None,
            "processed_count": self.conn.execute(
                "SELECT COUNT(*) c FROM processed_threads").fetchone()["c"],
        }

    def set_cursor(self, last_scan_iso):
        self.conn.execute(
            "INSERT INTO kv (key, value) VALUES ('last_scan_iso', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (last_scan_iso,))

    def is_thread_processed(self, thread_id):
        if not thread_id:
            return False
        return self.conn.execute(
            "SELECT 1 FROM processed_threads WHERE thread_id = ?",
            (thread_id,)).fetchone() is not None

    def mark_thread_processed(self, thread_id):
        if not thread_id:
            return
        self.conn.execute(
            "INSERT OR IGNORE INTO processed_threads (thread_id, processed_at)"
            " VALUES (?, ?)", (thread_id, _now()))

    # ------------------------------------------------------------------- scans
    def log_scan(self, status="ok", note="", **counts):
        cur = self.conn.execute(
            """INSERT INTO scans
               (started_at, finished_at, status, apps_added, interviews_added,
                leads_added, note)
               VALUES (?,?,?,?,?,?,?)""",
            (_now(), _now(), status, counts.get("apps_added", 0),
             counts.get("interviews_added", 0), counts.get("leads_added", 0),
             note),
        )
        return cur.lastrowid

    # ----------------------------------------------------- import / export
    def to_dict(self, owner_name="You"):
        """Legacy-shaped dict for the render pipeline."""
        apps = self.list_applications()
        for a in apps:  # normalize sqlite ints back to bools-ish
            a["reply"] = bool(a["reply"]); a["interview"] = bool(a["interview"])
            a["flag"] = bool(a["flag"])
        return {
            "applications": apps,
            "interviews": self.list_interviews(),
            "contacts": self.list_contacts(),
            "leads": self.list_leads(),
            "templates": self.list_templates(),
            "meta": {"owner_name": owner_name},
            "cursor": self.get_cursor(),
        }

    def import_legacy(self, data, cfg):
        """Import an old store.json blob. Idempotent via upsert."""
        counts = {"apps": 0, "interviews": 0, "contacts": 0, "leads": 0}
        for a in data.get("applications", []):
            action, _ = self.upsert_application(a, cfg)
            if action == "added":
                counts["apps"] += 1
        for iv in data.get("interviews", []):
            action, _ = self.add_interview(iv)
            if action == "added":
                counts["interviews"] += 1
        for c in data.get("contacts", []):
            action, _ = self.add_contact(c)
            if action == "added":
                counts["contacts"] += 1
        for le in data.get("leads", []):
            action, _ = self.add_lead(le)
            if action == "added":
                counts["leads"] += 1
        self.seed_templates(data.get("templates", []))
        cursor = data.get("cursor", {})
        if cursor.get("last_scan_iso"):
            self.set_cursor(cursor["last_scan_iso"])
        for tid in cursor.get("processed_thread_ids", []):
            self.mark_thread_processed(tid)
        self.conn.commit()
        return counts
