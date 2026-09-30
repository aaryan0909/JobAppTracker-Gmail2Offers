#!/usr/bin/env python3
"""config.py — load and validate config.json (stdlib only, no dependencies).

The config file is the single place a user customizes the board:
Gmail queries, classification keywords, stage order, thresholds, templates.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_CONFIG = os.path.join(ROOT, "config.json")

_REQUIRED_TOP = ["owner_name", "gmail", "classification", "stages", "thresholds"]
_REQUIRED_THRESHOLDS = [
    "stale_days", "momentum_window_days", "momentum_target",
    "lead_fresh_days", "networking_gap_days", "min_segment_count",
]


class ConfigError(Exception):
    pass


def load(path=None):
    """Load config.json, validate the shape, and return the dict.

    Raises ConfigError with a human-readable message on any problem.
    """
    path = path or os.environ.get("CAREERBOARD_CONFIG", DEFAULT_CONFIG)
    if not os.path.exists(path):
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Copy config.json from the repo (or set CAREERBOARD_CONFIG) and edit it."
        )
    try:
        with open(path) as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Config file {path} is not valid JSON: {e}")

    for key in _REQUIRED_TOP:
        if key not in cfg:
            raise ConfigError(f"Config file {path} is missing required key: '{key}'")
    for key in _REQUIRED_THRESHOLDS:
        if key not in cfg["thresholds"]:
            raise ConfigError(
                f"Config file {path}: thresholds is missing required key: '{key}'"
            )
    stages = cfg["stages"]
    if not stages.get("order"):
        raise ConfigError(f"Config file {path}: stages.order must be a non-empty list")
    if "terminal" not in stages:
        raise ConfigError(f"Config file {path}: stages.terminal is required")
    return cfg


def stage_rank(stage, cfg):
    """Numeric rank of a stage for forward-progress comparison. Terminal
    stages rank above everything; unknown stages rank 0 (never regress)."""
    stages = cfg["stages"]
    order = stages["order"]
    terminal = set(stages.get("terminal", []))
    s = (stage or "").strip()
    if s in terminal:
        return len(order) + 100
    try:
        return order.index(s) + 1
    except ValueError:
        return 0


def canonical_stage(stage, cfg):
    """Map a raw stage label to its canonical form via aliases."""
    aliases = cfg["stages"].get("aliases", {})
    s = (stage or "").strip()
    return aliases.get(s.lower(), s)


def should_advance(old_stage, new_stage, cfg):
    """True if new_stage represents forward progress (or a terminal outcome)
    from old_stage. Guards against out-of-order scans regressing a stage —
    e.g. a late-arriving 'Applied' email must not overwrite 'Interview'.

    Terminal stages always win (a rejection is news even after a final round).
    Unknown stages never overwrite a known one.
    """
    old_c = canonical_stage(old_stage, cfg)
    new_c = canonical_stage(new_stage, cfg)
    if not new_c:
        return False
    if new_c == old_c:
        return False
    terminal = set(cfg["stages"].get("terminal", []))
    if new_c in terminal:
        return old_c not in terminal  # don't flip-flop between terminal states
    if not old_c:
        return True
    return stage_rank(new_c, cfg) > stage_rank(old_c, cfg)
