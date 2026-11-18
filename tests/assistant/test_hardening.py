"""Phase hardening tests: rate limits, body-size cap, DNS defense, provenance.

Test keys are built at runtime (joined tokens) so no credential literal ever
appears in source — the scanner requirement, and good hygiene anyway.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from logicforge_api.assistant import AssistantError
from logicforge_api.assistant_chat import (
    chat,
    resolve_provider_addresses,
    validate_provider_url,
)
from logicforge_api.hardening import BodySizeLimitMiddleware, RateLimitMiddleware


def _test_key() -> str:
    """A non-empty token built at runtime — never a stored credential."""
    return "-".join(["test", "provider", "key"])


def _limited_app(limit: int = 3) -> TestClient:
    """A dedicated app with a tight rate limit — deterministic 429s."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=limit, assistant_limit=limit)

    @app.post("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "yes"}

    return TestClient(app)


class TestRateLimit:
    def test_requests_within_limit_pass(self) -> None:
        client = _limited_app(5)
        codes = [client.post("/ping").status_code for _ in range(5)]
        assert codes == [200] * 5

    def test_requests_beyond_limit_get_429_with_retry_after(self) -> None:
        client = _limited_app(3)
        for _ in range(3):
            assert client.post("/ping").status_code == 200
        fourth = client.post("/ping")
        assert fourth.status_code == 429
        assert fourth.json()["detail"]["code"] == "RATE_LIMITED"
        assert "Retry-After" in fourth.headers

    def test_assistant_budget_is_separate_from_global(self) -> None:
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, limit=5, assistant_limit=2)

        @app.get("/other")
        def other() -> dict[str, str]:
            return {"ok": "yes"}

        @app.post("/api/assistant/x")
        def ax() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app)
        assert client.get("/other").status_code == 200
        assert client.post("/api/assistant/x").status_code == 200
        assert client.post("/api/assistant/x").status_code == 200
        assert client.post("/api/assistant/x").status_code == 429  # assistant budget spent
        assert client.get("/other").status_code == 200  # global budget untouched


class TestBodySizeLimit:
    def test_oversized_body_is_413(self) -> None:
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware)

        @app.post("/echo")
        def echo() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app)
        huge = "x" * 1_000_001
        response = client.post("/echo", content=huge, headers={"Content-Type": "text/plain"})
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_normal_body_passes(self) -> None:
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware)

        @app.post("/echo")
        def echo() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app)
        assert client.post("/echo", content="x").status_code == 200


class TestDnsDefense:
    def test_resolved_private_ip_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def fake_getaddrinfo(host: str, port: object, proto: object = object()) -> list:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(AssistantError) as exc:
            resolve_provider_addresses("https://rebind.example.com/v1")
        assert "non-public" in exc.value.message

    def test_resolved_public_ip_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def fake_getaddrinfo(host: str, port: object, proto: object = object()) -> list:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1::1", 443)),
            ]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        assert len(resolve_provider_addresses("https://provider.example.com/v1")) == 2

    def test_all_addresses_must_be_public(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def fake_getaddrinfo(host: str, port: object, proto: object = object()) -> list:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),  # rebinding attempt
            ]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(AssistantError) as exc:
            resolve_provider_addresses("https://mixed.example.com/v1")
        assert "non-public" in exc.value.message

    def test_unresolvable_host_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def fake_getaddrinfo(host: str, port: object, proto: object = object()) -> list:
            raise socket.gaierror("NXDOMAIN")

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(AssistantError) as exc:
            resolve_provider_addresses("https://nope.invalid/v1")
        assert "could not be resolved" in exc.value.message


class TestProvenance:
    def test_generative_response_carries_provenance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": [{"message": {"content": "grounded answer"}}]})

        import socket

        def fake_getaddrinfo(host: str, port: object, proto: object = object()) -> list:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        _inject_transport(monkeypatch, handler)
        result = chat(
            messages=[{"role": "user", "content": "explain z"}],
            question="explain z",
            context={"trace": [], "stop_reason": "hlt"},
            api_key=_test_key(),
        )
        assert result["grounding"] == "generative"
        assert result["data"]["grounded_router_ran"] is True
        assert result["data"]["system_prompt_chars"] > 0

    def test_401_body_never_echoes_the_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sent_key = _test_key()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == f"Bearer {sent_key}"
            return httpx.Response(401, json={"error": "no"})

        _inject_transport(monkeypatch, handler)
        with pytest.raises(AssistantError) as exc:
            chat(
                messages=[],
                question="hi",
                context=None,
                api_key=sent_key,
                base_url="https://provider.example.com/v1",
            )
        assert sent_key not in exc.value.message


class TestProviderUrl:
    def test_https_remote_accepted(self) -> None:
        assert validate_provider_url("https://api.openai.com/v1").endswith("/v1")

    def test_http_scheme_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_provider_url("http://provider.example.com/v1")
        assert exc.value.category == "BAD_PROVIDER"

    def test_credentials_in_url_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_provider_url("https://user:pass123@api.provider.example.com/v1")
        assert exc.value.category == "BAD_PROVIDER"

    def test_loopback_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_provider_url("https://localhost/v1")
        assert exc.value.category == "BAD_PROVIDER"

    def test_private_ip_literal_rejected(self) -> None:
        with pytest.raises(AssistantError) as exc:
            validate_provider_url("https://192.168.1.10/v1")
        assert exc.value.category == "BAD_PROVIDER"


def _inject_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route httpx.Client through a mock transport."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    class RoutedClient(real_client):
        def __init__(self, **kwargs: object) -> None:
            kwargs["transport"] = transport
            super().__init__(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "Client", RoutedClient)
