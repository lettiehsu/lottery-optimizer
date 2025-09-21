# lottery_store.py — SQLite-backed history store with dated BLOB output
from __future__ import annotations
import os
import sqlite3
from typing import List

DB_PATH = os.environ.get("LOTTERY_DB", "lottery.db")

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = _conn()
    try:
        cur = con.cursor()
        # Mega Millions (5 mains + bonus)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS mm_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT,         -- ISO YYYY-MM-DD if available
            n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
            bonus INTEGER,          -- mega ball
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Powerball (5 mains + bonus)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pb_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT,
            n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
            bonus INTEGER,          -- powerball
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # IL Lotto jackpot/millions (6 mains, tier = 'JP' | 'M1' | 'M2')
        cur.execute("""
        CREATE TABLE IF NOT EXISTS il_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT,
            tier TEXT,              -- 'JP','M1','M2'
            n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER, n6 INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        con.commit()
    finally:
        con.close()

# ----------------- Insert helpers -----------------

def add_mm(mains5: List[int], bonus: int, draw_date: str | None = None):
    if len(mains5) != 5:
        raise ValueError("MM mains must be length 5")
    con = _conn()
    try:
        con.execute(
            "INSERT INTO mm_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
            (draw_date, mains5[0], mains5[1], mains5[2], mains5[3], mains5[4], bonus)
        )
        con.commit()
    finally:
        con.close()

def add_pb(mains5: List[int], bonus: int, draw_date: str | None = None):
    if len(mains5) != 5:
        raise ValueError("PB mains must be length 5")
    con = _conn()
    try:
        con.execute(
            "INSERT INTO pb_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
            (draw_date, mains5[0], mains5[1], mains5[2], mains5[3], mains5[4], bonus)
        )
        con.commit()
    finally:
        con.close()

def add_il(mains6: List[int], tier: str, draw_date: str | None = None):
    if len(mains6) != 6:
        raise ValueError("IL mains must be length 6")
    if tier not in ("JP", "M1", "M2"):
        raise ValueError("tier must be 'JP','M1','M2'")
    con = _conn()
    try:
        con.execute(
            "INSERT INTO il_draws(draw_date,tier,n1,n2,n3,n4,n5,n6) VALUES(?,?,?,?,?,?,?,?)",
            (draw_date, tier, mains6[0], mains6[1], mains6[2], mains6[3], mains6[4], mains6[5])
        )
        con.commit()
    finally:
        con.close()

# ----------------- Dated BLOB builders -----------------
# These return newest-first lists of human-readable lines WITH the draw date.
# Phase-1 inputs still expect undated lines, so use these for verification/CSV.

def mm_blob(limit: int = 20) -> str:
    con = _conn()
    try:
        rows = con.execute(
            "SELECT draw_date,n1,n2,n3,n4,n5,bonus "
            "FROM mm_draws ORDER BY "
            "COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        lines: List[str] = []
        for r in rows:
            date = (r["draw_date"] or "").strip() or "????-??-??"
            mains = f"{r['n1']:02d}-{r['n2']:02d}-{r['n3']:02d}-{r['n4']:02d}-{r['n5']:02d}"
            lines.append(f"{date} {mains} {int(r['bonus']):02d}")
        return "\n".join(lines)
    finally:
        con.close()

def pb_blob(limit: int = 20) -> str:
    con = _conn()
    try:
        rows = con.execute(
            "SELECT draw_date,n1,n2,n3,n4,n5,bonus "
            "FROM pb_draws ORDER BY "
            "COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        lines: List[str] = []
        for r in rows:
            date = (r["draw_date"] or "").strip() or "????-??-??"
            mains = f"{r['n1']:02d}-{r['n2']:02d}-{r['n3']:02d}-{r['n4']:02d}-{r['n5']:02d}"
            lines.append(f"{date} {mains} {int(r['bonus']):02d}")
        return "\n".join(lines)
    finally:
        con.close()

def il_blob(limit: int = 20, tier: str = "JP") -> str:
    """
    Return IL Lotto lines WITH dates. By default only Jackpot ('JP') lines,
    newest first, like: 'YYYY-MM-DD 05-06-14-15-48-49'
    """
    con = _conn()
    try:
        rows = con.execute(
            "SELECT draw_date,n1,n2,n3,n4,n5,n6 FROM il_draws "
            "WHERE tier=? ORDER BY COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
            (tier, limit)
        ).fetchall()
        lines: List[str] = []
        for r in rows:
            date = (r["draw_date"] or "").strip() or "????-??-??"
            mains = f"{r['n1']:02d}-{r['n2']:02d}-{r['n3']:02d}-{r['n4']:02d}-{r['n5']:02d}-{r['n6']:02d}"
            lines.append(f"{date} {mains}")
        return "\n".join(lines)
    finally:
        con.close()

# ----------------- CSV export (unchanged format with dates) -----------------

def export_csv(game: str, limit: int = 1000) -> str:
    game = game.upper()
    con = _conn()
    try:
        if game == "MM":
            rows = con.execute(
                "SELECT draw_date,n1,n2,n3,n4,n5,bonus,created_at FROM mm_draws "
                "ORDER BY COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            out = ["draw_date,n1,n2,n3,n4,n5,bonus,created_at"]
            for r in rows:
                out.append(f"{r['draw_date'] or ''},{r['n1']},{r['n2']},{r['n3']},{r['n4']},{r['n5']},{r['bonus']},{r['created_at']}")
            return "\n".join(out)

        if game == "PB":
            rows = con.execute(
                "SELECT draw_date,n1,n2,n3,n4,n5,bonus,created_at FROM pb_draws "
                "ORDER BY COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            out = ["draw_date,n1,n2,n3,n4,n5,bonus,created_at"]
            for r in rows:
                out.append(f"{r['draw_date'] or ''},{r['n1']},{r['n2']},{r['n3']},{r['n4']},{r['n5']},{r['bonus']},{r['created_at']}")
            return "\n".join(out)

        if game == "IL":
            rows = con.execute(
                "SELECT draw_date,tier,n1,n2,n3,n4,n5,n6,created_at FROM il_draws "
                "ORDER BY COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            out = ["draw_date,tier,n1,n2,n3,n4,n5,n6,created_at"]
            for r in rows:
                out.append(f"{r['draw_date'] or ''},{r['tier']},{r['n1']},{r['n2']},{r['n3']},{r['n4']},{r['n5']},{r['n6']},{r['created_at']}")
            return "\n".join(out)

        raise ValueError("game must be MM, PB, or IL")
    finally:
        con.close()

