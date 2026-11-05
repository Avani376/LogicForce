# Limitations and Honest Claims — LogicForge

Current as of Phase 0/1 build session (engine 0.1.0). This file is the anti-overclaim
contract: nothing below is “planned soon” marketing; it is a list of what the platform
cannot do today.

## Engine (implemented scope)

- **Combinational only.** No flip-flops, registers, counters, FSMs, clocks, or waveforms
  yet (Phase 2). Any sequential behavior claim is out of scope.
- **No delay or timing model.** Zero-delay value-change semantics only; no setup/hold,
  propagation delays, or glitch analysis — and none are claimed.
- **Combinational loops are rejected** (`COMBINATIONAL_LOOP`); intentional oscillators with
  delta-cycle semantics are not simulated (D8).
- **No tri-state resolution.** Multi-driver nets are errors; `Z` exists in the value domain
  but no v1 component drives it.
- **Truth tables are exhaustive up to 12 primary inputs**; larger circuits are refused,
  not truncated.

## Platform scope

- **No verification engine yet** (Phase 3): no property checks, no counterexamples. The
  VerificationReport schema exists on paper only.
- **No fault injection, repair, or optimization** (Phases 4–5).
- **No 8086 emulator, interrupts, or co-simulation** (Phases 6–8).
- **No AI assistance** (Phase 9). When it arrives it will be advisory and labeled; it will
  not compute results.
- **No persistence, users, auth, or multi-tenancy** (D5): the API is a stateless compute
  service. Anyone with network access to the dev server can submit circuits.
- **No Docker/deployment artifacts** (D6): local development only.
- **Single-machine testing**: validated on Windows (Python 3.13, Node 24) and CI targets
  Ubuntu (Python 3.12, Node 20); no claim about other environments.

## Metrics honesty

Any future performance numbers will be measured on this repository's own benchmarks and
labeled with the machine they were measured on. Estimated metrics (e.g., logic depth vs
physical delay) will be labeled as abstract-model estimates, never as hardware behavior.
