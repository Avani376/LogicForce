"""Phase 7 persistence tests: projects, versions, run history, auth gates."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from logicforge_api import persistence
from logicforge_api.persistence import (
    add_version,
    get_project,
    get_version,
    list_versions,
    save_project,
)


def _reset_db() -> None:
    persistence.reset_for_tests(":memory:")


class TestPersistenceLayer:
    def test_project_upsert_and_round_trip(self) -> None:
        _reset_db()
        save_project("p1", "Half Adder", {"schema_version": 1, "components": []})
        save_project("p1", "Half Adder v2", {"schema_version": 1, "components": [{"id": "G1"}]})
        record = get_project("p1")
        assert record is not None
        assert record.name == "Half Adder v2"
        assert record.document["components"] == [{"id": "G1"}]
        assert record.created_at <= record.updated_at

    def test_versions_are_immutable_snapshots(self) -> None:
        _reset_db()
        save_project("p2", "Counter", {"components": []})
        add_version("p2", "v1", {"components": [{"id": "old"}]})
        add_version("p2", "v2", {"components": [{"id": "new"}]})
        versions = list_versions("p2")
        assert [v["label"] for v in versions] == ["v2", "v1"]  # newest first
        doc = get_version("p2", versions[1]["id"])
        assert doc == {"components": [{"id": "old"}]}  # v1 unchanged by v2

    def test_missing_project_and_version_are_none(self) -> None:
        _reset_db()
        assert get_project("nope") is None
        assert get_version("nope", 1) is None

    def test_runs_keyed_by_hash(self) -> None:
        _reset_db()
        persistence.save_run("hash-aaa", "simulate", {"event_count": 1})
        persistence.save_run("hash-bbb", "verify", {"verdict": "PASS"})
        assert len(persistence.list_runs_by_hash("hash-aaa")) == 1
        assert len(persistence.list_runs_by_hash("hash-bbb")) == 1
        assert persistence.list_runs_by_hash("hash-ccc") == []


class TestProjectsApi:
    def test_save_list_load_delete_round_trip(self) -> None:
        _reset_db()
        from logicforge_api.main import app

        client = TestClient(app)
        saved = client.post(
            "/api/projects",
            json={"project_id": "demo1", "name": "Demo", "document": {"schema_version": 1}},
        )
        assert saved.status_code == 200
        listing = client.get("/api/projects").json()
        assert [p["id"] for p in listing["projects"]] == ["demo1"]
        loaded = client.get("/api/projects/demo1")
        assert loaded.status_code == 200
        assert loaded.json()["document"]["schema_version"] == 1
        assert client.delete("/api/projects/demo1").status_code == 200
        assert client.get("/api/projects/demo1").status_code == 404

    def test_version_endpoints(self) -> None:
        _reset_db()
        from logicforge_api.main import app

        client = TestClient(app)
        client.post("/api/projects", json={"project_id": "ver1", "name": "V", "document": {"a": 1}})
        added = client.post("/api/projects/ver1/versions", json={"label": "snap", "document": {"a": 2}})
        assert added.status_code == 200
        versions = client.get("/api/projects/ver1/versions").json()["versions"]
        assert len(versions) == 1
        doc = client.get("/api/projects/ver1/versions/1").json()
        assert doc["document"] == {"a": 2}

    def test_404s_are_structured(self) -> None:
        _reset_db()
        from logicforge_api.main import app

        client = TestClient(app)
        response = client.get("/api/projects/ghost")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "PROJECT_NOT_FOUND"

    def test_auth_required_when_token_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_db()
        monkeypatch.setenv("LOGICFORGE_AUTH_TOKEN", "team-token")
        from logicforge_api.main import app

        client = TestClient(app)
        payload = {"project_id": "sec1", "name": "Sec", "document": {}}
        # no token → 401
        assert client.post("/api/projects", json=payload).status_code == 401
        # wrong token → 401
        denied = client.post("/api/projects", json=payload, headers={"Authorization": "Bearer wrong"})
        assert denied.status_code == 401
        # correct token → allowed
        ok = client.post("/api/projects", json=payload, headers={"Authorization": "Bearer team-token"})
        assert ok.status_code == 200
        # reads stay open (design documents are non-sensitive)
        assert client.get("/api/projects").status_code == 200

    def test_auth_off_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_db()
        monkeypatch.delenv("LOGICFORGE_AUTH_TOKEN", raising=False)
        from logicforge_api.main import app

        client = TestClient(app)
        response = client.post("/api/projects", json={"project_id": "local1", "name": "Local", "document": {}})
        assert response.status_code == 200  # single-user local mode
