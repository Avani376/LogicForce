# Phase 1 — Complete Repository Audit

Date: 2026-11-13 · Scope: full codebase, architecture, APIs, frontend, backend,
documentation. Method: static inspection + the full gate suite + the 33-check
live API probe (`scripts/live_api_probe.py`) against a running server. This audit
found **no P0/P1 defects**; findings below are confirmed debt and gaps, ordered
by priority. The working tree was left functional throughout — nothing here
changed behavior.

## Evidence snapshot at audit time

| Check | Result |
|---|---|
| pytest (unit/golden/property/integration, coverage gate 90%) | 909 passed, 4 xfailed, 92.21% |
| ruff check + format --check | clean (173 files) |
| mypy --strict (12 packages + API) | 0 real errors (3 justified `type: ignore` in verify expressions) |
| web build (tsc + vite) | clean |
| Live API probe | 33/33 PASS incl. hostile inputs |
| CI on main | green at `e5c0c52` |
| TODO/FIXME/debug prints/bare-except swallows | **0** found |

## Prioritized findings

### P2 — significant, planned (not bugs)

| ID | Finding | Where | Recommended action |
|---|---|---|---|
| A1 | No persistence/auth/multi-tenancy (decision D5). Runs, circuits, and progress are session-only. | whole stack | Needs a storage design decision first; blocker for any shared deployment only |
| A2 | FSM state-graph visualization missing — engine, reachability endpoint, and API exist, but there is no UI view for FSMs. | apps/web | New panel rendering the transition graph; data already available via `/api/fsm/reachable` |
| A3 | Curriculum engine is API-only since the Learn tab was removed by product decision. Exercises/lessons are reachable only via `/api/curriculum/*` and Sparky's grounded answers. | engines/curriculum | Intentional. Revisit only if a learning UI is wanted again |

### P3 — technical debt / honest scope limits (documented, not accidental)

| ID | Finding | Where | Recommended action |
|---|---|---|---|
| B1 | PIC cascade (multi-chip) not simulated; ICW3 recorded only. | engines/pic8259 | Contract-declared out of scope; design first if attempted |
| B2 | A REP-prefixed string op executes as one step; per-iteration timing not modeled. | engines/cpu8086/timing.py | Add per-iteration cycle counts behind a contract amendment |
| B3 | Poll mode (`OCW3 P=1`) rejected as typed error. | engines/pic8259 | Fine for the educational subset; leave unless requested |
| B4 | Docker images not verified end-to-end at audit time — Docker daemon offline locally; config statically verified. | Dockerfile.*, compose | Run `docker compose up --build` when a daemon is available |
| B5 | `scripts/live_api_probe.py` is the only executable doc of endpoint behavior beyond tests; keep in sync when endpoints change. | scripts | Already referenced in CONTRIBUTING; wire into CI as an optional job if flakiness allows |
| B6 | Coverage hotspots: `pic8259/errors.py` 83%, some driver branches — aggregate still 92.21%. | tests | Add edge-case tests opportunistically |
| B7 | 3 `type: ignore[arg-type]` in verify expression evaluator (recursive AST typing). | verify/expressions.py | Refactor with a typed AST visitor if touched again |

### Verified non-issues (checked, no action needed)

- No TODO/FIXME markers, no debug prints, no bare-except swallows in `engines/` or `apps/api/`.
- Endpoint counts consistent across README, architecture diagram, and `docs/API.md` (21).
- Dependency declarations match actual imports in both ecosystems; `pip check` and `npm audit` clean.
- Line-ending/CI hazards from earlier sessions (CRLF blobs, I001 ordering) fully resolved — format check clean.
- Engine version strings consistent between `README.md` and each package's `version.py`.

## Conclusion

The repository is in a verified, releasable-as-prototype state. The only paths to
"production" run through A1 (persistence/auth) and B4 (live Docker verification);
everything else is either an intentional scope boundary or incremental polish.
