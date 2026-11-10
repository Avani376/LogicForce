# LogicForge HTTP API

Base URL (dev): `http://127.0.0.1:8000` · All bodies are JSON. Responses that encode
results carry `schema_version`, `engine_version`, `input_hash`, and a `scope` label
(see `docs/semantics/report-and-scope-labels.md`). Every response is deterministic:
same request + same engine versions ⇒ byte-identical body. Interactive schema:
`GET /docs` (FastAPI/OpenAPI) on a running instance.

## Meta

### `GET /api/health`

Liveness + versions: `{"status": "ok", "engine_version": "…", "sequential_engine_version": "…"}`.

## Circuits — combinational (Phase 1, `logic_engine` v0.1.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/circuits/validate` | Full validation report (typed codes, non-fail-fast) |
| `POST /api/circuits/simulate` | Topological propagation + trace events + input hash |
| `POST /api/circuits/truth-table` | Exhaustive enumeration ≤ 12 inputs, `EXHAUSTIVE(2^n)` |

## Sequential circuits & FSM (Phase 2 + C5, `sequential_engine` v0.2.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/sequential/simulate` | Clock-edge simulation with per-cycle inputs + waveform trace |
| `POST /api/fsm/simulate` | FSM run — per-cycle outputs + final state |
| `POST /api/fsm/reachable` | Reachability set of an FSM (graph analysis) |

## Verification (Phase 3, `verify_engine` v0.3.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/verify` | Property check over truth tables / FSM runs → `VerificationReport` with scope labels and counterexamples |

## Faults & repair (Phase 4, `fault_engine`/`repair_engine` v0.4.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/faults/apply` | Transform a circuit document (stuck-at, bridge, bit-flip operators) |
| `POST /api/fault-experiments` | Behavior probe + detection report for injected faults |
| `POST /api/repair-search` | Delta-guided candidate search with re-verification gate |

## Optimization (Phase 5, `optimize_engine` v0.5.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/optimize` | Behavior-preserving rewrites with before/after metrics + equivalence check |

## 8086 (Phases 6–7, C6–C9, `cpu8086` v0.6.0 + `pic8259` v0.1.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/8086/assemble` | Source → instruction count + labels; typed `ASM_ERROR` with line/category |
| `POST /api/8086/run` | Bounded run: IVT, scheduled NMI/INTR (`schedule`), step cap, full trace (`instruction`/`interrupt`/`iret`/`pending_intr` records) |
| `POST /api/8086/step` | One instruction with register/flag/memory deltas |
| `POST /api/8086/pic` | Phase C7 — resolve a scheduled 8259 flow (`base_vector`, `events`); optionally run the derived schedule through the CPU pipeline (`program`) |

Instruction subset now covers MOV/XCHG, the ALU family, INC/DEC/NEG, MUL/IMUL/DIV/IDIV
(C8), shifts/rotates (C6), string ops with REP/REPE/REPNE and the DF flag (C9),
PUSH/POP, jumps/LOOP/CALL/RET, INT/IRET/STI/CLI, IN/OUT, HLT/NOP. Anything else is a
typed `UNSUPPORTED_INSTRUCTION`.

## Explanations (Phase 9, `verify_engine/explain` v0.9.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/explain` | Evidence-grounded explanation of the latest result — cites real trace steps; deterministic |

## Assistant (Phase AI, `assistant.py` v0.1.0)

| Endpoint | Purpose |
|---|---|
| `POST /api/assistant/ask` | Grounded Q&A router: deterministic intent routing to the explain engine, the lesson catalog, or authored guidance. The `grounding` field states exactly what produced the answer (`engine_output` / `catalog` / `guidance`); with no evidence it refuses to invent (contract: `docs/semantics/assistant.md`) |

## Curriculum (Phase C10, `curriculum_engine` v0.1.0)

| Endpoint | Purpose |
|---|---|
| `GET /api/curriculum/lessons` | Static lesson catalog (6 lessons, unit-tagged) |
| `GET /api/curriculum/exercises` | All exercises with prompts/hints — pinned answers never leave the engine |
| `GET /api/curriculum/exercises/{id}` | One exercise |
| `POST /api/curriculum/grade` | Deterministic grading via the relevant engine (`EXHAUSTIVE`/`BOUNDED` scope + evidence lines) |

Grading is never string-matching: expression answers are truth-table-checked,
minimizations are equivalence + minimality checked against Quine-McCluskey, CPU
predictions are checked by running the pinned program.

## Error envelope (4xx)

```json
{ "detail": { "code": "ASM_ERROR", "line": 3, "category": "UNKNOWN_MNEMONIC", "message": "…" } }
```

| `code` | Source |
|---|---|
| `ASM_ERROR` | 8086 assembler (line + category) |
| `UNSUPPORTED_INSTRUCTION` | outside the declared subset |
| `CPU_RUNTIME_ERROR` | execution-time failure (stack violation, divide overflow…) |
| `PIC_ERROR` | 8259 programming/operation (carries `category`) |
| `CURRICULUM_ERROR` | unknown lesson/exercise (404) or bad submission (400) |
| engine-specific | validation & engine failures per the semantics docs |

## Planned (not implemented — from the project docs)

| Endpoint | Purpose | Phase |
|---|---|---|
| `POST /api/projects`, `GET/PUT /api/projects/{id}` | project/version persistence | with persistence (D5) |
| `GET /api/runs/{id}/trace` | stored run trace | with persistence |
