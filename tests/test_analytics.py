#!/usr/bin/env python3
"""Tests for engine/analytics.py and engine/recommend.py."""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import analytics, config as config_mod, recommend  # noqa: E402

CFG = config_mod.load(os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "config.json"))
TODAY = date(2026, 9, 30)


def app(id, title, company, stage, days_ago, **kw):
    d = (TODAY - timedelta(days=days_ago)).isoformat()
    a = {"id": id, "title": title, "company": company, "stage": stage,
         "date_applied": d, "source": "Greenhouse", "reply": True,
         "interview": False, "flag": False, "notes": ""}
    a.update(kw)
    return a


class TestEnrich(unittest.TestCase):
    def test_stale(self):
        apps = analytics.enrich(
            {"applications": [app(1, "Data Analyst", "Acme", "Applied", 30)]},
            CFG, TODAY)
        self.assertTrue(apps[0]["stale"])

    def test_not_stale_if_recent(self):
        apps = analytics.enrich(
            {"applications": [app(1, "Data Analyst", "Acme", "Applied", 5)]},
            CFG, TODAY)
        self.assertFalse(apps[0]["stale"])

    def test_advanced_flag(self):
        apps = analytics.enrich(
            {"applications": [app(1, "Data Analyst", "Acme", "Interview", 5,
                                  interview=True)]},
            CFG, TODAY)
        self.assertTrue(apps[0]["advanced"])
        self.assertFalse(apps[0]["rejected"])

    def test_rejected_terminal(self):
        apps = analytics.enrich(
            {"applications": [app(1, "Data Analyst", "Acme", "Rejected", 5)]},
            CFG, TODAY)
        self.assertTrue(apps[0]["rejected"])
        self.assertFalse(apps[0]["advanced"])
        self.assertFalse(apps[0]["stale"])

    def test_family_attached(self):
        apps = analytics.enrich(
            {"applications": [app(1, "Data Analyst", "Acme", "Applied", 5)]},
            CFG, TODAY)
        self.assertEqual(apps[0]["family"], "Data & Analytics")


class TestSegStats(unittest.TestCase):
    def test_rates_and_sort(self):
        store = {"applications": [
            app(1, "Data Analyst", "A", "Interview", 5, interview=True),
            app(2, "Data Analyst", "B", "Applied", 5),
            app(3, "Product Manager", "C", "Applied", 5),
        ]}
        apps = analytics.enrich(store, CFG, TODAY)
        stats = analytics.seg_stats(apps, "family")
        by_name = {s["segment"]: s for s in stats}
        self.assertEqual(by_name["Data & Analytics"]["interview_rate"], 50)
        self.assertEqual(by_name["Product"]["interview_rate"], 0)
        self.assertEqual(stats[0]["segment"], "Data & Analytics")  # sorted first


class TestMetrics(unittest.TestCase):
    def test_empty(self):
        m = analytics.compute_metrics([])
        self.assertEqual(m["total"], 0)
        self.assertEqual(m["interview_rate"], 0)

    def test_counts(self):
        store = {"applications": [
            app(1, "Data Analyst", "A", "Interview", 3, interview=True),
            app(2, "Data Analyst", "B", "Rejected", 40),
            app(3, "Data Analyst", "C", "Applied", 40),
        ]}
        apps = analytics.enrich(store, CFG, TODAY)
        m = analytics.compute_metrics(apps)
        self.assertEqual(m["total"], 3)
        self.assertEqual(m["interviews"], 1)
        self.assertEqual(m["rejected"], 1)
        self.assertEqual(m["active"], 2)
        self.assertEqual(m["applied_last_7"], 1)
        self.assertEqual(m["applied_last_30"], 1)


class TestNetworkingQueue(unittest.TestCase):
    def test_gap_filter(self):
        recent = (TODAY - timedelta(days=3)).isoformat()
        old = (TODAY - timedelta(days=30)).isoformat()
        store = {"contacts": [
            {"name": "A", "company": "X", "warmth": "warm", "last_touch": recent},
            {"name": "B", "company": "Y", "warmth": "warm", "last_touch": old},
            {"name": "C", "company": "Z", "warmth": "cold", "last_touch": old},
        ]}
        q = analytics.networking_queue(store, CFG, TODAY)
        self.assertEqual([c["name"] for c in q], ["B"])


class TestRecommendations(unittest.TestCase):
    def _recs(self, applications, extra=None):
        store = {"applications": applications, "interviews": [],
                 "contacts": [], "leads": [], "templates": []}
        if extra:
            store.update(extra)
        apps = analytics.enrich(store, CFG, TODAY)
        m = analytics.compute_metrics(apps)
        return recommend.recommendations(apps, store, m, CFG)

    def test_offer_is_top_priority(self):
        recs = self._recs([
            app(1, "Data Analyst", "Acme", "Offer", 5, interview=True),
            app(2, "Data Analyst", "Beta", "Applied", 40),
        ])
        self.assertEqual(recs[0]["kind"], "opportunity")
        kinds = [r["kind"] for r in recs]
        self.assertIn("decision", kinds)

    def test_stale_surfaces_cleanup(self):
        recs = self._recs([app(1, "Data Analyst", "Acme", "Applied", 30)])
        kinds = [r["kind"] for r in recs]
        self.assertIn("cleanup", kinds)

    def test_momentum_low(self):
        recs = self._recs([app(1, "Data Analyst", "Acme", "Applied", 2)])
        kinds = [r["kind"] for r in recs]
        self.assertIn("momentum", kinds)

    def test_empty_store_no_crash(self):
        recs = self._recs([])
        self.assertTrue(all("priority" in r for r in recs))

    def test_sorted_by_priority(self):
        recs = self._recs([
            app(1, "Data Analyst", "Acme", "Offer", 5, interview=True),
            app(2, "Data Analyst", "Beta", "Applied", 40),
        ])
        prios = [r["priority"] for r in recs]
        self.assertEqual(prios, sorted(prios))


if __name__ == "__main__":
    unittest.main()
