#!/usr/bin/env python
"""config_loader.py - laadt config.json (jouw sleutels). Geheimen NOOIT in de repo."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    p = os.path.join(HERE, "config.json")
    if not os.path.exists(p):
        raise SystemExit(
            "config.json ontbreekt -> kopieer config.example.json naar config.json en vul je sleutels in."
        )
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    # relatieve paden absoluut maken t.o.v. de capture-map
    for k in ("x_cookies", "tg_session", "raw_db"):
        if cfg.get(k) and not os.path.isabs(cfg[k]):
            cfg[k] = os.path.join(HERE, cfg[k])
    return cfg
