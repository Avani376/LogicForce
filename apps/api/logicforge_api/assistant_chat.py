"""Generative chat layer: OpenAI-compatible BYOK, always grounded (assistant.md).

The deterministic router runs first; its answer and the user's engine evidence
form the system prompt. The model extends that material — it never replaces it.
The API key is read per-request and never persisted or logged.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from logicforge_api.assistant import AssistantError, ask

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
KEY_HEADER = "X-Assistant-Key"
TIMEOUT_SECONDS = 45

SYSTEM_PROMPT_TEMPLATE = """You are Sparky, the mascot and guide of LogicForge — a digital-systems \
engineering platform where deterministic engines are the single source of truth.

Rules you must follow:
- The "Grounded material" below was computed by real engines for this user. Build your \
answer on top of it; never contradict it, never invent simulation results, verification \
verdicts, counterexamples, or numbers.
- If something is not covered by the grounded material or the conversation, say plainly \
that you don't know and suggest which LogicForge tab would produce the real answer.
- Keep the mascot's voice: friendly, encouraging, concise (under 180 words unless the \
user asks for depth). Use "EXHAUSTIVE"/"BOUNDED" scope labels exactly as given.
- Digital-systems topics only: circuits, Boolean algebra, number systems, sequential \
logic, the 8086, interrupts and the 8259 PIC, verification, faults, repair, optimization.

Grounded material (from the deterministic router and engines):
{grounded}"""


def resolve_key(header_key: str | None) -> str:
    """Header key wins; env var is the fallback. No key → typed error."""
    key = (header_key or "").strip() or os.environ.get("LOGICFORGE_AI_API_KEY", "").strip()
    if not key:
        raise AssistantError(
            "NO_KEY",
            "no API key provided — add one in Sparky's chat settings (stored only in your "
            "browser) or set LOGICFORGE_AI_API_KEY on the server; until then Sparky answers "
            "from the grounded catalog",
        )
    return key


def build_system_prompt(question: str, context: dict[str, Any] | None) -> str:
    """Deterministic router output becomes the model's grounded material."""
    grounded = ask(question, context)
    payload = {
        "router_answer": grounded["answer"],
        "kind": grounded["kind"],
        "grounding": grounded["grounding"],
        "sources": grounded["sources"],
        "user_engine_evidence": context,
    }
    return SYSTEM_PROMPT_TEMPLATE.format(grounded=script_safe_json(payload))


def script_safe_json(value: Any) -> str:
    """Compact JSON with < > & escaped so it is safe inside any prompt/template."""
    import json

    text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def chat(
    messages: list[dict[str, str]],
    question: str,
    context: dict[str, Any] | None,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Call an OpenAI-compatible endpoint. Typed errors on upstream failure."""
    chosen_base = (base_url or os.environ.get("LOGICFORGE_AI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    chosen_model = model or DEFAULT_MODEL
    system_prompt = build_system_prompt(question, context)
    payload = {
        "model": chosen_model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": 0.3,
        "max_tokens": 600,
    }
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{chosen_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise AssistantError(
            "UPSTREAM",
            f"the AI provider could not be reached ({exc.__class__.__name__}) — "
            "Sparky answers from the grounded catalog instead",
        ) from exc
    if response.status_code in (401, 403):
        raise AssistantError(
            "UPSTREAM",
            "the provider rejected that API key (401/403) — check it in Sparky's settings; "
            "the key is never stored server-side",
        )
    if response.status_code != 200:
        raise AssistantError(
            "UPSTREAM",
            f"the AI provider returned HTTP {response.status_code} — Sparky answers from the grounded catalog instead",
        )
    body = response.json()
    try:
        answer = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AssistantError("UPSTREAM", "the provider response had no answer content — try again") from exc
    return {
        "answer": answer,
        "grounding": "generative",
        "kind": "chat",
        "scope": "GENERATIVE",
        "model": chosen_model,
        "sources": ["openai-compatible provider", "logicforge grounded router"],
    }
