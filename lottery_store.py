# lottery_store.py — SQLite-backed history store with dated BLOB output + CSV import
from __future__ import annotations
import os
import sqlite3
import csv
from io import StringIO
from typing import List, Dict, Any, Optional

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

        # Uniqueness helpers (avoid duplicates when importing)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mm_uniq ON mm_draws(draw_date,n1,n2,n3,n4,n5,bonus)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pb_uniq ON pb_draws(draw_date,n1,n2,n3,n4,n5,bonus)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_il_uniq ON il_draws(draw_date,tier,n1,n2,n3,n4,n5,n6)")

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

def mm_blob(limit: int = 20) -> str:
    con = _conn()
    try:
        rows = con.execute(
            "SELECT draw_date,n1,n2,n3,n4,n5,bonus "
            "FROM mm_draws ORDER BY COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
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
            "FROM pb_draws ORDER BY COALESCE(draw_date,'9999-99-99') DESC, id DESC LIMIT ?",
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

# ----------------- CSV export -----------------

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

# ----------------- CSV import (bulk) -----------------
"""
Flexible CSV schema supported:

A) One combined file with a 'game' column:
   game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
   MM,2024-08-23,,10,14,34,40,43,,5
   PB,2024-08-24,,14,15,32,42,49,,1
   IL,2024-08-24,JP,01,04,05,10,18,49,
   IL,2024-08-24,M1,06,08,10,18,26,27,
   IL,2024-08-24,M2,02,18,21,27,43,50,

B) Per-game files (no 'game' column):
   # Mega Millions (exact headers, bonus required):
   draw_date,n1,n2,n3,n4,n5,bonus

   # Powerball (exact headers, bonus required):
   draw_date,n1,n2,n3,n4,n5,bonus

   # Illinois Lotto (tier required, bonus ignored):
   draw_date,tier,n1,n2,n3,n4,n5,n6
"""
def import_csv(csv_text: str) -> Dict[str, Any]:
    reader = csv.DictReader(StringIO(csv_text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]

    has_game = "game" in headers
    has_tier = "tier" in headers
    required_any = {"draw_date","n1","n2","n3","n4","n5"}
    if not required_any.issubset(headers):
        raise ValueError(f"CSV must include at least: {sorted(required_any)}")

    report = {"inserted": {"MM":0,"PB":0,"IL_JP":0,"IL_M1":0,"IL_M2":0}, "skipped": 0, "errors": 0, "rows": 0}
    con = _conn()
    try:
        cur = con.cursor()
        for row in reader:
            report["rows"] += 1
            try:
                game = (row.get("game") or "").strip().upper() if has_game else ""
                draw_date = (row.get("draw_date") or "").strip() or None
                tier = (row.get("tier") or "").strip().upper() if has_tier else ""

                n1 = int(row.get("n1") or 0); n2 = int(row.get("n2") or 0)
                n3 = int(row.get("n3") or 0); n4 = int(row.get("n4") or 0)
                n5 = int(row.get("n5") or 0)
                n6_val = row.get("n6"); n6 = int(n6_val) if n6_val not in (None, "") else None
                bonus_val = row.get("bonus"); bonus = int(bonus_val) if bonus_val not in (None, "") else None

                if has_game:
                    if game == "MM":
                        if bonus is None: raise ValueError("MM row missing bonus")
                        cur.execute("SELECT 1 FROM mm_draws WHERE draw_date=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND bonus=? LIMIT 1",
                                    (draw_date,n1,n2,n3,n4,n5,bonus))
                        if cur.fetchone(): 
                            report["skipped"] += 1; 
                        else:
                            cur.execute("INSERT INTO mm_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
                                        (draw_date,n1,n2,n3,n4,n5,bonus))
                            report["inserted"]["MM"] += 1

                    elif game == "PB":
                        if bonus is None: raise ValueError("PB row missing bonus")
                        cur.execute("SELECT 1 FROM pb_draws WHERE draw_date=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND bonus=? LIMIT 1",
                                    (draw_date,n1,n2,n3,n4,n5,bonus))
                        if cur.fetchone():
                            report["skipped"] += 1
                        else:
                            cur.execute("INSERT INTO pb_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
                                        (draw_date,n1,n2,n3,n4,n5,bonus))
                            report["inserted"]["PB"] += 1

                    elif game == "IL":
                        if not tier or tier not in ("JP","M1","M2"):
                            raise ValueError("IL row requires tier JP/M1/M2")
                        if n6 is None: raise ValueError("IL row missing n6")
                        cur.execute("SELECT 1 FROM il_draws WHERE draw_date=? AND tier=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND n6=? LIMIT 1",
                                    (draw_date,tier,n1,n2,n3,n4,n5,n6))
                        if cur.fetchone():
                            report["skipped"] += 1
                        else:
                            cur.execute("INSERT INTO il_draws(draw_date,tier,n1,n2,n3,n4,n5,n6) VALUES(?,?,?,?,?,?,?,?)",
                                        (draw_date,tier,n1,n2,n3,n4,n5,n6))
                            report["inserted"][f"IL_{tier}"] += 1
                    else:
                        raise ValueError("Unknown game (expect MM, PB, or IL)")

                else:
                    # Per-game file (no 'game' column). Decide by presence of 'tier' and 'n6'/'bonus'
                    if "bonus" in headers and (n6 is None):
                        # Treat as MM or PB; let caller decide outside? We try both; no harm in duplicates due to unique-check
                        if bonus is None: raise ValueError("MM/PB row missing bonus")
                        # Try MM insert
                        cur.execute("SELECT 1 FROM mm_draws WHERE draw_date=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND bonus=? LIMIT 1",
                                    (draw_date,n1,n2,n3,n4,n5,bonus))
                        if not cur.fetchone():
                            cur.execute("INSERT INTO mm_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
                                        (draw_date,n1,n2,n3,n4,n5,bonus))
                            report["inserted"]["MM"] += 1
                        else:
                            report["skipped"] += 1

                        # Try PB insert (if truly PB this will add; otherwise it will skip since duplicate with same combo is unlikely)
                        cur.execute("SELECT 1 FROM pb_draws WHERE draw_date=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND bonus=? LIMIT 1",
                                    (draw_date,n1,n2,n3,n4,n5,bonus))
                        if not cur.fetchone():
                            cur.execute("INSERT INTO pb_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
                                        (draw_date,n1,n2,n3,n4,n5,bonus))
                            report["inserted"]["PB"] += 1
                        else:
                            report["skipped"] += 1

                    elif "tier" in headers and n6 is not None:
                        if not tier or tier not in ("JP","M1","M2"):
                            raise ValueError("IL row requires tier JP/M1/M2")
                        cur.execute("SELECT 1 FROM il_draws WHERE draw_date=? AND tier=? AND n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND n6=? LIMIT 1",
                                    (draw_date,tier,n1,n2,n3,n4,n5,n6))
                        if cur.fetchone():
                            report["skipped"] += 1
                        else:
                            cur.execute("INSERT INTO il_draws(draw_date,tier,n1,n2,n3,n4,n5,n6) VALUES(?,?,?,?,?,?,?,?)",
                                        (draw_date,tier,n1,n2,n3,n4,n5,n6))
                            report["inserted"][f"IL_{tier}"] += 1
                    else:
                        raise ValueError("Cannot infer game for per-game CSV (check headers)")

            except Exception:
                report["errors"] += 1
        con.commit()
    finally:
        con.close()
    return report
