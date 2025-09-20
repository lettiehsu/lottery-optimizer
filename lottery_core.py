# lottery_core.py

# paste your full optimizer helpers here (parsers, generators, scoring, etc.)
# — the same code you used locally, but without the "__main__" part.

def run_phase_1_and_2(cfg: dict) -> dict:
    """
    Expect keys:
      cfg["LATEST_MM"] = ([m1..m5], bonus)
      cfg["LATEST_PB"] = ([m1..m5], bonus)
      cfg["LATEST_IL_JP"], cfg["LATEST_IL_M1"], cfg["LATEST_IL_M2"] = [6nums]
      cfg["HIST_MM"], cfg["HIST_PB"] = list[([mains], bonus)]
      cfg["HIST_IL"] = list[[6nums]]
      cfg["FEED_MM"], cfg["FEED_PB"], cfg["FEED_IL"] = dicts from text feeds
      cfg["runs"] = int, cfg["quiet"] = bool, cfg["data_dir"] = str

    Return a dict like:
      {
        "phase1": {
          "mm": {"batch": [...50 tickets...], "hits_lines": [...strings...]},
          "pb": {"batch": [...], "hits_lines": [...]},
          "il": {"batch": [...], "hits_lines": [...]},
        },
        "phase2": {
          "mm": {"totals": {...}, "top_positions": [...]},
          "pb": {"totals": {...}, "top_positions": [...]},
          "il": {"totals": {...}, "top_positions": [...]},
        },
        "buy_lists": {"mm": [...10...], "pb": [...10...], "il": [...15...]},
        "saved_path": "/tmp/buylists/buy_session_YYYYMMDD_HHMMSS.json"
      }
    """
    # >>> Here call the exact functions from your script that:
    # - build batches for phase 1
    # - print/collect the “hits_lines”
    # - run phase 2 sims and collect totals/top_positions
    # - select buy lists and save buylists JSON under cfg["data_dir"]/buylists
    #
    # Important: return plain Python types (lists/ints/strings), not custom classes.
    #
    # Finally: return the assembled dictionary.
    pass


def confirm_phase_3(saved_file: str, nwj: dict, data_dir: str) -> dict:
    """
    `saved_file` is the filename chosen from the dropdown.
    `nwj` keys may include: NWJ_MM, NWJ_PB, NWJ_IL_JP, NWJ_IL_M1, NWJ_IL_M2.
    Return a dict like:
      {
        "headings": {... phase1 & 2 headings from that saved run ...},  # optional
        "confirm": {
          "mm": {"totals": {...}, "lines": [...]},   # only if NWJ_MM provided
          "pb": {"totals": {...}, "lines": [...]},   # only if NWJ_PB provided
          "il": {"totals": {...}, "lines": [...]},
        }
      }
    """
    # 1) Load buy list JSON from f"{data_dir}/buylists/{saved_file}"
    # 2) Evaluate those exact tickets against NWJ_* targets using your scoring funcs
    # 3) Build “lines” with per-ticket details (≥2-ball for IL, ≥3 or 2+bonus for MM/PB)
    # 4) Return the dict above
    pass
