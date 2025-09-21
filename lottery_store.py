# lottery_store.py — simple SQLite store for jackpot history + BLOB views
import os, sqlite3, csv, io
from typing import List, Optional
from datetime import datetime

# Tip: mount a Render Disk at /var/data and set DB_PATH=/var/data/lottery.db
DB_PATH = os.environ.get("DB_PATH", "/var/data/lottery.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS mm_draws(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draw_date TEXT NOT NULL,
  n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL, n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
  bonus INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mm_draws_date ON mm_draws(draw_date DESC);

CREATE TABLE IF NOT EXISTS pb_draws(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draw_date TEXT NOT NULL,
  n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL, n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
  bonus INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pb_draws_date ON pb_draws(draw_date DESC);

-- Illinois: one row per set (JP / M1 / M2)
CREATE TABLE IF NOT EXISTS il_draws(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draw_date TEXT NOT NULL,
  tier TEXT NOT NULL CHECK(tier IN ('JP','M1','M2')),
  n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL, n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_il_draws_date ON il_draws(draw_date DESC, tier);
"""

def _conn():
  os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
  con = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
  con.row_factory = sqlite3.Row
  return con

def init_db():
  con = _conn()
  try:
    con.executescript(SCHEMA)
    con.commit()
  finally:
    con.close()

def _now_date():
  # ISO date (UTC)
  return datetime.utcnow().strftime("%Y-%m-%d")

def add_mm(main5: List[int], bonus: int, draw_date: Optional[str] = None):
  draw_date = draw_date or _now_date()
  n1,n2,n3,n4,n5 = [int(x) for x in main5]
  con = _conn()
  try:
    con.execute(
      "INSERT INTO mm_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
      (draw_date,n1,n2,n3,n4,n5,int(bonus))
    )
    con.commit()
  finally:
    con.close()

def add_pb(main5: List[int], bonus: int, draw_date: Optional[str] = None):
  draw_date = draw_date or _now_date()
  n1,n2,n3,n4,n5 = [int(x) for x in main5]
  con = _conn()
  try:
    con.execute(
      "INSERT INTO pb_draws(draw_date,n1,n2,n3,n4,n5,bonus) VALUES(?,?,?,?,?,?,?)",
      (draw_date,n1,n2,n3,n4,n5,int(bonus))
    )
    con.commit()
  finally:
    con.close()

def add_il(set6: List[int], tier: str, draw_date: Optional[str] = None):
  assert tier in ("JP","M1","M2")
  draw_date = draw_date or _now_date()
  n1,n2,n3,n4,n5,n6 = [int(x) for x in set6]
  con = _conn()
  try:
    con.execute(
      "INSERT INTO il_draws(draw_date,tier,n1,n2,n3,n4,n5,n6) VALUES(?,?,?,?,?,?,?,?)",
      (draw_date,tier,n1,n2,n3,n4,n5,n6)
    )
    con.commit()
  finally:
    con.close()

# ----- Blob builders (latest first, limit default 20) -----
def mm_blob(limit: int = 20) -> str:
  con = _conn()
  try:
    rows = con.execute(
      "SELECT n1,n2,n3,n4,n5,bonus FROM mm_draws ORDER BY draw_date DESC, id DESC LIMIT ?",
      (limit,)
    ).fetchall()
    lines = [f"{r['n1']:02d}-{r['n2']:02d}-{r['n3']:02d}-{r['n4']:02d}-{r['n5']:02d} {int(r['bonus']):02d}" for r in rows]
    return "\n".join(lines)
  finally:
    con.close()

def pb_blob(limit: int = 20) -> str:
  con = _conn()
  try:
    rows = con.execute(
      "SELECT n1,n2,n3,n4,n5,bonus FROM pb_draws ORDER BY draw_date DESC, id DESC LIMIT ?",
      (limit,)
    ).fetchall()
    lines = [f"{r['n1']:02d}-{r['n2']:02d}-{r['n3']:02d}-{r['n4']:02d}-{r['n5']:02d} {int(r['bonus']):02d}" for r in rows]
    return "\n".join(lines)
  finally:
    con.close()

def il_blob(limit: int = 20) -> str:
  # We use the latest 20 JP rows to build HIST_IL_BLOB
  con = _conn()
  try:
    rows = con.execute(
      "SELECT n1,n2,n3,n4,n5,n6 FROM il_draws WHERE tier='JP' ORDER BY draw_date DESC, id DESC LIMIT ?",
      (limit,)
    ).fetchall()
    lines = [f"{r['n1']:02d}-{r['n2']:02d}-{r['n3']:02d}-{r['n4']:02d}-{r['n5']:02d}-{r['n6']:02d}" for r in rows]
    return "\n".join(lines)
  finally:
    con.close()

# ----- CSV exports -----
def export_csv(game: str, limit: int = 1000) -> str:
  con = _conn()
  try:
    buf = io.StringIO()
    w = csv.writer(buf)
    if game == "MM":
      w.writerow(["draw_date","n1","n2","n3","n4","n5","mb"])
      for r in con.execute(
        "SELECT draw_date,n1,n2,n3,n4,n5,bonus FROM mm_draws ORDER BY draw_date DESC, id DESC LIMIT ?",
        (limit,)
      ):
        w.writerow([r["draw_date"], r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["bonus"]])
    elif game == "PB":
      w.writerow(["draw_date","n1","n2","n3","n4","n5","pb"])
      for r in con.execute(
        "SELECT draw_date,n1,n2,n3,n4,n5,bonus FROM pb_draws ORDER BY draw_date DESC, id DESC LIMIT ?",
        (limit,)
      ):
        w.writerow([r["draw_date"], r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["bonus"]])
    elif game == "IL":
      w.writerow(["draw_date","tier","n1","n2","n3","n4","n5","n6"])
      for r in con.execute(
        "SELECT draw_date,tier,n1,n2,n3,n4,n5,n6 FROM il_draws ORDER BY draw_date DESC, id DESC LIMIT ?",
        (limit,)
      ):
        w.writerow([r["draw_date"], r["tier"], r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]])
    else:
      raise ValueError("Unknown game")
    return buf.getvalue()
  finally:
    con.close()
