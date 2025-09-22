from __future__ import annotations
import json, os, time

def handle_run(payload: dict):
    """
    Safe stub that just writes Phase 1 payload to /tmp and returns the saved path.
    Replace with your full Phase-1 logic later.
    """
    phase = payload.get("phase", "phase1")
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    path = f"/tmp/lotto_{phase}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return {"ok": True, "saved_path": path}
