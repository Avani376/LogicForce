# Release Checklist — LogicForge

Status: Phase 10 (hardening). Each item references the evidence that satisfies it.

## Verification

- [x] All supported gate truth tables pass reference tests (240 tests, `tests/unit/`)
- [x] Golden combinational circuits reproduce committed tables (5 fixtures, 100× determinism)
- [x] Golden sequential circuits reproduce committed waveforms (3 fixtures, 100× determinism)
- [x] Sequential clock/state semantics tested (INC/DEC boundary rules, async, four-valued)
- [x] Verification engine: exhaustive invariants with scope labels (FSM firings, comb vectors)
- [x] Signature test: faulty traffic FSM → reproducible counterexample (test_signature_verification.py)
- [x] Fault injection + repair: seeded fault detected, repair re-verified (test_signature_phase4.py)
- [x] Optimization: objective improves, truth table preserved (test_signature_phase5.py)
- [x] Interrupts: NMI/INTR/IF masking, deterministic schedule (test_interrupts.py)
- [x] 8086 subset: golden programs + flag vectors (test_golden_cpu.py)
- [x] Co-simulation: port latency + X propagation (test_cosim.py)
- [x] Explanations: evidence citations, deterministic (test_explain.py, test_signature_phase9.py)
- [x] 659 tests passing, 91% coverage (CI gate ≥90%)
- [x] ruff check + ruff format clean
- [x] mypy --strict clean across all 8 packages (56 source files)
- [x] Web production build (tsc + vite) passes
- [x] Remote CI (GitHub Actions): ruff + format + mypy + pytest+cov + web build

## Determinism

- [x] Combinational: 100× byte-identical trace replay per golden fixture
- [x] Sequential: 100× byte-identical trace replay per golden fixture
- [x] Explanations: deterministic (same evidence → same output, pinned by test)
- [x] All engines: no clocks, no randomness, no wall-time dependencies

## Deployment

- [x] Dockerfile.api: Python 3.12 slim, uvicorn, health check
- [x] Dockerfile.web: Node 20 build stage + nginx, /api proxy
- [x] docker-compose.yml: api + web with health-check dependency
- [x] .dockerignore: excludes .venv, node_modules, .git, PRIVATE_CONTEXT.md

## Known limitations (see docs/LIMITATIONS.md for the full list)

- No persistence, auth, or multi-tenancy (D5)
- No Docker image published to a registry (local build only)
- 8086 UI panel not implemented (API + tests only)
- No Playwright E2E suite for the web workspace
- Explanation engine is rule-based, not an LLM

## Post-release backlog

1. Persistence (PostgreSQL) + auth + multi-tenancy (D5 revisit)
2. 8086 workspace UI (editor + registers/interrupt/waveform panels)
3. Playwright E2E suite for the web workspace
4. FSM state-graph SVG visualization
5. Sequential component palette in the editor
6. Performance benchmarks (1000-gate circuit, per the master prompt budget)

## Curriculum phases (C-series)

- [x] C1 — numsys engine (bases, complements, BCD/Excess-3/Gray, step traces)
- [x] C2 — boolean engine (parser, SOP/POS, theorems, NAND/NOR transform)
- [x] C3 — K-map + Quine-McCluskey minimization with don't-cares
- [x] C4 — combinational library (full adder, binary→Gray, parity, 4:1 mux)
- [x] C5 — sequential curriculum (characteristic/excitation tables, detectors)
- [x] C6 — 8086 timing model, expanded mnemonics, addressing modes
- [x] C7 — 8259 PIC engine: ICW/OCW state machine, priority/rotation, EOI family,
      scheduled delivery traces, PIC→8086 end-to-end integration, `POST /api/8086/pic`
