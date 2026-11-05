# Engineering Decisions — LogicForge

Decision log. Each entry: decision, rationale, consequences. Newest at the bottom.

## D1 — Follow the prescribed monorepo layout verbatim

The master prompt prescribes `apps/web`, `apps/api`, `engines/*`, `tests/`, `docs/`.
Adopted exactly, including `docs/semantics/`. Consequence: predictable navigation for future
sessions and reviewers; slight nesting cost for import paths, solved by D2.

## D2 — Editable install with per-package `package-dir` mapping

Keeping the prescribed tree while allowing clean imports (`logic_engine`,
`logicforge_api`) is solved with setuptools per-package mappings in `pyproject.toml` and
`pip install -e .`. Rejected alternatives: renaming/relocating packages (breaks the
prescribed layout), `sys.path` hacks (fragile across pytest/mypy/uvicorn/CI).

## D3 — Python 3.13 locally, `requires-python >= 3.12`

The local interpreter is 3.13.5; the master prompt names 3.12. Code is written to the 3.12
language level (no 3.13-only syntax) and CI runs 3.12. Consequence: both versions work.

## D4 — Strict validation: dangling input pins are errors, not defaults

`docs/semantics/circuit-graph-schema.md` makes an unconnected gate input pin an
`DANGLING_INPUT_PIN` error. Rationale: a defaulted input silently converts a wiring mistake
into wrong-but-plausible outputs — the exact failure mode this platform exists to prevent.
Unset *primary* inputs do default to `X` (explicit, documented, deterministic) because a
partially-driven input vector is a legitimate user intent. Consequence: the UI must surface
validation errors prominently (Phase 1c does).

## D5 — Persistence and auth deliberately deferred

The master prompt prescribes PostgreSQL, but every Phase 1 endpoint is a pure function of
its request body (circuit + inputs → report). Adding a database now would add infra and
attack surface without user value. Decision: stateless API in v1; persistence (projects,
versions, runs) lands with the verification engine phase, when saved artifacts become
meaningful. Recorded as a conscious deviation with a revisit trigger, not an omission.

## D6 — No placeholder Docker/docker-compose

`docker-compose.yml` appears in the documented target layout, but shipping an empty or fake
compose file violates the “never fake completed features” rule. It will be added in the
deployment phase when there is a real multi-process system to orchestrate.

## D7 — Custom SVG canvas instead of a graph library (web)

React Flow (or similar) is suggested in the docs. For the Phase 1 MVP a custom SVG canvas
is chosen: zero heavy dependencies, full control over keyboard accessibility and
color-blind-safe signal colors (both are master-prompt requirements), and the Phase 1 graph
(gates + wires) is small enough that wire routing does not justify a library. Revisit
trigger: automatic routing needs or >100-component canvases.

## D8 — Combinational loops are validation errors in v1

Delta-cycle iteration for intentional loops is deferred to Phase 2 (where clocked state
makes event scheduling meaningful). Rationale: an unterminated combinational loop in v1 has
no defined semantics; refusing it is the honest behavior. Tracked in LIMITATIONS.

## D9 — Determinism enforcement is a test, not a hope

The byte-identical-trace contract is enforced by a committed test that replays every golden
fixture 100× and compares serialized bytes, plus CI re-runs. Consequence: any accidental
nondeterminism (dict ordering, set iteration) fails the build, not the user.

## D10 — Coverage gate ≥90% applies to engines; API is covered too

`pytest --cov` gates `logic_engine` and `logicforge_api` at ≥90% in CI. Rationale: the
master prompt sets this bar for engines; the API surface in v1 is small enough that the
same bar costs little and keeps the HTTP boundary honest.

## D11 — Truth-table bound is a hard 12 inputs

Enumerating ≤ 2^12 = 4096 rows is exhaustive and fast; beyond that the endpoint returns
`TRUTH_TABLE_LIMIT_EXCEEDED`. Rationale: silently truncating would relabel an exhaustive
claim as bounded without telling the user — a scope-label integrity violation.
