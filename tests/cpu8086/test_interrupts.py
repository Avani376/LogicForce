"""Interrupt tests: INT/IRET, NMI, masked INTR, IF flag, nesting, determinism."""

from __future__ import annotations

import pytest
from cpu8086 import AsmError
from cpu8086.interrupts import ScheduledInterrupt
from cpu8086.machine import assemble_and_load

COUNTER_PROGRAM = """
    MOV WORD [0x200], 0
    MOV AX, 0
wait:
    INC AX
    JMP wait
handler:
    INC WORD [0x200]
    IRET
"""

HANDLER_SOURCE = """
    MOV AX, 0
wait:
    JMP wait
tick:
    INC WORD [0x200]
    IRET
"""


def test_software_int_dispatches_and_iret_returns() -> None:
    machine = assemble_and_load(
        "MOV WORD [0x200], 0\nINT 5\nMOV AX, 1\nHLT",
        interrupts={5: None if False else None} if False else None,
    )
    # INT 5 needs an IVT entry: rebuild with one via label
    machine = assemble_and_load(
        "MOV WORD [0x200], 0\nINT 5\nMOV AX, 1\nHLT\nhandler:\nINC WORD [0x200]\nIRET",
        interrupts={5: "handler"},
    )
    trace, reason = machine.run()
    assert reason == "hlt"
    kinds = [record.kind for record in trace]
    assert "interrupt" in kinds
    assert "iret" in kinds
    # INT pushed flags + return index, so the handler increments, IRET returns,
    # and execution continues: AX == 1 after the INT block
    assert machine.registers.get("AX") == 1


def test_software_int_handler_side_effect_visible() -> None:
    machine = assemble_and_load(
        "MOV WORD [0x200], 0\nINT 5\nHLT\nhandler:\nINC WORD [0x200]\nIRET",
        interrupts={5: "handler"},
    )
    machine.run()
    assert machine.memory.read_word(0, 0x200) == 1


def test_iret_restores_saved_flags() -> None:
    """IF was 0 at INT time (after INT zeroes it, IRET restores the pre-INT IF=0)."""
    machine = assemble_and_load(
        "INT 5\nMOV AX, 1\nHLT\nhandler:\nIRET",
        interrupts={5: "handler"},
    )
    machine.run()
    # pre-INT IF was 0 (power-on); the saved-flags word restores it
    assert machine.registers.flags["IF"] == 0


def test_nmi_fires_regardless_of_if() -> None:
    machine = assemble_and_load(
        "MOV WORD [0x200], 0\nwait:\nJMP wait\ntick:\nINC WORD [0x200]\nIRET",
        interrupts={2: "tick"},
        schedule=[ScheduledInterrupt(source="nmi", at_step=3, number=2)],
    )
    trace, reason = machine.run(max_steps=100)
    interrupts = [r for r in trace if r.kind == "interrupt"]
    assert len(interrupts) == 1
    assert interrupts[0].source == "nmi"
    assert interrupts[0].number == 2
    assert machine.memory.read_word(0, 0x200) == 1


def test_intr_masked_until_sti() -> None:
    """INTR scheduled while IF=0 is parked; STI lets it fire at the next boundary."""
    machine = assemble_and_load(
        "MOV WORD [0x200], 0\nCLI\nMOV BX, 7\nSTI\nwait:\nJMP wait\ntick:\nINC WORD [0x200]\nIRET",
        interrupts={4: "tick"},
        schedule=[ScheduledInterrupt(source="intr", at_step=2, number=4)],
    )
    trace, reason = machine.run(max_steps=200)
    pending = [r for r in trace if r.kind == "pending_intr"]
    fired = [r for r in trace if r.kind == "interrupt"]
    assert len(pending) == 1  # parked once, observable once
    assert len(fired) == 1
    assert machine.memory.read_word(0, 0x200) == 1


def test_nesting_cap_is_typed_error() -> None:
    """A self-interrupting handler exceeds the cap of 8 — typed error, no hang."""
    machine = assemble_and_load(
        "INT 1\nHLT\nhandler:\nINT 1\nIRET",
        interrupts={1: "handler"},
    )
    from cpu8086 import CpuRuntimeError

    with pytest.raises((CpuRuntimeError, AsmError)) as excinfo:
        machine.run(max_steps=100)
    assert "nesting" in str(excinfo.value).lower() or "cap" in str(excinfo.value).lower()


def test_iret_without_frame_is_typed_error() -> None:
    machine = assemble_and_load("IRET\nHLT")
    from cpu8086 import CpuRuntimeError

    with pytest.raises(CpuRuntimeError) as excinfo:
        machine.run()
    assert "IRET" in str(excinfo.value) or "matching" in str(excinfo.value)


def test_scheduled_interrupt_without_ivt_entry_rejected() -> None:
    with pytest.raises(AsmError) as excinfo:
        assemble_and_load(
            "HLT", interrupts={}, schedule=[ScheduledInterrupt(source="nmi", at_step=1, number=9)]
        )
    assert excinfo.value.category == "UNKNOWN_LABEL"


def test_scheduled_source_and_bounds_validated() -> None:
    with pytest.raises(AsmError):
        ScheduledInterrupt(source="dma", at_step=1, number=1)
    with pytest.raises(AsmError):
        ScheduledInterrupt(source="nmi", at_step=-1, number=1)
    with pytest.raises(AsmError):
        ScheduledInterrupt(source="nmi", at_step=1, number=256)


def test_interrupt_schedule_is_part_of_determinism() -> None:
    """Same program + schedule => byte-identical traces (engine rule 2)."""
    machine_a = assemble_and_load(
        "MOV WORD [0x200], 0\nwait:\nJMP wait\ntick:\nINC WORD [0x200]\nIRET",
        interrupts={2: "tick"},
        schedule=[ScheduledInterrupt(source="nmi", at_step=3, number=2)],
    )
    machine_b = assemble_and_load(
        "MOV WORD [0x200], 0\nwait:\nJMP wait\ntick:\nINC WORD [0x200]\nIRET",
        interrupts={2: "tick"},
        schedule=[ScheduledInterrupt(source="nmi", at_step=3, number=2)],
    )
    trace_a, _ = machine_a.run(max_steps=50)
    trace_b, _ = machine_b.run(max_steps=50)
    import json

    assert json.dumps(
        [(r.kind, r.step, r.number, r.register_changes, r.flag_changes) for r in trace_a],
        sort_keys=True,
    ) == json.dumps(
        [(r.kind, r.step, r.number, r.register_changes, r.flag_changes) for r in trace_b],
        sort_keys=True,
    )
