"""8086 endpoints: assemble, run (bounded), step (Phase 6d)."""

from __future__ import annotations

from typing import Any

from cpu8086 import AsmError, CpuRuntimeError, UnsupportedInstructionError, assemble
from cpu8086.executor import Cpu, assemble_and_load
from cpu8086.version import CPU8086_ENGINE_VERSION
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/8086", tags=["8086"])


class AssembleRequest(BaseModel):
    source: str


class RunRequest(BaseModel):
    source: str
    max_steps: int = 10_000
    breakpoints: list[int] = Field(default_factory=list)


class StepRequest(BaseModel):
    source: str


def _asm_http_error(exc: AsmError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "code": "ASM_ERROR",
            "line": exc.line,
            "category": exc.category,
            "message": exc.message,
        },
    )


@router.post("/assemble")
def assemble_endpoint(request: AssembleRequest) -> dict[str, Any]:
    try:
        program = assemble(request.source)
    except AsmError as exc:
        raise _asm_http_error(exc) from exc
    return {
        "engine_version": CPU8086_ENGINE_VERSION,
        "instruction_count": len(program.instructions),
        "labels": dict(sorted(program.labels.items())),
    }


@router.post("/run")
def run_endpoint(request: RunRequest) -> dict[str, Any]:
    machine: Cpu
    try:
        machine = assemble_and_load(request.source)
        trace, stop_reason = machine.run(
            max_steps=request.max_steps, breakpoints=tuple(request.breakpoints)
        )
    except UnsupportedInstructionError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_INSTRUCTION", "message": str(exc), "line": exc.line},
        ) from exc
    except CpuRuntimeError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "CPU_RUNTIME_ERROR", "message": str(exc)}
        ) from exc
    except AsmError as exc:
        raise _asm_http_error(exc) from exc
    return {
        "engine_version": CPU8086_ENGINE_VERSION,
        "stop_reason": stop_reason,
        "registers": machine.registers.snapshot(),
        "flags": dict(machine.registers.flags),
        "trace": [
            {
                "step": record.step,
                "ip": record.ip,
                "instruction": record.instruction,
                "register_changes": record.register_changes,
                "flag_changes": record.flag_changes,
                "memory_changes": [list(pair) for pair in record.memory_changes],
                "halted": record.halted,
            }
            for record in trace
        ],
    }


@router.post("/step")
def step_endpoint(request: StepRequest) -> dict[str, Any]:
    machine: Cpu
    try:
        machine = assemble_and_load(request.source)
        record = machine.step()
    except UnsupportedInstructionError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_INSTRUCTION", "message": str(exc), "line": exc.line},
        ) from exc
    except CpuRuntimeError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "CPU_RUNTIME_ERROR", "message": str(exc)}
        ) from exc
    except AsmError as exc:
        raise _asm_http_error(exc) from exc
    return {
        "engine_version": CPU8086_ENGINE_VERSION,
        "record": {
            "step": record.step,
            "ip": record.ip,
            "instruction": record.instruction,
            "register_changes": record.register_changes,
            "flag_changes": record.flag_changes,
            "memory_changes": [list(pair) for pair in record.memory_changes],
            "halted": record.halted,
        },
        "registers": machine.registers.snapshot(),
        "halted": machine.halted,
    }
