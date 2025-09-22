import csv
from datetime import datetime

# In-memory database (swap for real persistence later if you want)
try:
    DB
except NameError:
    DB = {"MM": {}, "PB": {}, "IL_JP": {}, "IL_M1": {}, "IL_M2": {}}
# DB[bucket][date_key] = {"date": "MM/DD/YYYY", "mains": [..], "bonus": int|None}

def _date_key_mmddyyyy(d: datetime) -> str:
    return d.strftime("%m/%d/%Y")

def _parse_row(row: dict):
    """
    Normalize one CSV row to (bucket, record) or None.
    Input headers (case-insensitive): game, draw_date, tier, n1..n6, bonus
    """
    # Normalize keys to lower
    lr = {k.lower(): v for k, v in row.items()}

    game = (lr.get("game") or "").strip().upper()
    date_str = (lr.get("draw_date") or "").strip()
    tier = (lr.get("tier") or "").strip().upper()

    if not game or not date_str:
        return None

    # Parse date MM/DD/YYYY
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
    except ValueError:
        return None
    dkey = _date_key_mmddyyyy(dt)

    # number fields
    def to_i(x):
        x = (x or "").strip()
        # allow "01" etc
        return int(x) if x and x.replace("-", "").isdigit() else None

    n1 = to_i(lr.get("n1"))
    n2 = to_i(lr.get("n2"))
    n3 = to_i(lr.get("n3"))
    n4 = to_i(lr.get("n4"))
    n5 = to_i(lr.get("n5"))
    n6 = to_i(lr.get("n6"))
    bonus = to_i(lr.get("bonus"))

    if game == "IL":
        # Only keep tiered IL rows (JP/M1/M2)
        if tier not in ("JP", "M1", "M2"):
            return None
        bucket = f"IL_{tier}"
        mains = [x for x in (n1, n2, n3, n4, n5, n6) if x is not None]
        # IL requires 6 mains
        if len(mains) != 6:
            return None
        rec = {"date": dkey, "mains": mains, "bonus": None}
        return bucket, rec

    if game in ("MM", "PB"):
        mains = [x for x in (n1, n2, n3, n4, n5) if x is not None]
        if len(mains) != 5:
            return None
        # bonus allowed to be None
        rec = {"date": dkey, "mains": mains, "bonus": bonus}
        return game, rec

    return None

def import_csv_io(file_like, overwrite: bool = False):
    """
    Parse a combined master CSV from a file-like object and upsert into DB.
    Returns {"ok": True, "added": N, "updated": M, "total": T}
    """
    reader = csv.DictReader(file_like)
    added = updated = 0
    for row in reader:
        parsed = _parse_row(row)
        if not parsed:
            continue
        bucket, rec = parsed
        key = rec["date"]
        exists = key in DB[bucket]
        if exists:
            if overwrite:
                DB[bucket][key] = rec
                updated += 1
        else:
            DB[bucket][key] = rec
            added += 1

    total = sum(len(DB[k]) for k in DB)
    return {"ok": True, "added": added, "updated": updated, "total": total}

def import_csv(text: str, overwrite: bool = False):
    """
    Optional convenience: accept raw CSV text and route to import_csv_io.
    """
    import io
    return import_csv_io(io.StringIO(text), overwrite=overwrite)

def get_by_date(game_key: str, date_str: str):
    """
    Return one row as {date, mains, bonus} or None.
    game_key in {"MM","PB","IL_JP","IL_M1","IL_M2"}.
    date_str must be MM/DD/YYYY.
    """
    return DB.get(game_key, {}).get(date_str)

def get_history(game_key: str, start_date: str, limit: int = 20):
    """
    Return newest→older rows starting at start_date (inclusive), up to limit,
    and a HIST_* style text blob for the UI.
    For MM/PB: "01-02-03-04-05 09"
    For IL_* : "01-02-03-04-05-06"
    """
    # Validate/normalize input date
    try:
        _ = datetime.strptime(start_date, "%m/%d/%Y")
    except ValueError:
        return {"rows": [], "blob": ""}

    rows = DB.get(game_key, {})
    # Sort by date descending
    keys = sorted(rows.keys(), key=lambda s: datetime.strptime(s, "%m/%d/%Y"), reverse=True)

    out = []
    started = False
    for k in keys:
        if not started:
            started = (k == start_date)
            if not started:
                continue
        rec = rows[k]
        mains = rec["mains"]
        if game_key in ("MM", "PB"):
            bonus = rec.get("bonus")
            if bonus is not None:
                line = f"{'-'.join(f'{n:02d}' for n in mains)} {bonus:02d}"
            else:
                # Shouldn't happen, but format without bonus if missing
                line = "-".join(f"{n:02d}" for n in mains)
        else:
            line = "-".join(f"{n:02d}" for n in mains)
        out.append(line)
        if len(out) >= limit:
            break

    return {"rows": out, "blob": "\n".join(out)}
