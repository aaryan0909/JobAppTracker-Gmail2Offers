#!/usr/bin/env python3
"""recommend.py — the decision-board recommendations engine.

Pure functions: takes enriched applications + store dict + metrics + config,
returns ranked next-actions. All thresholds come from config.json —
no hardcoded numbers, no personal channel names.
"""
from engine import analytics, classify


def recommendations(apps, store, metrics, cfg):
    th = cfg["thresholds"]
    min_n = th["min_segment_count"]
    low_value = [c.lower() for c in cfg.get("low_value_channels", [])]
    recs = []

    def add(priority, kind, title, detail, action=None, items=None):
        recs.append({"priority": priority, "kind": kind, "title": title,
                     "detail": detail, "action": action, "items": items or []})

    terminal = set(cfg["stages"].get("terminal", []))

    # 1) Active advanced opportunities — highest priority
    hot = [a for a in apps
           if a["advanced"] and not a["rejected"]
           and (a.get("stage") or "").strip().lower() != "applied"]
    hot_sorted = sorted(hot, key=lambda a: (("offer" not in (a.get("stage") or "").lower()),
                                            a.get("company", "")))
    if hot_sorted:
        items = [{"label": f'{a["company"]} — {a["title"]}', "sub": a["stage"]}
                 for a in hot_sorted[:8]]
        add(1, "opportunity", "Active opportunities need your attention",
            f"{len(hot_sorted)} application(s) are mid-process. Keep momentum: "
            "confirm timing, prep, and send thank-yous within 24h of each round.",
            "Open Pipeline → focus on these", items)

    # 2) Offer decision
    offers = [a for a in apps if "offer" in (a.get("stage") or "").lower()
              and (a.get("stage") or "").strip() not in terminal]
    if offers:
        items = [{"label": f'{a["company"]} — {a["title"]}', "sub": a["stage"]}
                 for a in offers]
        add(1, "decision", "You have an offer / imminent offer",
            "Decide and respond promptly — even a decline should be gracious and "
            "fast to protect the relationship. A decline draft is in your Templates tab.",
            "Send your decision", items)

    # 3) Best-converting segment → double down; zero-converting → rethink
    fam = [s for s in metrics["by_family"] if s["count"] >= min_n]
    if fam:
        best = fam[0]
        if best["interview_rate"] > 0:
            add(2, "strategy", f'Lean into {best["segment"]} roles',
                f'Your strongest segment: {best["interview_rate"]}% reach interview '
                f'({best["interviews"]}/{best["count"]}). This beats your '
                f'{metrics["interview_rate"]}% overall — prioritise more of these.',
                f'Search & apply to more {best["segment"]} roles')
        worst = [s for s in fam if s["interview_rate"] == 0]
        if worst:
            w = max(worst, key=lambda x: x["count"])
            add(3, "strategy", f'Re-think your {w["segment"]} approach',
                f'{w["count"]} {w["segment"]} applications, 0 interviews so far. '
                "Either tailor the resume/keywords for these or reallocate effort "
                "to higher-converting families.",
                "Review or pause this segment")

    # 4) Best channel (excluding configured low-value channels)
    src = [s for s in metrics["by_source"]
           if s["count"] >= min_n
           and not any(lv in s["segment"].lower() for lv in low_value)]
    if src and src[0]["interview_rate"] > metrics["interview_rate"]:
        s = src[0]
        add(3, "insight", f'{s["segment"]} is your best channel',
            f'Roles via {s["segment"]} convert at {s["interview_rate"]}% vs '
            f'{metrics["interview_rate"]}% overall. Favor postings on this channel.',
            None)

    # 5) Stale applications → re-engage or archive
    stale = [a for a in apps if a["stale"]]
    if stale:
        items = [{"label": f'{a["company"]} — {a["title"]}',
                  "sub": f'{a["days_since"]}d, no reply'}
                 for a in sorted(stale, key=lambda a: -(a["days_since"] or 0))[:10]]
        add(2, "cleanup", f"Re-engage or archive {len(stale)} stalled applications",
            f"These have sat >{th['stale_days']} days with no movement. Send the "
            "'re-engage' template to the recruiter, or mark them closed to keep "
            "your board honest.",
            "Use the Re-engage template", items)

    # 6) Networking queue — warm contacts not touched recently
    queue = analytics.networking_queue(store, cfg)
    if queue:
        items = [{"label": f'{c["name"]} — {c["company"]}', "sub": c.get("title", "")}
                 for c in queue[:8]]
        add(2, "network", f"Reach out to {len(queue)} warm contacts",
            "Relationships decay. These people already know you — a short check-in "
            "keeps you top of mind for current and future roles.",
            "Open Network tab → send a note", items)

    # 7) Momentum / cadence
    window, target = th["momentum_window_days"], th["momentum_target"]
    recent = sum(1 for a in apps
                 if (a["days_since"] if a["days_since"] is not None else 999) <= window)
    if recent < target:
        add(3, "momentum", "Keep your application momentum up",
            f"Only {recent} new applications in the last {window} days. Aim for a "
            "steady weekly cadence in your best-converting families to keep the "
            "pipeline full.",
            "Block time to apply this week")
    else:
        add(4, "momentum", "Strong momentum",
            f"{recent} applications in the last {window} days. Nice pace — make sure "
            "follow-ups and prep keep up with volume.")

    # 8) Job-alert leads → match to strong families
    leads = store.get("leads", [])
    fresh = [l for l in leads
             if (analytics.days_since(l.get("date", "")) or 999) <= th["lead_fresh_days"]]
    if fresh:
        strong = {s["segment"] for s in metrics["by_family"]
                  if s["count"] >= min_n
                  and s["interview_rate"] >= metrics["interview_rate"]}
        matched = [l for l in fresh
                   if classify.job_family(l.get("title", ""), cfg) in strong]
        items = [{"label": f'{l.get("company", "?")} — {l.get("title", "")}',
                  "sub": classify.job_family(l.get("title", ""), cfg)}
                 for l in (matched or fresh)[:8]]
        suffix = f" · {len(matched)} in your strong families" if matched else ""
        add(3, "leads", f"{len(fresh)} new job leads from alerts{suffix}",
            "From your job-alert emails. Prioritise the ones in families where you "
            "already convert well — that's where your effort pays off.",
            "Apply to the best-fit leads", items)

    # 9) Interview prep / recent rounds
    ints = sorted(store.get("interviews", []), key=lambda x: x.get("date", ""),
                  reverse=True)
    if ints:
        recent_ints = ints[:3]
        items = [{"label": f'{i["company"]} — {i.get("round", "")}',
                  "sub": i.get("date", "")} for i in recent_ints]
        add(4, "prep", "Recent interview activity",
            "Review notes from these rounds and confirm any outstanding next steps.",
            "Open Interviews tab", items)

    recs.sort(key=lambda r: r["priority"])
    return recs
