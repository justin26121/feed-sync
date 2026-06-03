#!/usr/bin/env python
"""tg_capture.py - Telegram-vangst via telethon (gratis, leest jouw kanalen).

Draait op de VM. Credentials = api_id + api_hash (gratis van my.telegram.org) + een
.session-bestand (eerste keer interactief: telefoon + code). Geen wachtwoord in code.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import raw_store


def load_watchlist():
    with open(os.path.join(HERE, "watchlist.json"), encoding="utf-8") as f:
        return json.load(f)


async def capture(session, api_id, api_hash, raw_db, lookback_min=180, per_channel=30):
    from telethon import TelegramClient
    client = TelegramClient(session, api_id, api_hash)
    await client.start()   # gebruikt .session; eerste keer telefoon + code (interactief, lokaal)
    conn = raw_store.connect(raw_db)
    wl = load_watchlist()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_min)
    new = dups = errs = 0
    for ch in wl["telegram_channels"]:
        name = ch["channel"]
        try:
            async for msg in client.iter_messages(name, limit=per_channel):
                if not msg.text:
                    continue
                ts = msg.date
                if ts and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts and ts < cutoff:
                    break   # iter_messages loopt nieuw -> oud
                ok = raw_store.add_raw(
                    conn, "tg", name, msg.text, post_id=str(msg.id),
                    author=ch.get("name") or name,
                    url=f"https://t.me/{name}/{msg.id}",
                    posted_at=(ts.isoformat() if ts else None),
                )
                new += 1 if ok else 0
                dups += 0 if ok else 1
        except Exception as e:
            errs += 1
            print(f"  [tg] {name}: {type(e).__name__}: {str(e)[:90]}")
    conn.close()
    await client.disconnect()
    print(f"tg_capture: nieuw={new} dup={dups} errors={errs} kanalen={len(wl['telegram_channels'])}")
    return {"new": new, "dup": dups, "errors": errs}


if __name__ == "__main__":
    import config_loader
    cfg = config_loader.load()
    asyncio.run(capture(cfg["tg_session"], cfg["tg_api_id"], cfg["tg_api_hash"],
                        cfg["raw_db"], cfg.get("lookback_min", 180), cfg.get("tg_per_channel", 30)))
