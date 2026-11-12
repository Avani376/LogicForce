# Semantics: Assistant (interactive Q&A layer)

Status: **CONTRACT** (implemented in `apps/api/logicforge_api/assistant.py`)
Layer version: 0.1.0 · Upstreams: explain engine, curriculum engine

## What the assistant is

An **interactive question router** — the user-facing "AI" of LogicForge. It is
deliberately *not* an LLM: every answer is produced by deterministic rules that
route the question to a real source (engine output, the curriculum catalog, or
authored product guidance) and cite that source. Same question + same context +
same versions ⇒ byte-identical answer. This enforces the platform's
architectural principle: **AI never fabricates simulation states, verification
results, counterexamples, diagnoses, or equivalence claims.**

## Request

```json
{ "question": "why did my verification fail?",
  "context": { …optional engine evidence… } }
```

`question` is a non-empty string (≤ 500 chars after trim). `context` is optional
arbitrary engine evidence (same shape the explain endpoint accepts).

## Intent routing (deterministic, first match wins)

| Order | Intent | Trigger (case-insensitive) | Grounding |
|---|---|---|---|
| 1 | `exercise` | "exercise", "practice", "quiz", "test me" | curriculum catalog (exercise ids + prompts + hints) |
| 2 | `lesson` | "what is", "who", "explain the concept", "lesson", "define", or ≥ 1 content keyword match | curriculum catalog — lessons scored by keyword overlap with title/summary/key points; ties broken by lesson id |
| 3 | `explain` | "why", "explain", "trace", "counterexample", "fail" **and** context present | explain engine on the provided evidence (cites real trace steps) |
| 4 | `guide` | product keywords: "pic", "interrupt", "8086", "optimize", "fault", "repair", "verify", "visual", "kmap", "gray", "bcd" | authored capability guidance (what the tab does, where to go) |
| 5 | `meta` | fallback | capability overview + suggestions |

If order 3 matches but no context was provided, the assistant answers with
order-4 guidance for the relevant tab **plus** an explicit note that engine
evidence is needed for a grounded explanation — it never invents one.

## Response

```json
{ "answer": "…",
  "grounding": "engine_output" | "catalog" | "guidance",
  "kind": "exercise" | "lesson" | "explain" | "guide" | "meta",
  "scope": "EXHAUSTIVE" | "RULE_BASED",
  "sources": ["curriculum_engine 0.1.0", …],
  "suggestions": ["Try the Learn tab →", …],
  "data": { …intent-specific payload… } }
```

- `grounding: engine_output` — the answer body came from a computation performed
  by an engine this request (only the `explain` intent).
- `grounding: catalog` — retrieved from the shipped, test-covered curriculum
  catalog.
- `grounding: guidance` — authored product facts (tab purposes, workflow order);
  contains no simulation/verification claims.
- `data.exercises` / `data.lesson` / `data.explanation` carry the upstream
  payloads verbatim so the UI can render them.

## Errors

Typed 400 envelope: `ASSISTANT_ERROR` with `category`
`EMPTY_QUESTION` (blank/oversized question). A `context` that is not a JSON
object is rejected earlier, by the request schema, as a standard HTTP 422 —
the engine-level `BAD_CONTEXT` guard applies to direct library callers.
Engine errors surfaced while
fulfilling an `explain` intent are returned as answers with
`grounding: guidance` + the error text — the assistant degrades gracefully,
never crashes, never invents.

## Generative layer (optional, BYOK)

`POST /api/assistant/chat` — when the user supplies an API key (request header
`X-Assistant-Key`, or server env `LOGICFORGE_AI_API_KEY`), the conversation is
answered by an OpenAI-compatible chat model. Grounding rules still apply:

- The server first runs the deterministic router (`ask()`) and injects its
  answer, the matched catalog facts, and the user's engine evidence into the
  system prompt. The model is instructed to extend that material, not replace
  it, and to say "I don't know" outside it.
- Responses carry `grounding: "generative"` and name the `model` used — the UI
  labels them differently from grounded answers.
- The key is never logged, never persisted server-side, and never committed.
  `LOGICFORGE_AI_BASE_URL` selects the provider (any OpenAI-compatible API);
  default `https://api.openai.com/v1`.
- No key ⇒ typed `ASSISTANT_ERROR(NO_KEY)`; upstream failure ⇒ typed
  `ASSISTANT_ERROR(UPSTREAM)` — the UI falls back to the grounded router.

## Out of scope

Free-form LLM generation, conversation memory across requests (each ask is
stateless), and any claim not backed by an engine, the catalog, or authored
product facts.
