#!/usr/bin/env python
"""x_capture_pw.py - X-vangst via Playwright (echte headless browser + jouw cookies).

Vervangt de twikit-route: twikit en tweety worden beide geblokt door X's anti-bot
(client-transaction-id / animation-key). Een ECHTE browser maakt die header zelf -> betrouwbaar
en bestand tegen X's periodieke updates. Leest de watchlist, opent elk X-profiel, schraapt de
tweets, schrijft nieuwe naar raw_store. Rust-pauzes tegen ban-risico.

Cookies: secrets/cookies.json (van extract_cookies.py - geen wachtwoord nodig).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import raw_store

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def load_watchlist():
    with open(os.path.join(HERE, "watchlist.json"), encoding="utf-8") as f:
        return json.load(f)


def _cookies(path):
    ck = json.load(open(path, encoding="utf-8"))
    return [{"name": k, "value": v, "domain": ".x.com", "path": "/"} for k, v in ck.items()]


def _parse_dt(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def capture(cookies_path, raw_db, lookback_min=180, per_account=15, delay_sec=4.0, headless=True):
    from playwright.sync_api import sync_playwright
    conn = raw_store.connect(raw_db)
    wl = load_watchlist()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_min)
    new = dups = errs = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 1800})
        ctx.add_cookies(_cookies(cookies_path))
        page = ctx.new_page()
        for acc in wl["x_accounts"]:
            handle = acc["handle"].lstrip("@")
            try:
                page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=40000)
                try:
                    page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
                except Exception:
                    pass
                arts = page.query_selector_all('article[data-testid="tweet"]')[:per_account]
                for a in arts:
                    tnode = a.query_selector('div[data-testid="tweetText"]')
                    txt = tnode.inner_text() if tnode else ""
                    if not txt:
                        continue
                    tm = a.query_selector("time")
                    posted = _parse_dt(tm.get_attribute("datetime") if tm else None)
                    if posted and posted < cutoff:
                        continue
                    link = a.query_selector('a[href*="/status/"]')
                    href = link.get_attribute("href") if link else ""
                    pid = href.rsplit("/status/", 1)[-1] if "/status/" in href else None
                    url = ("https://x.com" + href) if href.startswith("/") else href
                    ok = raw_store.add_raw(
                        conn, "x", acc["handle"], txt, post_id=pid,
                        author=acc.get("name") or acc["handle"], url=url,
                        posted_at=(posted.isoformat() if posted else None),
                    )
                    new += 1 if ok else 0
                    dups += 0 if ok else 1
            except Exception as e:
                errs += 1
                print(f"  [x] {handle}: {type(e).__name__}: {str(e)[:80]}")
            time.sleep(delay_sec)   # rust-pauze tussen accounts (ban-mitigatie)
        browser.close()
    conn.close()
    print(f"x_capture_pw: nieuw={new} dup={dups} errors={errs} accounts={len(wl['x_accounts'])}")
    return {"new": new, "dup": dups, "errors": errs}


if __name__ == "__main__":
    import config_loader
    cfg = config_loader.load()
    capture(cfg["x_cookies"], cfg["raw_db"], cfg.get("lookback_min", 180),
            cfg.get("x_per_account", 15), cfg.get("x_delay_sec", 4.0))
