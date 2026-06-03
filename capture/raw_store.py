#!/usr/bin/env python
"""raw_store.py - duurzame ruwe-opslag voor gevangen posts (op de VM).

De vangers (x_capture/twikit, tg_capture/telethon) schrijven hier elke nieuwe post in.
Dedup via payload_hash (UNIQUE) zodat dezelfde post nooit dubbel landt. De lokale
intake.py leest de nog-niet-verwerkte rijen (ingested=0) en zet ze door naar events.db.

Bewust simpel + zelfstandig (alleen stdlib sqlite3) zodat dit ook op een kale
Oracle-VM draait zonder de rest van de repo.
"""
import sqlite3
import hashlib
import os
from datetime import datetime, timezone

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_store.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route TEXT NOT NULL,            -- 'x' | 'tg'
    handle TEXT NOT NULL,           -- '@handle' of kanaal-id
    author TEXT,                    -- weergavenaam
    post_id TEXT,                   -- tweet-id / message-id
    text TEXT NOT NULL,
    url TEXT,
    posted_at TEXT,                 -- ISO (bron-tijd)
    captured_at TEXT NOT NULL,      -- ISO (wanneer wij het vingen)
    payload_hash TEXT NOT NULL UNIQUE,
    ingested INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_raw_ingested ON raw_posts(ingested);
CREATE INDEX IF NOT EXISTS idx_raw_captured ON raw_posts(captured_at);
"""


def _hash(route, handle, post_id, text):
    basis = f"{route}|{handle}|{post_id or ''}|{(text or '')[:200]}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def connect(db_path=None):
    conn = sqlite3.connect(db_path or DEFAULT_DB, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")   # wacht i.p.v. direct 'locked' bij gelijktijdige toegang
    conn.executescript(SCHEMA)
    return conn


def add_raw(conn, route, handle, text, post_id=None, author=None, url=None, posted_at=None):
    """Voeg een ruwe post toe. Returns True als nieuw, False als duplicaat."""
    h = _hash(route, handle, post_id, text)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        conn.execute(
            """INSERT INTO raw_posts(route, handle, author, post_id, text, url, posted_at, captured_at, payload_hash)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (route, handle, author, post_id, text, url, posted_at, now, h),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicaat (payload_hash bestaat al)


def get_uningested(conn, limit=500):
    cur = conn.execute(
        "SELECT id, route, handle, author, post_id, text, url, posted_at FROM raw_posts WHERE ingested=0 ORDER BY id LIMIT ?",
        (limit,),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def mark_ingested(conn, ids):
    if not ids:
        return
    conn.executemany("UPDATE raw_posts SET ingested=1 WHERE id=?", [(i,) for i in ids])
    conn.commit()


def stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM raw_posts").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM raw_posts WHERE ingested=0").fetchone()[0]
    return {"total": total, "pending": pending, "ingested": total - pending}


if __name__ == "__main__":
    c = connect()
    print("raw_store:", stats(c))
