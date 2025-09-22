# -*- coding: utf-8 -*-
"""
Simple JSON storage for Phase 2 buy lists and a 'recent' listing.
"""

import os
import json
from typing import Dict, List

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
os.makedirs(DATA_DIR, exist_ok=True)

def save_buy_lists(buy_lists: Dict, suffix: str) -> str:
    path = os.path.join(DATA_DIR, f"buy_lists_{suffix}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(buy_lists, f, ensure_ascii=False, indent=2)
    return path

def load_buy_lists(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def list_recent_files(limit: int = 20) -> List[str]:
    files = [f for f in os.listdir(DATA_DIR) if f.startswith("buy_lists_") and f.endswith(".json")]
    files.sort(reverse=True)
    return [os.path.join(DATA_DIR, f) for f in files[:limit]]
