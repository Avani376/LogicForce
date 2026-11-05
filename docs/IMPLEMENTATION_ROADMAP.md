# Implementation Roadmap — LogicForge

Phases and exit criteria follow the master engineering prompt. Status is kept honest:
a phase is *Done* only when its exit criterion has actually passed with executed tests.

| Phase | Deliverable | Exit criterion | Status |
|---|---|---|---|
| 0 | Architecture, semantics docs, repo scaffold, CI | Scope and engine rules documented; toolchain verified; CI config committed | **Done (this session)** |
| 1 | Deterministic combinational engine + truth tables + FastAPI service + gate editor MVP | Reference circuits (half adder, full adder, 2:1 mux, 4:1 mux, 2:4 decoder) pass golden tests; engine + API tests green; web production build passes | **In progress (this session)** |
| 2 | Sequential engine: flip-flops, registers, counters, FSM, waveforms | Clock/state semantics documented + tested; waveform trace from engine | Planned |
| 3 | Verification engine v1 + counterexamples | Faulty traffic-light FSM yields a reproducible counterexample | Planned |
| 4 | Fault injection + repair search + re-verification | Seeded fault detected; repair candidate re-verifies against original suite | Planned |
| 5 | Optimization with equivalence checking | Metric improves while behavior stays equivalent | Planned |
| 6 | 8086 core + debugger | Documented instruction subset passes differential tests | Planned |
| 7 | Interrupts: IVT/ISR, INTR/NMI, 8259-style PIC | Reproducible interrupt traces | Planned |
| 8 | Hardware–software co-simulation | Circuit and CPU events share one ordered trace | Planned |
| 9 | Evidence-grounded AI assistance | Explanations cite real trace events; unverified suggestions labeled | Planned |
| 10 | Hardening, deployment, demo | End-to-end signature demo passes; release checklist | Planned |

## Signature demo (acceptance target)

“North and East never green together” → FSM → simulate → verify `PASS (EXHAUSTIVE, N states)`
→ inject fault → `FAIL` + counterexample → repair → re-verify `PASS` → compare reports.
Automated as an end-to-end test when Phase 3/4 land.

## Session plan (this build)

1. Phase 0 — audit, scaffold, semantics, docs, CI, tooling. **Done.**
2. Phase 1 engine — `logic_engine` + unit/golden/property/determinism tests. 
3. Phase 1 API — FastAPI validate/simulate/truth-table + integration tests.
4. Phase 1c web — accessible gate editor MVP wired to schema v1; `npm run build` verified.
5. Each milestone committed separately with a conventional commit message.
