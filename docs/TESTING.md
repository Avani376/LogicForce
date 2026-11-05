# Testing — LogicForge

Run everything from the repository root:

```bash
.venv/Scripts/activate            # Windows Git Bash: source .venv/Scripts/activate
pytest                            # all tests
pytest tests/sequential tests/golden    # subsets
ruff check .                      # lint
ruff format --check .             # formatting gate
mypy engines/logic/logic_engine engines/sequential/sequential_engine apps/api/logicforge_api   # strict type check
```

CI runs the same four steps plus a coverage gate (`--cov-fail-under=90` on
`logic_engine` + `logicforge_api`).

## Test categories (implemented in Phase 1)

| Category | Location | What it proves |
|---|---|---|
| Unit | `tests/unit/` | Gate tables exhaustive over {0,1,X,Z}²; N-input folding; constants; primary-input default `X`; validation codes; topological `(depth, id)` ordering; trace event shape |
| Unit (sequential) | `tests/sequential/` | D/T/JK/SR characteristic tables exhaustive vs the semantics doc (incl. honest X and forbidden SR=11); async table; counter wrap; v2 validation codes; tick order; async override + re-settle; bounds refusals |
| Golden | `tests/golden/`, `fixtures_seq/` | Five combinational reference circuits reproduce committed truth tables; three sequential fixtures (divide-by-2 DFF, 4-bit Johnson counter, mod-8 counter) reproduce committed waveforms + events |
| Determinism | `tests/golden/` | Every fixture (combinational and sequential) simulated 100× yields byte-identical serialized results |
| Property | `tests/property/` | hypothesis-generated acyclic DAGs: simulator ≡ independent naive recursive evaluator; hypothesis-generated DFF feedback networks: sequential tick loop ≡ independent naive cycle evaluator (settle → async → capture → commit) |
| Integration | `tests/integration/` | FastAPI endpoints: health, validate (valid + each error class), simulate, truth-table, bound errors, 422 shape errors |

## Golden fixtures

`tests/golden/fixtures/*.json` (combinational, schema v1) and
`tests/golden/fixtures_seq/*.json` (sequential, schema v2) contain the circuit **and**
the expected results (truth tables / waveforms + events). Expected values are generated
from **closed-form reference definitions** committed in
`scripts/gen_golden_fixtures.py` and `scripts/gen_sequential_fixtures.py` — deliberately
not produced by running the engine, so the engine cannot rewrite its own oracle. A
failing golden test means engine behavior changed — never edit a fixture to make a test
pass without a semantics-doc change in the same commit.

## Regression rule

Every bug fix ships with the test that would have caught it.

## Later categories (planned, from the master prompt)

Sequential/clock tests (Phase 2), verification counterexamples (3), fault detection (4),
repair re-verification (4), optimization equivalence (5), 8086 differential tests (6),
UI/Playwright (1c onward). Not claimed as done until their phase exit criteria pass.
