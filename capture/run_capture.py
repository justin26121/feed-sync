#!/usr/bin/env python
"""run_capture.py - draait X (Playwright) + Telegram (telethon) vangst (op de VM, op een cron).

X = sync Playwright (echte browser); TG = async telethon. Daarom: X eerst (sync), dan TG via
asyncio.run (een sync Playwright-call mag NIET binnen een asyncio-loop draaien).
"""
import os
import sys
import asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config_loader
import raw_store
import x_capture_pw
import tg_capture


def main():
    cfg = config_loader.load()
    rx = x_capture_pw.capture(
        cfg["x_cookies"], cfg["raw_db"], cfg.get("lookback_min", 180),
        cfg.get("x_per_account", 15), cfg.get("x_delay_sec", 4.0),
    )
    rt = asyncio.run(tg_capture.capture(
        cfg["tg_session"], cfg["tg_api_id"], cfg["tg_api_hash"],
        cfg["raw_db"], cfg.get("lookback_min", 180), cfg.get("tg_per_channel", 30),
    ))
    conn = raw_store.connect(cfg["raw_db"])
    print("raw_store:", raw_store.stats(conn))
    conn.close()
    print(f"TOTAAL nieuw deze run: X={rx['new']} TG={rt['new']}")


if __name__ == "__main__":
    main()
