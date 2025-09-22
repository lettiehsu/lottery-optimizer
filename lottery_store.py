# lottery_store.py
import csv, io
from datetime import datetime

# Assume you have some global or injected storage dict/list; adjust as needed.
# For example:
# DB = {"MM": [], "PB": [], "IL_JP": [], "IL_M1": [], "IL_M2": []}

def _parse_row(row):
    """Return normalized record or None; raise on unrecoverable schema issues."""
    # Expected columns from your combined master:
    # game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus
    game = row.get("game", "").strip().upper()
    date_str = row.get("draw_date", "").strip()
    tier = (row.get("tier") or "").strip().upper()  # "", "JP", "M1", "M2"

    if not game or not date_str:
        return None

    # Normalize game for IL tiers
    if game == "IL":
        if tier == "JP":
            game_key = "IL_JP"
        elif tier == "M1":
            game_key = "IL_M1"
        elif tier == "M2":
            game_key = "IL_M2"
        else:
            # rows like IL,9/20/2025,,6,14,17,18,29,30,  (ignored if not a tier row)
            return None
    else:
        game_key = game  # "MM" or "PB"

    # Date normalize MM/DD/YYYY
    try:
        draw_dt = datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        # Try other common formats if needed
        return None

    # Read numbers
    def to_int(x):
        x = (x or "").strip()
        return int(x) if x.isdigit() else None

    n1 = to_int(row.get("n1"))
    n2 = to_int(row.get("n2"))
    n3 = to_int(row.get("n3"))
    n4 = to_int(row.get("n4"))
    n5 = to_int(row.get("n5"))
    n6 = to_int(row.get("n6"))
    bonus = to_int(row.get("bonus"))

    mains = [x for x in (n1, n2, n3, n4, n5) if x is not None]
    # IL tiers have 6 mains; MM/PB have 5 mains
    if game_key.startswith("IL_"):
        # expect 6 mains
        if n6 is None or len(mains) != 5:
            # For IL we want 6 numbers; include n6
            mains = [x for x in (n1, n2, n3, n4, n5, n6) if x is not None]
        bonus_val = None
    else:
        bonus_val = bonus

    return game_key, {
        "date": draw_dt.strftime("%m/%d/%Y"),
        "mains": mains,
        "bonus": bonus_val
    }

def import_csv_io(file_like, overwrite=False):
    """
    Parse a CSV from a file-like object and upsert into the store.
    Returns {"ok": True, "added": N, "updated": M, "total": T}
    """
    reader = csv.DictReader(file_like)
    added = updated = 0

    # Provide your own storage implementation below; here we assume dict of dicts keyed by date.
    # Example in-memory structure:
    global DB
    try:
        DB
    except NameError:
        DB = {"MM": {}, "PB": {}, "IL_JP": {}, "IL_M1": {}, "IL_M2": {}}

    for row in reader:
        parsed = _parse_row(row)
        if not parsed:
            continue
        game_key, rec = parsed
        key = rec["date"]

        if key in DB[game_key]:
            if overwrite:
                DB[game_key][key] = rec
                updated += 1
        else:
            DB[game_key][key] = rec
            added += 1

    total = sum(len(DB[g]) for g in DB)
    return {"ok": True, "added": added, "updated": updated, "total": total}

# Convenience getters the UI calls:
def get_by_date(game_key: str, date_str: str):
    global DB
    return DB.get(game_key, {}).get(date_str)

def get_history(game_key: str, from_date: str, limit: int = 20):
    global DB
    # return newest-first up to limit
    rows = DB.get(game_key, {})
    # Sort by date descending
    sorted_keys = sorted(rows.keys(),
                         key=lambda d: datetime.strptime(d, "%m/%d/%Y"),
                         reverse=True)
    # Start from from_date (inclusive) then take limit
    out = []
    passed_start = False
    for k in sorted_keys:
        if not passed_start:
            passed_start = (k == from_date)
            if not passed_start:
                continue
        out.append(rows[k])
        if len(out) >= limit:
            break
    return out
