# Architecture — LogicForge

Status: Phase 0 (v0.1). Describes the implemented structure plus the committed target shape.

## Principles

1. **Determinism is the source of truth.** Engines compute all results. The UI and any
   future AI layer may explain results, never produce them.
2. **Engines are pure.** No I/O, no clocks, no randomness inside `engines/*`. Side effects
   (HTTP, persistence) live only at the API boundary.
3. **Semantics-first.** `docs/semantics/` is the contract; code and tests implement it.
4. **Typed boundaries.** Python: mypy `--strict` on engines + API. TypeScript: `strict` on
   the web app.
5. **Explicit failures.** Typed error codes surfaced in reports and HTTP 400s — never
   silent defaults.

## Layout (implemented)

```
D:\Logic_Force\
├── apps/
│   ├── api/                  # FastAPI service (thin HTTP boundary over engines)
│   │   └── logicforge_api/
│   │       ├── main.py       # app factory, versioned responses
│   │       ├── schemas.py    # pydantic request/response models
│   │       └── routers/
│   │           └── circuits.py
│   └── web/                  # React + TypeScript editor workspace (Phase 1c)
├── engines/
│   └── logic/logic_engine/   # pure deterministic combinational engine (no web deps)
│       ├── values.py         # four-valued logic + gate truth tables
│       ├── components.py     # component/pin model
│       ├── graph.py          # circuit graph, JSON schema v1 parse/serialize
│       ├── validation.py     # complete validation report
│       ├── simulator.py      # topological propagation + trace events
│       ├── truth_table.py    # bounded exhaustive enumeration
│       ├── hashing.py        # canonical JSON + SHA-256 input hash
│       └── version.py        # ENGINE_VERSION
├── tests/
│   ├── unit/                 # truth tables, validation, ordering
│   ├── golden/               # fixtures + expected truth tables (committed)
│   ├── property/             # hypothesis: simulator vs independent naive evaluator
│   └── integration/          # FastAPI via TestClient
└── docs/
    ├── semantics/            # normative contracts (written before code)
    └── …                     # audit, architecture, roadmap, decisions, testing, API, limits
```

Both importable packages are installed editable (`pip install -e .`) with a per-package
`package-dir` mapping, so the documented layout is preserved and imports are stable
(`import logic_engine`, `import logicforge_api`).

## Data flow (Phase 1, implemented)

```
Browser UI ──JSON schema v1──▶ FastAPI /api/circuits/*
                                  │ pydantic shape check
                                  ▼
                              logic_engine.validate() ─▶ ValidationReport (errors → HTTP 400)
                              logic_engine.simulate() ─▶ SimulationResult + trace
                              logic_engine.truth_table() ─▶ TruthTableResult (EXHAUSTIVE(2^n))
```

Later phases add parallel flows (verification → Phase 3, faults → Phase 4, 8086 → Phase 6,
co-simulation scheduler → Phase 8) behind the same rule: one engine, one deterministic
trace, scope labels on every claim.

## Engine semantics

Normative contracts live in `docs/semantics/`:

- `logic-values.md` — four-valued domain {0,1,X,Z}, gate tables, N-input folding.
- `propagation.md` — acyclic validation, topological layers `(depth, id)`, trace event shape,
  byte-level determinism contract.
- `circuit-graph-schema.md` — JSON schema v1, validation codes.
- `report-and-scope-labels.md` — report schemas, EXHAUSTIVE/BOUNDED/SAMPLED/INCOMPLETE.

## Technology (as prescribed by the project documentation)

| Layer | Choice | Status |
|---|---|---|
| Engines | Python ≥3.12, pure modules | **implemented (logic)** |
| API | FastAPI + pydantic v2 | **implemented (Phase 1 subset)** |
| Web | React + TypeScript + Vite, custom SVG canvas | Phase 1c |
| Database | PostgreSQL | deferred (D5) — API is stateless compute in v1 |
| Realtime | SSE/WebSockets | deferred — sim latency budget makes sync viable for Phase 1 |
| Deployment | Docker | deferred to Phase 10 (D6) |
| CI | GitHub Actions: ruff + mypy --strict + pytest + coverage gate | **implemented** |
