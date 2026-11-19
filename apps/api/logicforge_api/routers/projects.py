"""Projects, versions, and run history — persisted engineering state (Phase 7).

Read endpoints are open (design documents are non-sensitive); writes require
the bearer token when LOGICFORGE_AUTH_TOKEN is configured (auth.py).
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from logicforge_api import auth
from logicforge_api.persistence import (
    ProjectRecord,
    add_version,
    delete_project,
    get_project,
    get_version,
    list_projects,
    list_runs_by_hash,
    list_versions,
    save_project,
    save_run,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    document: dict[str, Any]
    kind: str = Field(default="circuit", pattern="^(circuit|fsm|8086)$")
    project_id: str | None = Field(default=None, max_length=100)


class VersionIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    document: dict[str, Any]


def _project_out(record: ProjectRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "kind": record.kind,
        "document": record.document,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.post("")
def create_or_update_project(request: ProjectIn, _auth: None = Depends(auth.require_write_auth)) -> dict[str, Any]:
    project_id = request.project_id or secrets.token_hex(8)
    record = save_project(project_id, request.name, request.document, request.kind)
    return _project_out(record)


@router.get("")
def list_all_projects() -> dict[str, Any]:
    return {"projects": [_project_out(record) for record in list_projects()]}


@router.get("/{project_id}")
def get_one_project(project_id: str) -> dict[str, Any]:
    record = get_project(project_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": f"no project {project_id!r}"}
        )
    return _project_out(record)


@router.delete("/{project_id}")
def delete_one_project(project_id: str, _auth: None = Depends(auth.require_write_auth)) -> dict[str, Any]:
    if not delete_project(project_id):
        raise HTTPException(
            status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": f"no project {project_id!r}"}
        )
    return {"deleted": project_id}


@router.post("/{project_id}/versions")
def add_project_version(
    project_id: str, request: VersionIn, _auth: None = Depends(auth.require_write_auth)
) -> dict[str, Any]:
    if get_project(project_id) is None:
        raise HTTPException(
            status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": f"no project {project_id!r}"}
        )
    version_id = add_version(project_id, request.label, request.document)
    return {"version_id": version_id, "label": request.label}


@router.get("/{project_id}/versions")
def list_project_versions(project_id: str) -> dict[str, Any]:
    if get_project(project_id) is None:
        raise HTTPException(
            status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": f"no project {project_id!r}"}
        )
    return {"versions": list_versions(project_id)}


@router.get("/{project_id}/versions/{version_id}")
def get_project_version(project_id: str, version_id: int) -> dict[str, Any]:
    if get_project(project_id) is None:
        raise HTTPException(
            status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": f"no project {project_id!r}"}
        )
    document = get_version(project_id, version_id)
    if document is None:
        raise HTTPException(
            status_code=404, detail={"code": "VERSION_NOT_FOUND", "message": f"no version {version_id}"}
        )
    return {"project_id": project_id, "version_id": version_id, "document": document}


class RunIn(BaseModel):
    input_hash: str = Field(min_length=16, max_length=64)
    kind: str = Field(pattern="^(simulate|verify|fault_experiment|optimize)$")
    result: dict[str, Any]


runs_router = APIRouter(prefix="/api/runs", tags=["runs"])


@runs_router.post("")
def save_run_endpoint(request: RunIn, _auth: None = Depends(auth.require_write_auth)) -> dict[str, Any]:
    save_run(request.input_hash, request.kind, request.result)
    return {"saved": True, "input_hash": request.input_hash}


@runs_router.get("")
def list_runs_endpoint(hash: str, _auth: None = Depends(auth.require_write_auth)) -> dict[str, Any]:
    return {"runs": list_runs_by_hash(hash)}
