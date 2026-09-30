#!/usr/bin/env python3
"""Tests for engine/classify.py — the deterministic classification core."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import classify, config as config_mod  # noqa: E402

CFG = config_mod.load(os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "config.json"))


class TestNormalize(unittest.TestCase):
    def test_ampersand(self):
        self.assertEqual(classify.normalize("R&D"), "r and d")
        self.assertEqual(classify.normalize("R and D"), "r and d")

    def test_punctuation(self):
        self.assertEqual(classify.normalize("Acme, Inc."), "acme inc")

    def test_none(self):
        self.assertEqual(classify.normalize(None), "")


class TestAppKey(unittest.TestCase):
    def test_duplicates_collapse(self):
        self.assertEqual(
            classify.app_key("Acme", "Data Analyst", "2026-01-01"),
            classify.app_key("acme ", "data analyst", "2026-01-01"))

    def test_ampersand_collapse(self):
        self.assertEqual(classify.app_key("R&D Corp", "Data Analyst"),
                         classify.app_key("R and D Corp", "Data Analyst"))

    def test_unknown_titles_not_collapsed(self):
        # distinct applications with unknown titles must NOT merge
        self.assertNotEqual(
            classify.app_key("Acme", "[unknown title]", "2026-01-01"),
            classify.app_key("Acme", "[unknown title]", "2026-01-02"))

    def test_unknown_title_same_day_collapses(self):
        self.assertEqual(
            classify.app_key("Acme", "unknown", "2026-01-01"),
            classify.app_key("Acme", "[unknown title]", "2026-01-01"))


class TestJobFamily(unittest.TestCase):
    def test_data_analyst(self):
        self.assertEqual(classify.job_family("Senior Data Analyst", CFG),
                         "Data & Analytics")

    def test_product_analyst_leans_analytics(self):
        self.assertEqual(classify.job_family("Product Analyst", CFG),
                         "Data & Analytics")

    def test_product_manager(self):
        self.assertEqual(classify.job_family("Senior Product Manager", CFG),
                         "Product")

    def test_fallback_analyst(self):
        self.assertEqual(classify.job_family("Fraud Analyst", CFG),
                         "Risk & Finance")  # 'fraud' keyword wins first

    def test_other(self):
        self.assertEqual(classify.job_family("Barista", CFG), "Other")


class TestSeniority(unittest.TestCase):
    def test_director(self):
        self.assertEqual(classify.seniority("Director of Analytics", CFG),
                         "Director+")

    def test_entry(self):
        self.assertEqual(classify.seniority("Data Analyst Intern", CFG),
                         "Entry/Associate")

    def test_mid_default(self):
        self.assertEqual(classify.seniority("Data Wizard", CFG), "Mid")


class TestClassifyEmail(unittest.TestCase):
    def test_rejection(self):
        self.assertEqual(classify.classify_email(
            "Update on your application",
            "noreply@acme.com",
            "Unfortunately we have decided not to move forward", CFG), "rejection")

    def test_offer(self):
        self.assertEqual(classify.classify_email(
            "Offer letter from Acme",
            "hr@acme.com",
            "We are pleased to offer you the role", CFG), "offer")

    def test_interview(self):
        self.assertEqual(classify.classify_email(
            "Interview invitation: Data Analyst",
            "recruiter@acme.com",
            "We'd like to schedule a phone screen", CFG), "interview")

    def test_application_confirmation(self):
        self.assertEqual(classify.classify_email(
            "Thank you for applying",
            "jobs@acme.com",
            "We received your application", CFG), "application_confirmation")

    def test_rejection_beats_interview_mention(self):
        # rejection emails often mention past interviews — rejection must win
        self.assertEqual(classify.classify_email(
            "Thank you for interviewing",
            "hr@acme.com",
            "Unfortunately we will not be moving forward", CFG), "rejection")

    def test_other(self):
        self.assertEqual(classify.classify_email(
            "Your receipt", "store@shop.com", "Thanks for your order", CFG),
            "other")


class TestStageGuard(unittest.TestCase):
    def test_forward_progress_allowed(self):
        self.assertTrue(config_mod.should_advance("Applied", "Interview", CFG))
        self.assertTrue(config_mod.should_advance("Phone Screen", "Round 2", CFG))

    def test_regression_blocked(self):
        # THE bug this guards: a late "Applied" email must not overwrite "Interview"
        self.assertFalse(config_mod.should_advance("Interview", "Applied", CFG))
        self.assertFalse(config_mod.should_advance("Final Round", "Phone Screen", CFG))

    def test_terminal_always_wins(self):
        self.assertTrue(config_mod.should_advance("Final Round", "Rejected", CFG))
        self.assertTrue(config_mod.should_advance("Applied", "Rejected", CFG))

    def test_terminal_does_not_flipflop(self):
        self.assertFalse(config_mod.should_advance("Rejected", "Withdrawn", CFG))

    def test_unknown_never_overwrites(self):
        self.assertFalse(config_mod.should_advance("Interview", "Some Custom Stage", CFG))
        self.assertTrue(config_mod.should_advance("", "Applied", CFG))

    def test_aliases(self):
        self.assertEqual(config_mod.canonical_stage("phone screen", CFG), "Phone Screen")
        self.assertTrue(config_mod.should_advance("Applied", "recruiter screen", CFG))


class TestExtraction(unittest.TestCase):
    def test_company_from_sender(self):
        self.assertEqual(classify.extract_company(
            "Thank you for applying", "Acme via Greenhouse",
            "jobs@greenhouse.io", "", CFG), "Acme")

    def test_company_from_subject(self):
        self.assertEqual(classify.extract_company(
            "Your application to Initech", "jobs", "jobs@initech.com", "", CFG),
            "Initech")

    def test_company_from_domain(self):
        self.assertEqual(classify.extract_company(
            "Interview next week", "Jane Doe", "jane@initech.com", "", CFG),
            "Initech")

    def test_ats_domain_skipped(self):
        self.assertEqual(classify.extract_company(
            "Application received", "Greenhouse", "jobs@greenhouse.io", "", CFG), "")

    def test_title_from_subject(self):
        self.assertEqual(classify.extract_title(
            "Thank you for applying for the Data Analyst position",
            "body here"), "Data Analyst")

    def test_detect_source(self):
        self.assertEqual(classify.detect_source("jobs@lever.co", CFG), "Lever")
        self.assertEqual(classify.detect_source("x@myworkday.com", CFG), "Workday")
        self.assertEqual(classify.detect_source("friend@gmail.com", CFG), "Direct")


class TestEmailToRecord(unittest.TestCase):
    def test_full_pipeline(self):
        rec = classify.email_to_record({
            "thread_id": "t1", "subject": "Thank you for applying",
            "sender_name": "Acme via Greenhouse",
            "sender_email": "jobs@greenhouse.io",
            "date": "2026-09-01", "snippet": "", "body": "We received your application",
        }, CFG)
        self.assertEqual(rec["event"], "application_confirmation")
        self.assertEqual(rec["company"], "Acme")
        self.assertEqual(rec["stage"], "Applied")
        self.assertEqual(rec["source"], "Greenhouse")
        self.assertFalse(rec["flag"])

    def test_low_confidence_flagged(self):
        rec = classify.email_to_record({
            "thread_id": "t2", "subject": "Hello",
            "sender_name": "Newsletter", "sender_email": "news@micro1.com",
            "date": "2026-09-01", "snippet": "weekly digest", "body": "",
        }, CFG)
        self.assertTrue(rec["flag"])


if __name__ == "__main__":
    unittest.main()
