#!/usr/bin/env python3
"""career_lib.py — backward-compatibility shim (v1 API).

The engine was split into focused modules (config, classify, analytics,
recommend, store, crypto, render, cli). This file keeps the old CLI working:

    python3 engine/career_lib.py build | cursor | ingest <file> | xlsx

New code should use `python -m engine.cli ...` instead. If a legacy
store.json exists next to this file it is migrated into the SQLite store
on first run; afterwards the database is the source of truth.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import cli as _cli  # noqa: E402
from engine import config as config_mod  # noqa: E402
from engine import store as store_mod  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(HERE, "store.json")


def _maybe_migrate():
    if os.path.exists(LEGACY):
        cfg = config_mod.load()
        with open(LEGACY) as f:
            legacy = json.load(f)
        with store_mod.Store() as st:
            counts = st.import_legacy(legacy, cfg)
        os.rename(LEGACY, LEGACY + ".migrated")
        print(f"migrated legacy store.json → sqlite {counts} (renamed to store.json.migrated)")


def main(argv):
    _maybe_migrate()
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "build":
        _cli.main(["build"])
    elif cmd == "cursor":
        _cli.main(["cursor"])
    elif cmd == "ingest":
        if len(argv) < 3:
            print("usage: career_lib.py ingest <records.json>")
            sys.exit(1)
        _cli.main(["ingest", argv[2]])
    elif cmd == "xlsx":
        _cli.main(["xlsx"])
    else:
        print("usage: career_lib.py [build|cursor|ingest <file>|xlsx]")
        print("  (new CLI: python -m engine.cli --help)")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
