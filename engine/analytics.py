#!/usr/bin/env python3
"""analytics.py — pure analytics over the application store.

No I/O. Takes plain dicts + config, returns plain dicts.
Unit-tested in tests/test_analytics.py.
"""
from datetime import date

from engine import classify


def days_since(d, today=None):
    """Days between an ISO date string and today; None if unparseable."""
    today = today or date.today()
    try:
        return (today - date.fromisoformat((d or "")[:10])).days
    except (ValueError, TypeError):
        return None


def enrich(store, cfg, today=None):
    """Attach derived fields to every application: family, seniority, sector,
    days_since, rejected/advanced/stale flags."""
    stale_days = cfg["thresholds"]["stale_days"]
    terminal = {(s or "").strip().lower() for s in cfg["stages"].get("terminal", [])}
    apps = []
    for a in store["applications"]:
        e = dict(a)
        e["family"] = classify.job_family(a.get("title"), cfg)
        e["seniority"] = classify.seniority(a.get("title"), cfg)
        e["sector"] = classify.sector(a.get("company"), cfg)
        e["days_since"] = days_since(a.get("date_applied", ""), today)
        e["rejected"] = (a.get("stage") or "").strip().lower() in terminal
        stage = (a.get("stage") or "").strip().lower()
        e["advanced"] = bool(a.get("interview")) or (
            stage not in ("applied",) and stage not in terminal and bool(stage)
        )
        e["stale"] = (
            stage == "applied"
            and not a.get("interview")
            and (e["days_since"] or 0) > stale_days
            and not e["rejected"]
        )
        apps.append(e)
    return apps


def seg_stats(apps, key):
    """Per-segment counts + interview/reply/rejected rates, sorted by
    interview rate desc, then count desc."""
    out = {}
    for a in apps:
        k = a.get(key) or "Other"
        d = out.setdefault(k, {"segment": k, "count": 0, "interviews": 0,
                               "replies": 0, "rejected": 0})
        d["count"] += 1
        d["interviews"] += 1 if a["advanced"] else 0
        d["replies"] += 1 if a.get("reply") else 0
        d["rejected"] += 1 if a["rejected"] else 0
    for d in out.values():
        d["interview_rate"] = round(100 * d["interviews"] / d["count"]) if d["count"] else 0
        d["reply_rate"] = round(100 * d["replies"] / d["count"]) if d["count"] else 0
    return sorted(out.values(), key=lambda x: (-x["interview_rate"], -x["count"]))


def stage_dist(apps):
    out = {}
    for a in apps:
        out[a.get("stage") or "Applied"] = out.get(a.get("stage") or "Applied", 0) + 1
    return out


def compute_metrics(apps):
    n = len(apps)
    interviews = sum(1 for a in apps if a["advanced"])
    replies = sum(1 for a in apps if a.get("reply"))
    rejected = sum(1 for a in apps if a["rejected"])
    active = n - rejected
    recent7 = sum(1 for a in apps if (a["days_since"] if a["days_since"] is not None else 999) <= 7)
    recent30 = sum(1 for a in apps if (a["days_since"] if a["days_since"] is not None else 999) <= 30)
    return {
        "total": n,
        "interviews": interviews,
        "replies": replies,
        "rejected": rejected,
        "active": active,
        "interview_rate": round(100 * interviews / n) if n else 0,
        "reply_rate": round(100 * replies / n) if n else 0,
        "applied_last_7": recent7,
        "applied_last_30": recent30,
        "by_family": seg_stats(apps, "family"),
        "by_source": seg_stats(apps, "source"),
        "by_seniority": seg_stats(apps, "seniority"),
        "by_sector": seg_stats(apps, "sector"),
        "stage_dist": stage_dist(apps),
    }


def networking_queue(store, cfg, today=None):
    """Warm/hot contacts not touched in `networking_gap_days`, hottest first."""
    gap = cfg["thresholds"]["networking_gap_days"]
    q = []
    for c in store.get("contacts", []):
        w = (c.get("warmth") or "cold").lower()
        lt = c.get("last_touch", "")
        days = days_since(lt, today) if lt else 999
        if w in ("hot", "warm") and days >= gap:
            cc = dict(c)
            cc["days_since_touch"] = days
            q.append(cc)
    rank = {"hot": 0, "warm": 1, "cold": 2}
    return sorted(q, key=lambda c: (rank.get((c.get("warmth") or "cold").lower(), 2),
                                    -(c.get("days_since_touch") or 0)))
