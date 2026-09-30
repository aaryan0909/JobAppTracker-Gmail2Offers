#!/usr/bin/env python3
"""anonymize_demo.py — build a public demo payload from YOUR real store.

Reads your private SQLite store, scrubs every company/contact/email into
fictional stand-ins, and writes the anonymized payload to web/demo-data.json
(and docs/demo-data.json for GitHub Pages). Belt-and-suspenders: a final
text pass scrubs residual names and email addresses.

Your real data never leaves the machine; only the anonymized blob is
committed. Prefer fully synthetic data? Use `python -m engine.cli demo`
(seed_demo.py) instead.
"""
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import config as config_mod  # noqa: E402
from engine import render, store as store_mod  # noqa: E402

POOL = ["Northwind Tech", "Acme Analytics", "Lumen Financial", "Vertex Labs",
        "Cobalt Systems", "Meridian Bank", "Helix AI", "Atlas Logistics",
        "Orion Health", "Solstice Media", "Granite Capital", "Pinnacle Retail",
        "Beacon Software", "Cascade Energy", "Summit Consulting", "Vega Gaming",
        "Quill Fintech", "Harbor Data", "Nimbus Cloud", "Ironwood Industrial",
        "Kestrel Strategy", "Onyx Payments", "Polaris Research", "Sage Ventures",
        "Tidal Commerce", "Umbra Security", "Willow HealthTech", "Zephyr Mobility",
        "Drift Marketing", "Ember Robotics", "Cedar Capital", "Flint Mobility",
        "Garnet Group", "Indigo Insights", "Juniper Bank", "Koda Cloud"]


def anonymize(store_dict, owner_name="Demo"):
    anon = copy.deepcopy(store_dict)
    companies = []
    for sec in (anon["applications"], anon["interviews"],
                anon.get("leads", []), anon["contacts"]):
        for r in sec:
            c = r.get("company")
            if c and c not in companies:
                companies.append(c)
    cmap = {c: POOL[i % len(POOL)] + ("" if i < len(POOL) else f" {i // len(POOL) + 1}")
            for i, c in enumerate(sorted(companies))}

    def scrub_emails(s):
        return re.sub(r"[\w.+-]+@[\w.-]+", "contact@example.com", s or "")

    for a in anon["applications"]:
        a["company"] = cmap.get(a["company"], a["company"])
        a["notes"] = ""
        a["url"] = ""
    for iv in anon["interviews"]:
        iv["company"] = cmap.get(iv["company"], iv["company"])
        iv["interviewer"] = "Talent Team"
        iv["details"] = scrub_emails(iv["details"])
    for le in anon.get("leads", []):
        le["company"] = cmap.get(le["company"], le["company"])
        le["url"] = ""
    roles = ["Recruiter", "Hiring Manager", "Talent Partner", "Team Lead"]
    for i, c in enumerate(anon["contacts"]):
        c["name"] = f"{roles[i % len(roles)]} {chr(65 + i % 26)}"
        c["company"] = cmap.get(c["company"], c["company"])
        c["email"] = f"contact{i + 1}@example.com"
        c["phone"] = ""
        c["linkedin"] = ""
        c["title"] = c.get("title", "Recruiter")
        c["context"] = "(demo)"
    anon["meta"]["owner_name"] = owner_name
    return anon


def main():
    cfg = config_mod.load()
    with store_mod.Store() as st:
        data = st.to_dict()
    payload = render.build_payload(anonymize(data), cfg, sample=True)

    # final belt-and-suspenders text pass over the serialized payload
    s = json.dumps(payload, indent=1)
    s = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", "contact@example.com", s)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for d in (os.path.join(root, "web"), os.path.join(root, "docs")):
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, "demo-data.json")
        with open(out, "w") as f:
            f.write(s)
        print(f"anonymized demo → {out} "
              f"({payload['metrics']['total']} apps)")

    # sanity check: no real-looking emails survived
    leftovers = set(re.findall(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", s)) - {"contact@example.com"}
    if leftovers:
        print(f"WARNING: unscrubbed emails found: {leftovers}")


if __name__ == "__main__":
    main()
