# API — LogicForge

Base URL (dev): `http://127.0.0.1:8000` · All request/response bodies are JSON.
Responses that encode results carry `schema_version`, `engine_version`, `input_hash`, and a
`scope` label (see `docs/semantics/report-and-scope-labels.md`).

## Implemented (Phase 1)

### `GET /api/health`
Liveness + versions.
```json
{ "status": "ok", "api_version": "1", "engine_version": "0.1.0" }
```

### `POST /api/circuits/validate`
Body: circuit document (schema v1). Returns the full validation report (complete, not
fail-fast). HTTP 200 even when invalid — invalidity is a *result*, not a transport error.

### `POST /api/circuits/simulate`
Body: `{ "circuit": {…}, "inputs": { "a": "1", "b": 0 } }` — input values accept
`"0"|"1"|"X"|"Z"` strings or `0|1` integers (normalized to strings). Omitted inputs default
to `"X"`. Response: `SimulationResult` (outputs by OUTPUT-name, ordered trace events,
`scope: "SINGLE_VECTOR"`).

Errors: `400` with `{"errors": [ValidationIssue…]}` when the circuit is invalid;
`422` when the request body shape is wrong (pydantic).

### `POST /api/circuits/truth-table`
Body: circuit document. Response: `TruthTableResult` with `scope: "EXHAUSTIVE(2^n)"`
(n = number of primary inputs). `400 TRUTH_TABLE_LIMIT_EXCEEDED` when n > 12;
`400` validation errors otherwise.

## Error envelope (400 responses)

```json
{ "detail": { "code": "VALIDATION_FAILED", "errors": [ { "code": "DANGLING_INPUT_PIN", "message": "…", "component_id": "G1" } ], "warnings": [] } }
```

Machine-readable `code`s come from the authoritative table in
`docs/semantics/circuit-graph-schema.md`.

## Planned (not implemented — listed for contract review, from the project docs)

| Endpoint | Purpose | Phase |
|---|---|---|
| `POST /api/projects`, `GET/PUT /api/projects/{id}` | project/version persistence | with verification (D5) |
| `POST /api/verify` | property check → VerificationReport | 3 |
| `POST /api/fault-experiments` | fault injection run | 4 |
| `POST /api/repair-search` | candidate patches + re-verification | 4 |
| `POST /api/optimize` | metric comparison with equivalence check | 5 |
| `POST /api/8086/assemble`, `POST /api/8086/run` | assembler + bounded execution | 6 |
| `GET /api/runs/{id}/trace` | stored run trace | with persistence |
| `POST /api/assistant/explain` | evidence-grounded explanation | 9 |

Planned endpoints are contract placeholders only — none return fake data; they return 404
until implemented.
