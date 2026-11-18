# Engineering Audit — full-platform review (refresh of docs/PHASE1_AUDIT.md)

Date: 2026-11-18 · Auditor: principal-engineer review session · Branch: `main` @ `9c8876b`

## Method

Static inspection of every engine, router, component, config and doc; the full gate
suite; the 33-check live API probe; the 10-probe engine boundary validation; a
dead-code/duplication scan; coverage-by-module analysis; and a docs-vs-implementation
consistency check. Code changes were made only after this report.

## Prioritized findings

### P2 — worth fixing now

| ID | Finding | Evidence | Severity | Fix |
|---|---|---|---|---|
| N1 | **Docs drift — tour banner says "five tabs / Five views"** while the workspace has seven (FSM and Faults were added in Phase 7). Stale alt text in `README.md:50` and caption inside `docs/assets/tour.svg`. | grep "five tabs" README.md | P3→fixed this session | Update alt text + tour banner pills/caption |
| N2 | **Coverage hotspots — error classes untested**: `cpu8086/errors.py` 77%, `pic8259/errors.py` 83%, `curriculum/errors.py` 83%, `cosim.py` 87%. The uncovered lines are the category-validation guards of the typed-error classes — a wrong category would raise a raw `ValueError` instead of the intended error. | coverage report | P3 | Direct unit tests for the category guards |
| N3 | **Duplication (accepted, documented)**: `evaluate_expression` exists in both `verify_engine/expressions.py` and `boolean_engine/boolean.py`; `truth_table` in both `logic_engine` and `boolean_engine`. Different semantics per domain — consolidation would couple engines. | grep | P3 | Keep; documented here so it is a decision, not an accident |

### P3 — accepted scope limits (from PHASE1_AUDIT, unchanged)

- A1 persistence/auth (D5) — the only production blocker.
- B1 PIC cascade · B2 REP per-iteration timing · B4 Docker live-run (daemon offline).
- B6 hotspots = N2 above. B7 three justified `type: ignore` in verify expressions.

### Verified clean

- 917 tests, coverage 92.12% (gate 90) · ruff/format · mypy --strict 0 errors
- web build clean · pip check clean · npm audit 0 vulnerabilities
- live probe 33/33 · engine validation 10/10
- No orphan frontend components; no TODO/FIXME/debug prints; no dead exports
- Full Mimosa security scan: 0 findings (sealed `bd6d05807131`); `.mimosa/` state untracked

## Remediation order (executed in this session)

1. N1 docs/tour refresh → commit
2. N2 error-class guard tests (target: aggregate ≥ 92.3%, hotspots ≥ 90%) → commit
3. Live-link refresh: rebuild UI, restart the single-origin production server, browser-verify
