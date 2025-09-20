#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, os, time, uuid
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lottery_core import (
    parse_hist_blob, parse_feed_blob, GameSpec, G_MM, G_PB, G_IL,
    phase1_evaluate, phase2_predict_and_recommend, phase3_confirm,
    pack_latest_dict, normalize_latest_payload
)

APP_TITLE = "Lottery Optimizer API (safe mode)"

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title=APP_TITLE)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": APP_TITLE})

@app.get("/health")
async def health():
    return {"ok": True, "ts": time.time()}

@app.get("/recent")
async def recent():
    files = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:20]:
        try:
            meta = json.loads(p.read_text(encoding="utf-8")).get("_meta", {})
        except Exception:
            meta = {}
        out.append({
            "file": p.name,
            "mtime": p.stat().st_mtime,
            "size": p.stat().st_size,
            "meta": meta
        })
    return {"saved": out}

def _coalesce_form_or_json(req: Request, form: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    # prefer JSON body keys; fall back to form fields
    out = {}
    out.update(form or {})
    out.update(body or {})
    return out

@app.post("/run_json")
async def run_json(request: Request):
    """
    Phase 1 (Evaluation) and Phase 2 (Prediction + Buy-list).
    Input: fields for LATEST_*, HIST_*_BLOB, FEED_* (see README).
    Returns: evaluation summary + buy lists + saved_path.
    """
    try:
        # accept either form or raw JSON
        try:
            body = await request.json()
        except Exception:
            body = {}
        form = {}
        if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded") or \
           request.headers.get("content-type", "").startswith("multipart/form-data"):
            formdata = await request.form()
            form = {k: v for k, v in formdata.items()}

        payload = _coalesce_form_or_json(request, form, body)
        # Normalize "latest" fields from strings -> tuples
        latest = normalize_latest_payload(payload)

        # Parse blobs/feeds
        hist_mm = parse_hist_blob(payload.get("HIST_MM_BLOB", ""), game=G_MM)
        hist_pb = parse_hist_blob(payload.get("HIST_PB_BLOB", ""), game=G_PB)
        hist_il = parse_hist_blob(payload.get("HIST_IL_BLOB", ""), game=G_IL)

        feed_mm = parse_feed_blob(payload.get("FEED_MM", ""), game=G_MM)
        feed_pb = parse_feed_blob(payload.get("FEED_PB", ""), game=G_PB)
        feed_il = parse_feed_blob(payload.get("FEED_IL", ""), game=G_IL)

        # Phase 1 — Evaluation vs NJ (new jackpot)
        phase1 = phase1_evaluate(
            latest_dict=latest,  # expects LATEST_MM / LATEST_PB / LATEST_IL_JP/M1/M2 (as provided)
            hist={"MM": hist_mm, "PB": hist_pb, "IL": hist_il},
            feeds={"MM": feed_mm, "PB": feed_pb, "IL": feed_il}
        )

        # Phase 2 — Prediction (move NJ to top, 20-cap hist, simulate 100x)
        phase2 = phase2_predict_and_recommend(
            latest_dict=latest,
            hist={"MM": hist_mm, "PB": hist_pb, "IL": hist_il},
            feeds={"MM": feed_mm, "PB": feed_pb, "IL": feed_il},
            runs=100, batch_rows=50
        )

        # Save a confirmable artifact for Phase 3
        artifact = {
            "_meta": {
                "id": str(uuid.uuid4()),
                "ts": time.time(),
                "note": "Phase 1+2 result. Use /confirm_json with NWJ_* to verify buy lists later."
            },
            "phase1": phase1,
            "phase2": {
                "stats": phase2["stats"],
                "buy_lists": phase2["buy_lists"],
                "used_history_capped": phase2["used_history_capped"]
            }
        }
        fname = f"lotto_{int(time.time())}_{artifact['_meta']['id'][:8]}.json"
        fpath = DATA_DIR / fname
        fpath.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

        return JSONResponse({
            "ok": True,
            "saved_path": fpath.name,
            "phase1": phase1,
            "phase2": {
                "stats": phase2["stats"],
                "buy_lists": phase2["buy_lists"]
            }
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": repr(e)}, status_code=500)

@app.post("/confirm_json")
async def confirm_json(
    request: Request,
    saved_path: Optional[str] = Form(default=None),
):
    """
    Phase 3 — Confirmation against NWJ.
    Provide: saved_path (from /run_json), and NWJ_* fields (latest official results).
    """
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}
        formdata = await request.form()
        form = {k: v for k, v in formdata.items()}
        payload = _coalesce_form_or_json(request, form, body)

        spath = payload.get("saved_path") or saved_path
        if not spath:
            return JSONResponse({"ok": False, "error": "missing saved_path"}, status_code=400)

        f = DATA_DIR / spath
        if not f.exists():
            return JSONResponse({"ok": False, "error": f"no such saved file: {spath}"}, status_code=404)

        saved = json.loads(f.read_text(encoding="utf-8"))

        # NWJ_* provided now
        n_latest = normalize_latest_payload(payload, prefix="NWJ_")  # accept NWJ_* keys
        result = phase3_confirm(saved, n_latest)

        return JSONResponse({"ok": True, "confirmation": result})
    except Exception as e:
        return JSONResponse({"ok": False, "error": repr(e)}, status_code=500)
