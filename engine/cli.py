#!/usr/bin/env python3
"""cli.py — the Career Decision Board command-line interface.

Usage (from the repo root):
  python -m engine.cli init                 create config + empty database
  python -m engine.cli scan                 Gmail API scan → merge → rebuild
  python -m engine.cli scan --imap          IMAP (app password) scan → merge → rebuild
  python -m engine.cli ingest <records.json>  merge a records file (e.g. from the LLM scan) → rebuild
  python -m engine.cli build                rebuild dashboard artifacts from the store
  python -m engine.cli xlsx                 rebuild the Job Tracker.xlsx mirror
  python -m engine.cli seed                 load clearly-labeled SAMPLE data (for trying the board)
  python -m engine.cli migrate <store.json> import a legacy store.json into the database
  python -m engine.cli cursor               print the scan cursor as JSON
  python -m engine.cli demo                 seed sample data + rebuild + refresh demo-data.json

Env vars: CAREERBOARD_CONFIG (config path), CAREERBOARD_DB (sqlite path).
Core commands need only the stdlib. `scan` needs the Gmail API packages;
`xlsx` needs openpyxl; the encrypted phone build needs `cryptography`.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import analytics, config as config_mod, render
from engine import store as store_mod


def _load_config(args):
    try:
        return config_mod.load(args.config)
    except config_mod.ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        sys.exit(2)


def cmd_init(args):
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dst = args.config or os.path.join(root, "config.json")
    if not os.path.exists(dst):
        print(f"config already at default location: {dst}")
    cfg = _load_config(args)
    with store_mod.Store(args.db) as st:
        st.seed_templates(cfg.get("templates", []))
    print(f"initialized — config: {dst}")
    print(f"database: {args.db or store_mod.DEFAULT_DB}")
    print("next: python -m engine.cli seed   # try with sample data, or")
    print("      python -m engine.cli scan   # scan your Gmail (see docs/SETUP.md)")


def _merge_records(store, cfg, records):
    """Merge ingest-schema records into the store. Returns counts."""
    counts = {"applications": 0, "interviews": 0, "contacts": 0, "leads": 0,
              "updated": 0}
    seen_threads = set()
    for rec in records.get("applications", []):
        tid = rec.get("thread_id", "")
        if tid and store.is_thread_processed(tid):
            continue
        action, _ = store.upsert_application(rec, cfg)
        if action == "added":
            counts["applications"] += 1
        elif action in ("stage_advanced", "updated"):
            counts["updated"] += 1
        if tid:
            seen_threads.add(tid)
    for rec in records.get("interviews", []):
        tid = rec.get("thread_id", "")
        if tid and store.is_thread_processed(tid):
            continue
        action, _ = store.add_interview(rec)
        if action == "added":
            counts["interviews"] += 1
        if tid:
            seen_threads.add(tid)
    for rec in records.get("contacts", []):
        action, _ = store.add_contact(rec)
        if action == "added":
            counts["contacts"] += 1
    for rec in records.get("leads", []):
        action, _ = store.add_lead(rec)
        if action == "added":
            counts["leads"] += 1
    for tid in seen_threads:
        store.mark_thread_processed(tid)
    if records.get("scanned_at"):
        store.set_cursor(records["scanned_at"])
    return counts


def cmd_scan(args):
    cfg = _load_config(args)
    if args.imap:
        from engine import ingest_imap
        print("scanning Gmail via IMAP…")
        records = ingest_imap.scan(cfg, progress=print)
    else:
        from engine import ingest_gmail
        print("scanning Gmail via API…")
        records = ingest_gmail.scan(cfg, progress=print)
    with store_mod.Store(args.db) as st:
        st.seed_templates(cfg.get("templates", []))
        counts = _merge_records(st, cfg, records)
        st.log_scan(note="gmail scan", apps_added=counts["applications"],
                    interviews_added=counts["interviews"],
                    leads_added=counts["leads"])
        data = st.to_dict(cfg.get("owner_name", "You"))
    render.write_dashboard(data, cfg)
    print(f"scan done — +{counts['applications']} apps, "
          f"+{counts['interviews']} interviews, +{counts['leads']} leads, "
          f"{counts['updated']} updated")


def cmd_ingest(args):
    cfg = _load_config(args)
    with open(args.records) as f:
        records = json.load(f)
    with store_mod.Store(args.db) as st:
        st.seed_templates(cfg.get("templates", []))
        counts = _merge_records(st, cfg, records)
        data = st.to_dict(cfg.get("owner_name", "You"))
    render.write_dashboard(data, cfg)
    print(f"ingest done — +{counts['applications']} apps, "
          f"+{counts['interviews']} interviews, +{counts['leads']} leads, "
          f"{counts['updated']} updated")


def cmd_build(args):
    cfg = _load_config(args)
    with store_mod.Store(args.db) as st:
        data = st.to_dict(cfg.get("owner_name", "You"))
    render.write_dashboard(data, cfg)


def cmd_xlsx(args):
    cfg = _load_config(args)
    with store_mod.Store(args.db) as st:
        data = st.to_dict(cfg.get("owner_name", "You"))
    render.render_xlsx(data, cfg, args.out)


def cmd_seed(args):
    from engine import seed_demo
    cfg = _load_config(args)
    with store_mod.Store(args.db) as st:
        n = seed_demo.seed(st, cfg)
    print(f"seeded {n} sample applications (clearly-labeled synthetic data)")
    cmd_build(args)


def cmd_migrate(args):
    cfg = _load_config(args)
    with open(args.store_json) as f:
        legacy = json.load(f)
    with store_mod.Store(args.db) as st:
        counts = st.import_legacy(legacy, cfg)
    print(f"migrated legacy store.json → {counts}")
    cmd_build(args)


def cmd_cursor(args):
    with store_mod.Store(args.db) as st:
        print(json.dumps(st.get_cursor(), indent=2))


def cmd_demo(args):
    """Regenerate the public demo artifacts from sample data."""
    from engine import seed_demo
    cfg = _load_config(args)
    with store_mod.Store(args.db) as st:
        seed_demo.seed(st, cfg, clear=True)
        data = st.to_dict("Demo")
    payload = render.build_payload(data, cfg, sample=True)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for d in (os.path.join(root, "web"), os.path.join(root, "docs")):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "demo-data.json"), "w") as f:
            json.dump(payload, f, indent=1)
        print(f"demo-data.json → {d} ({payload['metrics']['total']} apps)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Career Decision Board")
    ap.add_argument("--config", default=None, help="path to config.json")
    ap.add_argument("--db", default=None, help="path to careerboard.db")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create config + empty database")
    p = sub.add_parser("scan", help="scan Gmail, merge, rebuild")
    p.add_argument("--imap", action="store_true",
                   help="use IMAP + app password instead of the Gmail API")
    p = sub.add_parser("ingest", help="merge a records JSON file, rebuild")
    p.add_argument("records")
    sub.add_parser("build", help="rebuild dashboard artifacts")
    p = sub.add_parser("xlsx", help="rebuild the spreadsheet mirror")
    p.add_argument("--out", default=None)
    sub.add_parser("seed", help="load sample data")
    p = sub.add_parser("migrate", help="import a legacy store.json")
    p.add_argument("store_json")
    sub.add_parser("cursor", help="print the scan cursor")
    sub.add_parser("demo", help="regenerate public demo artifacts from sample data")

    args = ap.parse_args(argv)
    {"init": cmd_init, "scan": cmd_scan, "ingest": cmd_ingest,
     "build": cmd_build, "xlsx": cmd_xlsx, "seed": cmd_seed,
     "migrate": cmd_migrate, "cursor": cmd_cursor, "demo": cmd_demo}[args.cmd](args)


if __name__ == "__main__":
    main()
