#!/usr/bin/env python3
"""Generate web/demo-data.json: a realistic but fully ANONYMIZED payload for the
public GitHub Pages demo. Reuses the real engine logic; scrubs all PII."""
import json, os, re, copy
import career_lib as CL

store = json.load(open(os.path.join(CL.HERE, "store.json")))
anon = copy.deepcopy(store)

POOL = ["Northwind Tech","Acme Analytics","Lumen Financial","Vertex Labs","Cobalt Systems",
"Meridian Bank","Helix AI","Atlas Logistics","Orion Health","Solstice Media","Granite Capital",
"Pinnacle Retail","Beacon Software","Cascade Energy","Summit Consulting","Vega Gaming",
"Quill Fintech","Harbor Data","Nimbus Cloud","Ironwood Industrial","Kestrel Strategy",
"Onyx Payments","Polaris Research","Sage Ventures","Tidal Commerce","Umbra Security",
"Willow HealthTech","Zephyr Mobility","Drift Marketing","Ember Robotics","Cedar Capital",
"Flint Mobility","Garnet Group","Hollow Tree Foods","Indigo Insights","Juniper Bank"]

companies = []
for sec in (anon["applications"], anon["interviews"], anon.get("leads",[]), anon["contacts"]):
    for r in sec:
        c = r.get("company")
        if c and c not in companies: companies.append(c)
cmap = {c: POOL[i % len(POOL)] + ("" if i < len(POOL) else f" {i//len(POOL)+1}") for i,c in enumerate(sorted(companies))}

def scrub_emails(s): return re.sub(r"[\w.+-]+@[\w.-]+", "contact@example.com", s or "")

for a in anon["applications"]:
    a["company"] = cmap.get(a["company"], a["company"]); a["notes"]=""; a["url"]=""
for iv in anon["interviews"]:
    iv["company"] = cmap.get(iv["company"], iv["company"])
    iv["interviewer"] = "Talent Team"
    iv["details"] = scrub_emails(iv["details"])
for l in anon.get("leads",[]):
    l["company"] = cmap.get(l["company"], l["company"]); l["url"]=""
roles = ["Recruiter","Hiring Manager","Talent Partner","Team Lead","Director"]
for i,c in enumerate(anon["contacts"]):
    c["name"] = f"{roles[i%len(roles)]} {chr(65+i%26)}"
    c["company"] = cmap.get(c["company"], c["company"])
    c["email"] = f"contact{i+1}@example.com"; c["phone"]=""; c["linkedin"]=""
    c["title"] = c.get("title","Recruiter"); c["context"]="(demo)"
anon["meta"]["owner_name"] = "Demo"

payload = CL.build_payload(anon)

# final belt-and-suspenders text pass: scrub any residual names / emails
s = json.dumps(payload, indent=2)
for a, b in [("Aaryan Chawla", "Alex Doe"), ("Aaryan", "Alex"), ("Chawla", "Doe")]:
    s = s.replace(a, b)
s = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", "contact@example.com", s)

out = os.path.join(CL.ROOT, "web", "demo-data.json")
open(out, "w").write(s)
import json as _j; pl = _j.loads(s)
print(f"✅ demo-data.json written: {pl['metrics']['total']} apps, "
      f"{len(pl['recommendations'])} recs, all anonymized → {out}")
