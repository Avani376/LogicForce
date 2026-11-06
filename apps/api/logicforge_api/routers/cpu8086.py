"""8086 endpoints: assemble, run (bounded), step (Phase 6d)."""

from __future__ import annotations

from typing import Any

from cpu8086 import AsmError, CpuRuntimeError, UnsupportedInstructionError, assemble
from cpu8086.interrupts import ScheduledInterrupt
from cpu8086.machine import Cpu, assemble_and_load
from cpu8086.version import CPU8086_ENGINE_VERSION
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/8086", tags=["8086"])


class AssembleRequest(BaseModel):
    source: str


class ScheduledInterruptIn(BaseModel):
    source: str
    at_step: int
    number: int


class RunRequest(BaseModel):
    source: str
    max_steps: int = 10_000
    breakpoints: list[int] = Field(default_factory=list)
    interrupts: dict[int, str] = Field(default_factory=dict)
    schedule: list[ScheduledInterruptIn] = Field(default_factory=list)


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
        schedule = [ScheduledInterrupt(source=s.source, at_step=s.at_step, number=s.number) for s in request.schedule]
        machine = assemble_and_load(request.source, request.interrupts, schedule)
        trace, stop_reason = machine.run(max_steps=request.max_steps, breakpoints=tuple(request.breakpoints))
    except UnsupportedInstructionError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_INSTRUCTION", "message": str(exc), "line": exc.line},
        ) from exc
    except CpuRuntimeError as exc:
        raise HTTPException(status_code=400, detail={"code": "CPU_RUNTIME_ERROR", "message": str(exc)}) from exc
    except AsmError as exc:
        raise _asm_http_error(exc) from exc
    return {
        "engine_version": CPU8086_ENGINE_VERSION,
        "stop_reason": stop_reason,
        "registers": machine.registers.snapshot(),
        "flags": dict(machine.registers.flags),
        "trace": [
            {
                "kind": record.kind,
                "number": record.number,
                "source": record.source,
                "handler": record.handler,
                "resumed_at": record.resumed_at,
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
        raise HTTPException(status_code=400, detail={"code": "CPU_RUNTIME_ERROR", "message": str(exc)}) from exc
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


# ---------------------------------------------------------------- Phase C7: 8259 PIC


class PicEventIn(BaseModel):
    at_step: int
    op: str
    line: int = 0
    masked: bool = False


class PicProgramIn(BaseModel):
    source: str
    max_steps: int = Field(default=10_000, ge=1, le=200_000)
    interrupts: dict[int, str] = Field(default_factory=dict)


class PicRunRequest(BaseModel):
    base_vector: int = 8
    aeoi: bool = False
    single: bool = True
    events: list[PicEventIn] = Field(default_factory=list)
    program: PicProgramIn | None = None


@router.post("/pic")
def pic_endpoint(request: PicRunRequest) -> dict[str, Any]:
    """Resolve a scheduled 8259 PIC flow; optionally run the derived schedule
    through the 8086 pipeline (interrupts.md IF gating applies on top)."""
    from pic8259 import PicConfig, PicError, PicEvent, resolve_pic_flow

    try:
        config = PicConfig(base_vector=request.base_vector, aeoi=request.aeoi, single=request.single)
        events = [PicEvent(at_step=e.at_step, op=e.op, line=e.line, masked=e.masked) for e in request.events]
        result = resolve_pic_flow(config, events)
    except PicError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "PIC_ERROR", "category": exc.category, "message": exc.message},
        ) from exc

    response: dict[str, Any] = {
        "pic_engine_version": result.engine_version,
        "deliveries": [{"at_step": d.at_step, "line": d.line, "vector": d.vector} for d in result.deliveries],
        "pic_trace": [e.to_json() for e in result.trace],
        "final_registers": {"IRR": result.final_irr, "ISR": result.final_isr, "IMR": result.final_imr},
        "scope": result.scope,
    }

    if request.program is None:
        return response

    try:
        schedule = [ScheduledInterrupt(source="intr", number=d.vector, at_step=d.at_step) for d in result.deliveries]
        machine = assemble_and_load(request.program.source, request.program.interrupts, schedule)
        trace, stop_reason = machine.run(max_steps=request.program.max_steps)
    except UnsupportedInstructionError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_INSTRUCTION", "message": str(exc), "line": exc.line},
        ) from exc
    except CpuRuntimeError as exc:
        raise HTTPException(status_code=400, detail={"code": "CPU_RUNTIME_ERROR", "message": str(exc)}) from exc
    except AsmError as exc:
        raise _asm_http_error(exc) from exc

    response["cpu_engine_version"] = CPU8086_ENGINE_VERSION
    response["stop_reason"] = stop_reason
    response["registers"] = machine.registers.snapshot()
    response["cpu_trace"] = [
        {
            "kind": record.kind,
            "number": record.number,
            "source": record.source,
            "step": record.step,
            "ip": record.ip,
            "resumed_at": record.resumed_at,
            "instruction": record.instruction,
        }
        for record in trace
    ]
    return response
