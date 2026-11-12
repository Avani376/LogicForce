# Project Context — read this before your first PR

Last updated: 2026-11-13. If something here contradicts the code, trust the
code and fix this file in your PR.

## What this project is

LogicForge is a digital-systems engineering workspace: you design circuits and
8086 programs, and deterministic engines simulate, verify, break, repair, and
optimize them. The defining constraint is that **the engines are the only
source of truth**. The UI explains; the assistant routes; nothing in the stack
is allowed to invent a simulation result, a verification verdict, or a number.

There is an optional generative layer for the chat assistant (bring-your-own
API key). It is deliberately constrained: the deterministic router runs first,
its output plus engine evidence form the system prompt, and replies are labeled
`generative` so users can tell them apart from grounded ones. Don't loosen
this — it's the platform's main differentiator.

## Current state (honest)

- 12 engine packages, 22 API endpoints, ~900 tests, coverage ~92% (gate: 90%).
- 8086 covers the declared educational subset end to end: ALU, MUL/IMUL/DIV/IDIV,
  shifts/rotates, string ops with REP and the DF flag, CALL/RET, interrupts,
  published timing, addressing modes.
- The 8259 PIC is modeled single-chip (no cascade). A REP block executes as one
  step — documented in `docs/semantics/cpu8086.md`, don't "fix" it silently.
- CI is green on `main`; the live-API probe in `scripts/live_api_probe.py`
  passes 33/33 against a running server.

## Architecture in one paragraph

FastAPI app (`apps/api`) exposes thin routers; every router calls an engine
package under `engines/` and maps typed engine errors (`LogicEngineError`
subclasses with categories) to HTTP 4xx envelopes. The React workspace
(`apps/web`) renders engine output and never computes results itself. Data
contracts are pinned by `docs/semantics/*.md` — each engine has one, written
before the code, and tests check code against contract.

## Data flow example (worth understanding early)

1. User clicks Simulate → `POST /api/circuits/simulate` with the circuit JSON.
2. Router parses/validates → `logic_engine` propagates values topologically and
   returns outputs + a trace + a SHA-256 `input_hash` (same inputs ⇒ same hash).
3. The UI renders outputs, trace rows, and the scope label. The hash is what
   makes runs replayable — keep it flowing through any new endpoint you add.

## Where things live (the non-obvious bits)

- Flag semantics for the 8086: `engines/cpu8086/cpu8086/registers.py` — helpers
  like `add_flags`, `mul_flags`. Undefined-by-Intel flags are *defined* here
  (documented deviation); don't change them without a contract amendment.
- Priority rotation in the PIC: `engines/pic8259/pic8259/controller.py`
  (`_priority_floor`). The driver enforces one INTA per boundary.
- Minimality grading for exercises: `engines/curriculum/curriculum_engine/
  grader.py` — equivalence over minterms (A is the MSB of the row index) plus a
  literal-count comparison against QM.
- Assistant grounding: `apps/api/logicforge_api/assistant.py` (router) and
  `assistant_chat.py` (BYOK layer). Intent order and grounding labels are
  contractual — see `docs/semantics/assistant.md`.
- Mascot reactions: components dispatch `sparky:event` CustomEvents
  (`emitSparky` in `apps/web/src/components/Sparky.tsx`); Sparky listens and
  changes mood/speech. Sounds are synthesized in `lib/sounds.ts` (WebAudio, no
  audio assets).

## Testing culture

- Unit + golden (committed expected outputs) + property (hypothesis) +
  integration (FastAPI TestClient) + a live probe script.
- The golden fixtures are the regression net for determinism — 100× byte-identical
  replays. If you intentionally change engine output, update the fixture **and**
  the contract in the same PR, and say why in the commit message.
- Coverage gate is 90% enforced in CI; the practical bar is "every new branch
  and error path has a test".

## Environment variables (all optional)

- `LOGICFORGE_AI_API_KEY` — server-side fallback key for the generative chat
  layer. Never commit one. The browser-local key (Sparky settings) takes
  precedence when the client sends it.
- `LOGICFORGE_AI_BASE_URL` — any OpenAI-compatible provider; defaults to
  `https://api.openai.com/v1`.

## Open work (pick one)

1. FSM state-graph visualization in the web workspace (the FSM engine and the
   reachability endpoint already exist).
2. Cascade (multi-PIC) support behind a contract amendment.
3. Per-iteration timing for REP string ops in `engines/cpu8086/cpu8086/timing.py`.
4. Persistence (project/version storage) — needs a design decision on D5 first.
5. More golden circuits and curriculum exercises — always welcome, low risk.

## Non-goals

Browser compatibility below modern evergreen browsers, multi-user auth (that's
the D5 persistence decision), and any feature that requires the UI to compute
results locally.
