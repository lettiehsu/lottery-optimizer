# Lottery Optimizer (MM / PB / IL)

A Flask web app that:
- **Phase 1** (Evaluation): uses the last 20 jackpots + “Lottery Defeated” feeds to generate 50-row batches per game and prints exact-hit stats vs NJ.
- **Phase 2** (Prediction): promotes the newest jackpot into history, runs 100× regenerated 50-row batches (no printing of the 5000 rows), aggregates hit stats and outputs **buy lists** (MM/PB:10, IL:15).
- **Phase 3** (Confirmation): checks those buy lists against the next announced jackpot.

> Endpoints exposed by `app.py`:
> - `GET /` — simple UI
> - `GET /health` — health check
> - `GET /recent` — list recent saved state files
> - `POST /run_json` — Phase 1 & Phase 2 JSON API
> - `POST /confirm_json` — Phase 3 JSON API

## Local dev

1. Python 3.11 recommended.

```bash
python -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # set SECRET_KEY
export FLASK_ENV=development   # or use .env
python app.py                  # or: flask --app app run --port 5000
