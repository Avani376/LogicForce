# LogicForge

**Self-verifying digital system engineering platform** — specify → design → simulate →
verify → fault-test → repair → optimize, with deterministic engines as the single source
of truth and every result traceable.

> Status: **Phase 0–1 build**. The deterministic combinational logic engine, its FastAPI
> service, and the gate editor MVP are implemented and tested. Sequential logic,
> verification, faults/repair, 8086, co-simulation, and AI assistance follow the roadmap in
> [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md). Nothing is claimed
> beyond what is tested — see [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## What works right now

- **Deterministic logic engine** (`engines/logic`): four-valued logic `{0, 1, X, Z}`,
  seven gate types + constants + primary I/O, strict circuit validation with typed error
  codes, topological propagation with a documented deterministic order, and full trace
  events. Byte-identical results for identical inputs — enforced by test (100× replay).
- **Golden reference circuits**: half adder, full adder, 2:1 mux, 4:1 mux, 2:4 decoder —
  committed expected truth tables.
- **API service** (`apps/api`): `POST /api/circuits/validate`, `/simulate`,
  `/truth-table` (exhaustive ≤ 12 inputs), `GET /api/health`.
- **Sequential engine** (`engines/sequential`, v0.2.0): DFF/TFF/JK/SR flip-flops,
  registers, counters with a documented global-clock tick model; waveform trace.
- **Verification engine** (`engines/verify`, v0.3.0): exhaustive invariant checking
  (combinational + FSM firing space) with `EXHAUSTIVE`/`INCOMPLETE` scope labels and
  **replayable counterexamples** — the faulty traffic-light controller is an automated
  acceptance test.
- **Operator workspace** (`apps/web`): accessible gate editor — palette, drag placement,
  click-to-wire, input toggles, live simulation, truth-table view, validation panel,
  sequential waveform viewer, undo/redo, save/load.

## Quickstart

```bash
# Backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt && pip install -e .
uvicorn logicforge_api.main:app --reload --port 8000

# Frontend (second terminal)
cd apps/web && npm install && npm run dev
```

## Testing

```bash
pytest              # unit + golden + property + integration, with coverage gate ≥ 90%
ruff check .        # lint
mypy engines/logic/logic_engine apps/api/logicforge_api   # strict types
```

## Documentation

| Doc | Content |
|---|---|
| [`docs/PROJECT_AUDIT.md`](docs/PROJECT_AUDIT.md) | repository audit |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | architecture and principles |
| [`docs/semantics/`](docs/semantics/) | **normative engine contracts** (written before code) |
| [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md) | phases + honest status |
| [`docs/ENGINEERING_DECISIONS.md`](docs/ENGINEERING_DECISIONS.md) | decision log |
| [`docs/VERIFICATION_MODEL.md`](docs/VERIFICATION_MODEL.md) | scope labels, verdict rules |
| [`docs/API.md`](docs/API.md) | endpoints (implemented + planned) |
| [`docs/TESTING.md`](docs/TESTING.md) | test strategy |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | what the platform cannot do yet |

## Engineering rules (enforced)

1. Determinism is the source of truth — engines compute, UI explains, AI (later) advises.
2. Same circuit + inputs + engine version ⇒ byte-identical output.
3. Every claim carries a scope label: `EXHAUSTIVE(k)` / `BOUNDED(k)` / `SAMPLED(n)` / `INCOMPLETE`.
4. Failures are typed errors, never silent defaults.
5. Tests run before any phase is called done.
