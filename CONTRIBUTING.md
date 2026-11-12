# Contributing to LogicForge

Short version: pick an issue, keep engines deterministic, write the contract
before the code, and make CI green before you ask for review.

## Setup

```bash
git clone https://github.com/Avani376/LogicForce.git
cd LogicForce

# Backend (Python 3.12+)
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; .venv/bin/activate elsewhere
pip install -r requirements.txt
pip install -e .

# Frontend
cd apps/web && npm install
```

Run both:

```bash
uvicorn logicforge_api.main:app --port 8000    # terminal 1
cd apps/web && npm run dev                     # terminal 2 — http://localhost:5173
```

## Every PR must pass

```bash
ruff check .
ruff format --check .
pytest --cov --cov-fail-under=90
mypy engines/logic/logic_engine engines/sequential/sequential_engine \
     engines/verify/verify_engine engines/faults/fault_engine \
     engines/repair/repair_engine engines/optimize/optimize_engine \
     engines/cpu8086/cpu8086 engines/cosim/cosim_engine engines/numsys/numsys \
     engines/boolean/boolean_engine engines/pic8259/pic8259 \
     engines/curriculum/curriculum_engine apps/api/logicforge_api
cd apps/web && npm run build
```

CI runs exactly these on every push to `main` and on PRs. If your change adds a
new engine package, add it to the mypy list in `.github/workflows/ci.yml`, to
`[tool.setuptools.packages]` + `[tool.setuptools.package-dir]` + the coverage
`source` list in `pyproject.toml`, and reinstall (`pip install -e .`).

## Repository layout

```
engines/            one folder per engine, each is an installable package
  logic/            combinational circuits, four-valued logic {0,1,X,Z}
  sequential/       flip-flops, FSMs, clock-edge simulation
  verify/           invariant checking + evidence-grounded explanations
  faults/ repair/   fault injection, diagnosis, re-verified repair
  optimize/         equivalence-checked rewrites
  cpu8086/          assembler, executor, timing, interrupts
  cosim/            shared circuit+CPU event scheduler
  numsys/           base conversion, complements, codes
  boolean/          parser, theorems, K-map, Quine-McCluskey
  pic8259/          programmable interrupt controller model
  curriculum/       lessons + engine-graded exercises
apps/api/           FastAPI routers — thin; engines do the work
apps/web/           React + Vite workspace (Circuit, 8086, Verify, Explain, Visuals)
tests/              unit/, golden/, property/, integration/, per-engine folders
docs/semantics/     normative contracts, one per engine
```

## The two rules that matter

1. **Engines are deterministic.** No wall-clock, no randomness, no environment
   reads inside `engines/*`. Same input + same engine version must produce
   byte-identical output — there are 100×-replay tests that enforce this, and a
   PR that breaks them will not be merged.

2. **Contracts come before code.** If you add or change engine behavior, write
   or amend `docs/semantics/<topic>.md` in the same PR, first. The doc is the
   spec; tests check the code against it. Claims in docs must match what the
   code actually does — overclaiming gets reverted.

Results carry scope labels: `EXHAUSTIVE(k)`, `BOUNDED(k)`, `SAMPLED(n)`,
`INCOMPLETE`. If your engine can't prove exhaustiveness, label it honestly.

## How to add things

**A new API endpoint:** engine function first (with tests), then a thin router
in `apps/api/logicforge_api/routers/`, typed 4xx mapping in the same style as
`routers/cpu8086.py`, an integration test in `tests/integration/`, and a row in
`docs/API.md`.

**A new web panel:** one component in `apps/web/src/components/`, wired in
`App.tsx`'s tab list, using the existing CSS vocabulary in `styles.css` rather
than inline styles. The UI never computes results — it renders engine output.

**A new curriculum exercise:** add it to
`engines/curriculum/curriculum_engine/catalog.py` with a grading kind that
routes to an engine (never string comparison), then extend
`tests/curriculum/test_grader.py`.

**A new instruction in the 8086:** amend `docs/semantics/cpu8086.md` (operand
forms + flag semantics), add the mnemonic to `assembler.py`, implement in
`machine.py`, and pin the flag vectors in `tests/cpu8086/`.

## Commits

Conventional style, one logical change per commit:
`feat(engine): …`, `fix(api): …`, `test(curriculum): …`, `docs: …`. Run the
checks before pushing — the CI log is public.

## Where the work is

See `docs/PROJECT_CONTEXT.md` for the current state and the shortlist of open
work (FSM state-graph view, persistence/auth, cascade PIC, string-op timing
modeling). Good first tasks: extending the curriculum catalog, more golden
circuits, and expanding the live API probe in `scripts/live_api_probe.py`.
