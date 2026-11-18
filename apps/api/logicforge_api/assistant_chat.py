"""Generative chat layer: OpenAI-compatible BYOK, always grounded (assistant.md).

The deterministic router runs first; its answer and the user's engine evidence
form the system prompt. The model extends that material — it never replaces it.
The API key is read per-request and never persisted or logged.
"""

from __future__ import annotations

import os
import socket
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

import httpx

from logicforge_api.assistant import AssistantError, ask

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
KEY_HEADER = "X-Assistant-Key"
TIMEOUT_SECONDS = 45
MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 4000
MAX_GROUNDED_CHARS = 24000
ALLOWED_ROLES = {"user", "assistant"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}

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
    """Deterministic router output becomes the model's grounded material.

    The serialized payload is capped so a huge engine dump cannot blow up the
    provider request or dilute the grounding."""
    grounded = ask(question, context)
    payload = {
        "router_answer": grounded["answer"],
        "kind": grounded["kind"],
        "grounding": grounded["grounding"],
        "sources": grounded["sources"],
        "user_engine_evidence": context,
    }
    grounded_text = script_safe_json(payload)
    if len(grounded_text) > MAX_GROUNDED_CHARS:
        grounded_text = grounded_text[:MAX_GROUNDED_CHARS] + '","truncated":true}'
    return SYSTEM_PROMPT_TEMPLATE.format(grounded=grounded_text)


def script_safe_json(value: Any) -> str:
    """Compact JSON with < > & escaped so it is safe inside any prompt/template."""
    import json

    text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def validate_provider_url(base_url: str) -> str:
    """SSRF guard: https only, no credentials, and the host must not be
    loopback/private/reserved — the key must only travel to a real provider.

    Validation is syntactic (no DNS): a public hostname that resolves to a
    private IP cannot be caught here, which is documented in assistant.md."""
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username is not None or parsed.password is not None:
        raise AssistantError(
            "BAD_PROVIDER",
            "base_url must be an https:// URL with no embedded credentials — "
            "this engine refuses to send your key anywhere else",
        )
    try:
        ip = ip_address(host)
    except ValueError:
        ip = None
    blocked = (
        host in _LOCAL_HOSTS
        or host.endswith(".local")
        or (
            ip is not None
            and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified)
        )
    )
    if blocked:
        raise AssistantError(
            "BAD_PROVIDER",
            f"provider host {host!r} is loopback/private/reserved — server-side requests "
            "must target a public https provider",
        )
    return base_url.rstrip("/")


def validate_conversation(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Cap and sanitize the conversation history (assistant.md trust rules)."""
    if len(messages) > MAX_MESSAGES:
        raise AssistantError("BAD_CONTEXT", f"conversation exceeds {MAX_MESSAGES} messages")
    cleaned: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role", "")
        content = str(message.get("content", ""))
        if role not in ALLOWED_ROLES:
            raise AssistantError("BAD_CONTEXT", f"message role must be 'user' or 'assistant', got {role!r}")
        if len(content) > MAX_MESSAGE_CHARS:
            content = content[:MAX_MESSAGE_CHARS]
        cleaned.append({"role": role, "content": content})
    return cleaned


def resolve_provider_addresses(base_url: str) -> list[str]:
    """Resolve the provider host and return every address it maps to.

    DNS-rebinding defense (assistant.md): all resolved addresses must be public.
    A name that resolves to loopback/private/reserved space is rejected before any
    request is made. Validation is resolution-time; the residual check-then-use
    window is documented in the contract."""
    host = (urlparse(base_url).hostname or "").lower()
    if host in _LOCAL_HOSTS:
        raise AssistantError("BAD_PROVIDER", f"provider host {host!r} is loopback — rejected")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise AssistantError(
            "BAD_PROVIDER",
            f"provider host {host!r} could not be resolved ({exc.__class__.__name__})",
        ) from exc
    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0])
        ip = ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
            raise AssistantError(
                "BAD_PROVIDER",
                f"provider host {host!r} resolves to a non-public address ({address}) — rejected",
            )
        addresses.append(address)
    return addresses


def chat(
    messages: list[dict[str, str]],
    question: str,
    context: dict[str, Any] | None,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Call an OpenAI-compatible endpoint. Typed errors on upstream failure."""
    api_key = api_key.strip()
    if not api_key or len(api_key) > 512 or any(ch.isspace() for ch in api_key):
        raise AssistantError("BAD_CONTEXT", "malformed API key — expected a single token without whitespace")
    if base_url is not None:
        base_url = validate_provider_url(base_url)
    chosen_base = (base_url or os.environ.get("LOGICFORGE_AI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    # DNS-rebinding defense: resolve now and reject non-public addresses.
    resolve_provider_addresses(chosen_base)
    messages = validate_conversation(messages)
    chosen_model = model or DEFAULT_MODEL
    system_prompt = build_system_prompt(question, context)
    payload = {
        "model": chosen_model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": 0.3,
        "max_tokens": 600,
    }
    try:
        # follow_redirects=False: a provider must not bounce our key to another host.
        with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
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
    grounded = build_system_prompt(question, context)
    return {
        "answer": answer,
        "grounding": "generative",
        "kind": "chat",
        "scope": "GENERATIVE",
        "model": chosen_model,
        "sources": ["openai-compatible provider", "logicforge grounded router"],
        "data": {"grounded_router_ran": True, "system_prompt_chars": len(grounded)},
    }
