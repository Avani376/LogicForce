# Testing — LogicForge

Run everything from the repository root:

```bash
.venv/Scripts/activate            # Windows Git Bash: source .venv/Scripts/activate
pytest                            # all tests
pytest tests/unit tests/golden    # subsets
ruff check .                      # lint
mypy engines/logic/logic_engine apps/api/logicforge_api   # strict type check
```

CI runs the same four steps plus a coverage gate (`--cov-fail-under=90` on
`logic_engine` + `logicforge_api`).

## Test categories (implemented in Phase 1)

| Category | Location | What it proves |
|---|---|---|
| Unit | `tests/unit/` | Gate tables exhaustive over {0,1,X,Z}²; N-input folding; constants; primary-input default `X`; validation codes; topological `(depth, id)` ordering; trace event shape |
| Golden | `tests/golden/` | Five reference circuits (half adder, full adder, 2:1 mux, 4:1 mux, 2:4 decoder) reproduce committed expected truth tables byte-for-byte |
| Determinism | `tests/golden/` | Every fixture simulated 100× yields byte-identical serialized results |
| Property | `tests/property/` | hypothesis-generated acyclic DAGs: simulator output ≡ independent naive recursive evaluator; trace `seq` strictly monotonic; every net's final value matches the evaluator |
| Integration | `tests/integration/` | FastAPI endpoints: health, validate (valid + each error class), simulate, truth-table, bound errors, 422 shape errors |

## Golden fixtures

`tests/golden/fixtures/*.json` contain the circuit (schema v1) **and** the expected truth
table, derived by hand from the semantics contracts and version-controlled. A failing
golden test means engine behavior changed — never edit a fixture to make a test pass
without a semantics-doc change in the same commit.

## Regression rule

Every bug fix ships with the test that would have caught it.

## Later categories (planned, from the master prompt)

Sequential/clock tests (Phase 2), verification counterexamples (3), fault detection (4),
repair re-verification (4), optimization equivalence (5), 8086 differential tests (6),
UI/Playwright (1c onward). Not claimed as done until their phase exit criteria pass.
