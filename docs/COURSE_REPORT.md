# LogicForge — Course Report

**Self-Verifying Digital System Engineering Platform**
Avani Jannawar · VIT SEM 3 · FOID CP · November 2026

## 1. Problem Statement

Students learning digital electronics and microprocessors use fragmented tools: paper
exercises, circuit simulators that don't verify, assembly debuggers that don't connect
to hardware, and AI assistants that hallucinate results. Moving from a requirement to
a verified, tested implementation requires manual work across disconnected tools.

LogicForge unifies the workflow: **specify → design → simulate → verify → fault-test →
repair → optimize** — with deterministic engines as the single source of truth.

## 2. Architecture

8 pure, deterministic engines behind a FastAPI service, with a React+TypeScript
workspace. Every result carries a scope label (`EXHAUSTIVE(k)` / `BOUNDED(k)` /
`INCOMPLETE`). Same inputs + same engine version = byte-identical output (enforced
by 100× replay tests).

| Engine | What it does |
|---|---|
| `logic_engine` | Combinational circuits: gates, truth tables, validation, propagation |
| `sequential_engine` | Clocked state: D/T/JK/SR flip-flops, registers, counters, FSMs |
| `verify_engine` | Exhaustive invariant checking with counterexamples + explanations |
| `fault_engine` | Seeded faults (stuck-at, gate swap, transition edits) |
| `repair_engine` | Delta-guided repair candidates, each re-verified against the suite |
| `optimize_engine` | Behavior-preserving rewrites with per-step equivalence evidence |
| `cpu8086` | 8086 educational core: assembler, executor, flags, interrupts |
| `cosim_engine` | Shared event scheduler: circuit ↔ CPU via I/O ports |

## 3. Key Design Decisions

1. **Determinism is the source of truth.** Engines compute; UI explains; AI advises.
   No clock, randomness, or wall-time in any engine.
2. **Scope labels on every claim.** EXHAUSTIVE means all cases were checked; BOUNDED
   means a limit was reached. The platform never overclaims.
3. **Semantics-first development.** Every engine's rules are documented in
   `docs/semantics/` before implementation; tests verify the code against those
   contracts.
4. **Faults are document transformations.** A fault rewrites the model document;
   the faulty model is then checked by the existing engines. No new evaluation
   semantics.
5. **Repairs are re-verified.** A candidate is "valid" only when the full property
   suite passes on it. The platform never claims "repaired" without evidence.

## 4. Implementation

- 8 engines (Python, typed, mypy strict)
- FastAPI service (21 endpoints)
- React + TypeScript workspace (SVG circuit editor, waveform viewer, 8086 panel)
- 659 tests (unit, golden, property-based, integration, signature acceptance)
- 91% coverage (CI gate ≥90%)
- Docker deployment (API + web with nginx reverse proxy)
- GitHub Actions CI (ruff, mypy strict, pytest+cov, web build)

## 5. Testing

| Level | Count | What it proves |
|---|---|---|
| Unit | 350+ | Gate tables, flag vectors, assembler diagnostics, validation codes |
| Golden | 30+ | 8 reference circuits/programs reproduce committed expectations |
| Property | 40+ | hypothesis: engines match independent naive evaluators |
| Integration | 40+ | HTTP endpoints with typed error mapping |
| Signature | 8 | One per major capability (verify, fault, optimize, explain, interrupts) |
| Determinism | 500+ | 100× byte-identical replay per fixture |

## 6. Results

- **Verification**: faulty traffic-light FSM produces a replayable counterexample
  (automated acceptance test)
- **Fault + repair**: seeded stuck-at fault detected by property suite; repair
  candidate re-verified to PASS (automated acceptance test)
- **Optimization**: wasteful half adder gate count reduced with truth-table
  equivalence proof (automated acceptance test)
- **Interrupts**: NMI/INTR scheduled at instruction boundaries; IF masking honest
  (parked interrupts observable); IRET restores flags (automated test)
- **Co-simulation**: circuit output read by CPU IN port; CPU OUT drives circuit
  input at the next settle (one-cycle port latency, documented)

## 7. Limitations

No persistence/auth (stateless API), no native machine-code encoding (IR-based),
no timing model (cycle-accurate abstraction only), explanation engine is rule-based
(not an LLM), combinational optimization only. See `docs/LIMITATIONS.md`.

## 8. Conclusion

LogicForge demonstrates that a self-verifying engineering platform is achievable
with deterministic engines, honest scope labels, and test-first development.
The entire workflow — from specification through fault injection, repair, and
optimization — produces evidence that can be inspected, replayed, and audited.
