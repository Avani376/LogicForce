"""Phase C7 integration: PIC-derived schedules run through the real 8086 pipeline.

The PIC resolves line requests to vector deliveries; each delivery becomes a
``cpu8086.ScheduledInterrupt`` — the CPU's own IF gating, IVT dispatch, and
IRET stack semantics apply unchanged on top.
"""

from __future__ import annotations

from cpu8086.interrupts import ScheduledInterrupt
from cpu8086.machine import assemble_and_load
from pic8259 import PicConfig, PicEvent, resolve_pic_flow

PIC_PROGRAM = """
    STI
    MOV CX, 0
wait:
    INC CX
    CMP CX, 50
    JNZ wait
    HLT
isr:
    INC DX
    IRET
""".strip()


def _pic_schedule(base_vector: int, events: list[PicEvent]) -> list[ScheduledInterrupt]:
    result = resolve_pic_flow(PicConfig(base_vector=base_vector), events)
    return [ScheduledInterrupt(source="intr", number=d.vector, at_step=d.at_step) for d in result.deliveries]


class TestPicToCpu:
    def test_single_interrupt_full_lifecycle(self) -> None:
        schedule = _pic_schedule(8, [PicEvent(3, "request", line=2), PicEvent(20, "eoi")])
        assert [(s.number, s.at_step) for s in schedule] == [(10, 3)]
        machine = assemble_and_load(PIC_PROGRAM, interrupts={10: "isr"}, schedule=schedule)
        trace, stop_reason = machine.run(max_steps=200)
        assert stop_reason == "hlt"
        kinds = [r.kind for r in trace]
        assert "interrupt" in kinds and "iret" in kinds
        fired = [r for r in trace if r.kind == "interrupt"]
        assert fired[0].number == 10
        assert fired[0].source == "intr"
        # Boundary semantics: request at_step=3 fires between instructions 3 and
        # 4; the interrupt record counts it as the 4th executed "slot".
        assert fired[0].step == 4
        resumed = [r for r in trace if r.kind == "iret"]
        assert len(resumed) == 1
        assert resumed[0].resumed_at == 3  # main flow continues where it left off
        # The handler incremented DX exactly once.
        assert machine.registers.get("DX") == 1

    def test_pic_priority_order_reaches_cpu(self) -> None:
        # IR5 then IR1 at the same boundary: PIC delivers IR5 at 2, IR1 at 3 —
        # the CPU trace must fire in exactly that order.
        schedule = _pic_schedule(
            8,
            [PicEvent(2, "request", line=5), PicEvent(2, "request", line=1), PicEvent(30, "eoi")],
        )
        assert [(s.number, s.at_step) for s in schedule] == [(13, 2), (9, 3)]
        program = PIC_PROGRAM + "\nisr13:\n    IRET\nisr9:\n    IRET"
        machine = assemble_and_load(program, interrupts={13: "isr13", 9: "isr9"}, schedule=schedule)
        trace, stop_reason = machine.run(max_steps=300)
        assert stop_reason == "hlt"
        fired = [(r.step, r.number) for r in trace if r.kind == "interrupt"]
        # Vector 9 arrives while the vector-13 handler runs (IF=0) — the CPU
        # parks it (pending_intr) and fires it right after the handler's IRET.
        assert fired == [(3, 13), (6, 9)]
        parked = [r for r in trace if r.kind == "pending_intr"]
        assert [r.number for r in parked] == [9]

    def test_masked_line_fires_only_after_unmask(self) -> None:
        # IR4 (vector 20) requested at 3 while masked — the PIC delivers nothing
        # until OCW1 unmasks at boundary 10; the CPU then fires vector 20.
        schedule = _pic_schedule(
            16,
            [
                PicEvent(1, "mask", line=4, masked=True),
                PicEvent(3, "request", line=4),
                PicEvent(10, "mask", line=4, masked=False),
            ],
        )
        assert [(s.number, s.at_step) for s in schedule] == [(20, 10)]
        machine = assemble_and_load(PIC_PROGRAM, interrupts={20: "isr"}, schedule=schedule)
        trace, stop_reason = machine.run(max_steps=300)
        assert stop_reason == "hlt"
        fired = [(r.step, r.number) for r in trace if r.kind == "interrupt"]
        assert fired == [(11, 20)]
        assert machine.registers.get("DX") == 1

    def test_if_zero_parks_vector_until_run_ends(self) -> None:
        # No STI — IF stays 0 for the whole run: the PIC delivered at boundary 1,
        # but the CPU parks the INTR and it never fires.
        schedule = _pic_schedule(8, [PicEvent(1, "request", line=0)])
        program = """
            MOV CX, 0
wait:
            INC CX
            CMP CX, 5
            JNZ wait
            HLT
isr:
            IRET
""".strip()
        machine = assemble_and_load(program, interrupts={8: "isr"}, schedule=schedule)
        trace, stop_reason = machine.run(max_steps=50)
        assert stop_reason == "hlt"
        assert not [r for r in trace if r.kind == "interrupt"]

    def test_determinism_replay(self) -> None:
        schedule = _pic_schedule(8, [PicEvent(3, "request", line=2), PicEvent(20, "eoi")])
        runs: list[list[tuple]] = []
        for _ in range(3):
            machine = assemble_and_load(PIC_PROGRAM, interrupts={10: "isr"}, schedule=schedule)
            trace, _ = machine.run(max_steps=200)
            runs.append([(r.kind, r.step, getattr(r, "number", None)) for r in trace])
        assert runs[0] == runs[1] == runs[2]
