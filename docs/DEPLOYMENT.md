# Deployment — LogicForge

Status: local development is fully supported (Phase 1). Containerized deployment is
Phase 10 — this file describes only what is actually runnable today.

## Prerequisites

- Python ≥ 3.12 (developed on 3.13.5)
- Node ≥ 20 (developed on v24.15.0) — for the web workspace

## Backend (API)

```bash
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash
pip install -r requirements.txt
pip install -e .
uvicorn logicforge_api.main:app --reload --port 8000
```

Health check: `GET http://127.0.0.1:8000/api/health`

The API is stateless (D5): no database, no migrations, no secrets required in Phase 1.

## Frontend (web workspace)

```bash
cd apps/web
npm install
npm run dev        # dev server (proxies /api to :8000)
npm run build      # production build (tsc + vite) — output apps/web/dist
```

## CI (GitHub Actions)

`.github/workflows/ci.yml` runs on push/PR:
1. Python job: install → `ruff check .` → `mypy --strict` (engines + api) →
   `pytest --cov --cov-fail-under=90`.
2. Web job (added with Phase 1c): `npm ci` → `npm run build`.

## Docker (planned, Phase 10)

Multi-stage images for API and static web, behind a reverse proxy; PostgreSQL only when
persistence lands (D5). The compose file will be added when there is something real to
orchestrate (D6).
