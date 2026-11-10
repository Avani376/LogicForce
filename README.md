# LogicForge

**Self-verifying digital system engineering platform** — specify → design → simulate →
verify → fault-test → repair → optimize, with deterministic engines as the single source
of truth and every result traceable.

> Status: **Phases 0–10 + curriculum phases C1–C10 complete**. All ten roadmap phases are
> implemented and tested, plus the syllabus-driven curriculum track: number systems,
> Boolean algebra, K-map/Quine-McCluskey, the combinational library, sequential
> curriculum, the full 8086 instruction set (timing, addressing, multiply/divide, string
> ops), the 8259 PIC, and the engine-graded lessons/exercises layer. Nothing is claimed
> beyond what is tested — see [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) and the
> C-series checklist in [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

## What works right now

- **Deterministic logic engine** (`engines/logic`): four-valued logic `{0, 1, X, Z}`,
  seven gate types + constants + primary I/O, strict circuit validation with typed error
  codes, topological propagation with a documented deterministic order, and full trace
  events. Byte-identical results for identical inputs — enforced by test (100× replay).
- **Golden reference circuits**: half adder, full adder, 2:1 mux, 4:1 mux, 2:4 decoder —
  committed expected truth tables.
- **API service** (`apps/api`): 20 endpoints across 12 routers — circuits, sequential/FSM,
  verify, faults/repair, optimize, 8086 (assemble/run/step/PIC), explain, curriculum.
  See [`docs/API.md`](docs/API.md).
- **Sequential engine** (`engines/sequential`, v0.2.0): DFF/TFF/JK/SR flip-flops,
  registers, counters with a documented global-clock tick model; waveform trace.
- **Verification engine** (`engines/verify`, v0.3.0): exhaustive invariant checking
  (combinational + FSM firing space) with `EXHAUSTIVE`/`INCOMPLETE` scope labels and
  **replayable counterexamples** — the faulty traffic-light controller is an automated
  acceptance test.
- **Fault & repair engines** (`engines/faults`, `engines/repair`, v0.4.0): seeded
  document-transformation faults (stuck-at, gate swap, transition edits), bounded
  behavior probes, property-suite detection, and delta-guided repair candidates where
  **every candidate is re-verified against the full suite** before "repaired" is claimed.
- **Optimization engine** (`engines/optimize`, v0.5.0): behavior-preserving combinational
  rewrites (double negation, buffers, constant folding, duplicate merge, dead gates) with
  **per-transformation exhaustive equivalence evidence** — objective improves, truth
  table provably unchanged.
- **Explanation engine** (`engines/verify` explain, v0.9.0): evidence-grounded
  explanations generated from real engine output — every finding cites trace steps
  or report verdicts; deterministic, rule-based, no LLM dependency.
- **8086 educational core** (`engines/cpu8086`, v0.6.0): IR-based assembler + executor
  with exact Intel-documented flag semantics, 1MiB segmented memory with mod-2^20
  wraparound, debugger controls (step, bounded run, breakpoints, full trace),
  **deterministic interrupts** (software INT, scheduled NMI/INTR, IF masking, IRET flag
  restoration), a published timing model (C6), MUL/IMUL/DIV/IDIV (C8), and string ops
  with the DF flag and REP/REPE/REPNE prefixes (C9).
- **Co-simulation engine** (`engines/cosim`, v0.8.0): one ordered event trace shared by
  circuit and 8086 — hardware/software interaction with a documented 4-step cycle.
- **Number-systems engine** (`engines/numsys`, v0.9.0): base conversion with worked
  steps, one's/two's complement arithmetic with flags, BCD/Excess-3/Gray codes, ASCII.
- **Boolean engine** (`engines/boolean`, v0.1.0): expression parser, SOP/POS canonical
  forms, 15 verified theorems, NAND/NOR transforms, K-map and Quine-McCluskey
  minimization with don't-cares (cross-checked against each other by tests).
- **8259 PIC engine** (`engines/pic8259`, v0.1.0): IRR/ISR/IMR, ICW/OCW programming
  state machine, fully-nested priority with rotation, the EOI family, and scheduled
  vector-delivery traces that map 1:1 onto the CPU's interrupt schedule.
- **Curriculum engine** (`engines/curriculum`, v0.1.0): 6 unit-tagged lessons and 7
  exercises graded **by the engines themselves** — truth-table equivalence, QM
  minimality, bounded CPU runs — with evidence lines and scope labels, never
  string-matching and never an LLM.
- **Grounded AI assistant** (`/api/assistant/ask` + Sparky): ask questions in
  natural language and get answers **routed to real sources** — the explain
  engine (cites actual trace steps), the lesson catalog, or authored product
  guidance. Deterministic, rule-based, and honest by construction: without
  engine evidence it refuses to invent an explanation (contract:
  [`docs/semantics/assistant.md`](docs/semantics/assistant.md)).
- **Sparky, the mascot** (`apps/web`): a cute chip-bot who blinks, bobs,
  celebrates your passes, consoles your failures, guides you to the next step
  with clickable CTAs, and doubles as the Ask-chat UI.
- **Animated visualizer** (`apps/web`, Visuals tab): the 9-stage workflow with a
  traveling pulse, event-activity bars, a truth-table heatmap with staggered
  reveal, and draw-on waveforms — all rendered from **real session data only**,
  with honest empty states.
- **Operator workspace** (`apps/web`): accessible gate editor — palette, drag placement,
  click-to-wire, input toggles, live simulation, truth-table view, validation panel,
  sequential waveform viewer, undo/redo, save/load.

## Deployment (Docker)

```bash
docker compose up --build
# API: http://localhost:8000  |  Web: http://localhost:80
```

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
mypy engines/*/*/ apps/api/logicforge_api   # strict types (CI lists every package)
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
| [`docs/API.md`](docs/API.md) | all implemented endpoints + planned ones |
| [`docs/COURSE_REPORT.md`](docs/COURSE_REPORT.md) | course deliverable — syllabus mapping |
| [`docs/syllabus-map.md`](docs/syllabus-map.md) | per-item traceability matrix |
| [`docs/TESTING.md`](docs/TESTING.md) | test strategy |
| [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) | video walkthrough script (record the demo from this) |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | what the platform cannot do yet |

## Engineering rules (enforced)

1. Determinism is the source of truth — engines compute, UI explains, AI (later) advises.
2. Same circuit + inputs + engine version ⇒ byte-identical output.
3. Every claim carries a scope label: `EXHAUSTIVE(k)` / `BOUNDED(k)` / `SAMPLED(n)` / `INCOMPLETE`.
4. Failures are typed errors, never silent defaults.
5. Tests run before any phase is called done.
