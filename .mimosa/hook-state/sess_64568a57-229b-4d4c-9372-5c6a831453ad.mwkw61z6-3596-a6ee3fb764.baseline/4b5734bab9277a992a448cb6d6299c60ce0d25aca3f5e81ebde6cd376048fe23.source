"""BYOK chat-layer tests: prompt grounding, key resolution, typed upstream errors."""

from __future__ import annotations

import httpx
import pytest
from logicforge_api.assistant import AssistantError
from logicforge_api.assistant_chat import (
    DEFAULT_BASE_URL,
    KEY_HEADER,
    build_system_prompt,
    chat,
    resolve_key,
    validate_conversation,
    validate_provider_url,
)


class TestKeyResolution:
    def test_header_key_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOGICFORGE_AI_API_KEY", "env-key")
        assert resolve_key("header-key") == "header-key"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOGICFORGE_AI_API_KEY", "env-key")
        assert resolve_key(None) == "env-key"

    def test_no_key_is_typed_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOGICFORGE_AI_API_KEY", raising=False)
        with pytest.raises(AssistantError) as exc:
            resolve_key(None)
        assert exc.value.category == "NO_KEY"

    def test_blank_header_falls_through_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOGICFORGE_AI_API_KEY", "env-key")
        assert resolve_key("   ") == "env-key"


class TestPromptGrounding:
    def test_router_answer_present_in_system_prompt(self) -> None:
        prompt = build_system_prompt("what is a flip-flop?", None)
        assert "Sparky" in prompt
        assert "never invent" in prompt.lower() or "never contradict" in prompt.lower()
        assert "characteristic table" in prompt.lower()  # router's lesson content
        assert '"kind":"lesson"' in prompt

    def test_engine_evidence_embedded(self) -> None:
        context = {"trace": [], "stop_reason": "hlt"}
        prompt = build_system_prompt("why did it stop?", context)
        assert "stop_reason" in prompt
        assert "hlt" in prompt

    def test_prompt_is_script_safe(self) -> None:
        from logicforge_api.assistant_chat import script_safe_json

        escaped = script_safe_json({"q": "<b>& brave"})
        assert "<b>" not in escaped
        assert "\\u003cb\\u003e" in escaped
        assert "&" not in escaped.replace("\\u0026", "")


class TestUpstreamCalls:
    def test_no_key_via_chat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOGICFORGE_AI_API_KEY", raising=False)
        with pytest.raises(AssistantError) as exc:
            chat(messages=[], question="hi", context=None, api_key=resolve_key(None))
        assert exc.value.category == "NO_KEY"

    def test_unreachable_provider_is_typed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(AssistantError) as exc:
            chat(
                messages=[{"role": "user", "content": "hi"}],
                question="hi",
                context=None,
                api_key="k",
                base_url="http://127.0.0.1:1",  # nothing listens here — deterministic failure
            )
        assert exc.value.category == "UPSTREAM"

    def test_provider_401_is_typed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "bad key"})

        transport = httpx.MockTransport(handler)
        original_post = httpx.post

        def routed_post(url: str, **kwargs: object) -> httpx.Response:
            kwargs["transport"] = transport
            return original_post(url, **kwargs)

        monkeypatch.setattr(httpx, "post", routed_post)
        with pytest.raises(AssistantError) as exc:
            chat(messages=[], question="hi", context=None, api_key="bad")
        assert exc.value.category == "UPSTREAM"
        assert "401" in exc.value.message

    def test_successful_generation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["payload"] = json_loads_safe(request.content)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "Sparky says: it toggles!"}}]},
            )

        _inject_transport(monkeypatch, handler)
        result = chat(
            messages=[{"role": "user", "content": "what is a T flip-flop?"}],
            question="what is a T flip-flop?",
            context=None,
            api_key="k",
        )
        assert result["grounding"] == "generative"
        assert result["scope"] == "GENERATIVE"
        assert "toggles" in result["answer"]
        payload = captured["payload"]
        assert "Grounded material" in str(payload)  # system prompt travels with the request
        assert '"kind":"lesson"' in str(payload)

    def test_default_base_url_constant(self) -> None:
        assert DEFAULT_BASE_URL.startswith("https://")
        assert KEY_HEADER == "X-Assistant-Key"


def _inject_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route httpx.Client through a mock transport (the module builds plain Clients)."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    class RoutedClient(real_client):
        def __init__(self, **kwargs: object) -> None:
            kwargs["transport"] = transport
            super().__init__(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "Client", RoutedClient)


def json_loads_safe(raw: bytes | None) -> object:
    import json

    return json.loads(raw.decode() if isinstance(raw, bytes) else "{}")


class TestProviderSecurity:
    def test_http_non_local_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_provider_url("http://169.254.169.254/v1")
        assert exc.value.category == "BAD_PROVIDER"

    def test_credentials_in_url_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_provider_url("https://user:key@api.example.com/v1")
        assert exc.value.category == "BAD_PROVIDER"

    def test_https_remote_accepted(self) -> None:
        assert validate_provider_url("https://api.openai.com/v1").endswith("/v1")

    def test_http_localhost_accepted(self) -> None:
        assert validate_provider_url("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"

    def test_conversation_caps(self) -> None:
        too_many = [{"role": "user", "content": "x"} for _ in range(21)]
        with pytest.raises(AssistantError) as exc:
            validate_conversation(too_many)
        assert exc.value.category == "BAD_CONTEXT"

    def test_role_whitelist(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_conversation([{"role": "system", "content": "evil"}])
        assert exc.value.category == "BAD_CONTEXT"

    def test_long_content_truncated(self) -> None:
        cleaned = validate_conversation([{"role": "user", "content": "a" * 5000}])
        assert len(cleaned[0]["content"]) == 4000

    def test_malformed_key_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            chat(messages=[], question="hi", context=None, api_key="two words")
        assert exc.value.category == "BAD_CONTEXT"
