"""FastAPI application factory (module-level singleton app).

Run locally: ``uvicorn logicforge_api.main:app --reload --port 8000``
The service is stateless (ENGINEERING_DECISIONS D5): every endpoint is a pure
function of its request body.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from logic_engine import ENGINE_VERSION
from sequential_engine import SEQUENTIAL_ENGINE_VERSION

from logicforge_api import API_VERSION
from logicforge_api.routers import circuits, cpu8086, faults, optimize, sequential, verify

app = FastAPI(
    title="LogicForge API",
    description=(
        "Deterministic digital-system engineering engines. "
        "All results are computed by the engines; scope labels state exactly "
        "what was explored."
    ),
    version=ENGINE_VERSION,
)

root = APIRouter(prefix="/api", tags=["meta"])


@root.get("/health")
def health() -> dict[str, str]:
    """Liveness plus versions, for reproducibility bookkeeping."""
    return {
        "status": "ok",
        "api_version": API_VERSION,
        "engine_version": ENGINE_VERSION,
        "sequential_engine_version": SEQUENTIAL_ENGINE_VERSION,
    }


app.include_router(root)
app.include_router(circuits.router)
app.include_router(sequential.router)
app.include_router(verify.router)
app.include_router(faults.router)
app.include_router(optimize.router)
app.include_router(cpu8086.router)
