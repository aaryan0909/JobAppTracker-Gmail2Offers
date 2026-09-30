#!/usr/bin/env python3
"""Tests for engine/store.py — SQLite store, upsert + dedup + stage guard."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import config as config_mod, store as store_mod  # noqa: E402

CFG = config_mod.load(os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "config.json"))


def app(**kw):
    a = {"thread_id": "", "company": "Acme", "title": "Data Analyst",
         "url": "", "stage": "Applied", "date_applied": "2026-09-01",
         "source": "Greenhouse", "reply": True, "interview": False,
         "flag": False, "notes": ""}
    a.update(kw)
    return a


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.st = store_mod.Store(os.path.join(self.tmp, "test.db"))
        self.st.seed_templates(CFG.get("templates", []))

    def tearDown(self):
        self.st.conn.close()

    def test_add_application(self):
        action, aid = self.st.upsert_application(app(thread_id="t1"), CFG)
        self.assertEqual(action, "added")
        self.assertEqual(len(self.st.list_applications()), 1)

    def test_dedup_by_thread_id(self):
        self.st.upsert_application(app(thread_id="t1"), CFG)
        action, _ = self.st.upsert_application(app(thread_id="t1"), CFG)
        self.assertEqual(action, "noop")

    def test_dedup_by_company_title(self):
        self.st.upsert_application(app(thread_id="t1"), CFG)
        action, _ = self.st.upsert_application(
            app(thread_id="t2", company="acme ", title="data analyst"), CFG)
        self.assertEqual(action, "noop")

    def test_unknown_titles_dont_collapse(self):
        self.st.upsert_application(
            app(thread_id="t1", title="[unknown title]", date_applied="2026-09-01"), CFG)
        action, _ = self.st.upsert_application(
            app(thread_id="t2", title="[unknown title]", date_applied="2026-09-02"), CFG)
        self.assertEqual(action, "added")

    def test_stage_advances_forward(self):
        self.st.upsert_application(app(thread_id="t1", stage="Applied"), CFG)
        action, _ = self.st.upsert_application(
            app(thread_id="t1", stage="Interview", interview=True), CFG)
        self.assertEqual(action, "stage_advanced")
        self.assertEqual(self.st.list_applications()[0]["stage"], "Interview")

    def test_stage_never_regresses(self):
        # the headline bug: a late "Applied" email must not overwrite "Interview"
        self.st.upsert_application(
            app(thread_id="t1", stage="Interview", interview=True), CFG)
        action, _ = self.st.upsert_application(app(thread_id="t1", stage="Applied"), CFG)
        self.assertEqual(action, "noop")
        self.assertEqual(self.st.list_applications()[0]["stage"], "Interview")

    def test_rejection_is_terminal(self):
        self.st.upsert_application(
            app(thread_id="t1", stage="Final Round", interview=True), CFG)
        action, _ = self.st.upsert_application(
            app(thread_id="t1", stage="Rejected"), CFG)
        self.assertEqual(action, "stage_advanced")
        self.assertEqual(self.st.list_applications()[0]["stage"], "Rejected")

    def test_interview_dedup(self):
        iv = {"thread_id": "i1", "company": "Acme", "title": "Data Analyst",
              "date": "2026-09-10", "round": "Round 1", "interviewer": "",
              "details": ""}
        action, _ = self.st.add_interview(iv)
        self.assertEqual(action, "added")
        action, _ = self.st.add_interview(dict(iv, thread_id="i2"))  # same content
        self.assertEqual(action, "noop")

    def test_contact_dedup_by_email(self):
        c = {"name": "Jane", "company": "Acme", "email": "jane@acme.com",
             "warmth": "warm", "last_touch": "2026-09-01"}
        self.assertEqual(self.st.add_contact(c)[0], "added")
        self.assertEqual(self.st.add_contact(c)[0], "noop")

    def test_lead_dedup(self):
        le = {"company": "Acme", "title": "Data Analyst", "source": "LinkedIn",
              "date": "2026-09-01", "url": ""}
        self.assertEqual(self.st.add_lead(le)[0], "added")
        self.assertEqual(self.st.add_lead(le)[0], "noop")

    def test_thread_cursor(self):
        self.assertFalse(self.st.is_thread_processed("t9"))
        self.st.mark_thread_processed("t9")
        self.assertTrue(self.st.is_thread_processed("t9"))
        self.st.set_cursor("2026-09-30T00:00:00+00:00")
        cur = self.st.get_cursor()
        self.assertEqual(cur["last_scan_iso"], "2026-09-30T00:00:00+00:00")
        self.assertEqual(cur["processed_count"], 1)

    def test_legacy_import_roundtrip(self):
        legacy = {
            "applications": [app(thread_id="t1"),
                             app(thread_id="t2", title="Product Analyst",
                                 stage="Rejected")],
            "interviews": [{"thread_id": "i1", "company": "Acme", "title": "Data Analyst",
                            "date": "2026-09-10", "round": "Round 1",
                            "interviewer": "", "details": ""}],
            "contacts": [], "leads": [],
            "templates": [{"name": "T", "audience": "A", "when": "W", "body": "B"}],
            "meta": {"owner_name": "Tester"},
            "cursor": {"last_scan_iso": "2026-09-30T00:00:00+00:00",
                       "processed_thread_ids": ["t1", "t2"]},
        }
        counts = self.st.import_legacy(legacy, CFG)
        self.assertEqual(counts["apps"], 2)
        self.assertEqual(counts["interviews"], 1)
        d = self.st.to_dict("Tester")
        self.assertEqual(len(d["applications"]), 2)
        self.assertEqual(d["meta"]["owner_name"], "Tester")
        # idempotent: importing twice adds nothing
        counts2 = self.st.import_legacy(legacy, CFG)
        self.assertEqual(counts2["apps"], 0)


if __name__ == "__main__":
    unittest.main()
