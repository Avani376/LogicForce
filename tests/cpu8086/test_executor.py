"""Executor tests: step/run semantics, flags, memory, breakpoints, bounded runs."""

from __future__ import annotations

from cpu8086.executor import assemble_and_load
from cpu8086.memory import physical


def test_mov_immediate_and_register_to_register() -> None:
    machine = assemble_and_load("MOV AX, 0x1234\nMOV BX, AX\nHLT")
    trace = []
    for _ in range(3):
        trace.append(machine.step())
    assert machine.registers.get("AX") == 0x1234
    assert machine.registers.get("BX") == 0x1234
    assert trace[0].register_changes["AX"] == 0x1234
    assert trace[1].register_changes["BX"] == 0x1234
    assert trace[2].halted is True


def test_add_sets_documented_flags() -> None:
    machine = assemble_and_load("MOV AL, 0x7F\nADD AL, 1\nHLT")
    machine.run()
    assert machine.registers.get("AL") == 0x80
    assert machine.registers.flags["OF"] == 1
    assert machine.registers.flags["SF"] == 1
    assert machine.registers.flags["AF"] == 1
    assert machine.registers.flags["CF"] == 0
    assert machine.registers.flags["ZF"] == 0


def test_add_carries_into_adc() -> None:
    machine = assemble_and_load("MOV AL, 0xFF\nADD AL, 1\nMOV AH, 0\nADC AH, 1\nHLT")
    machine.run()
    assert machine.registers.get("AL") == 0x00  # wrapped, CF set
    assert machine.registers.get("AH") == 0x02  # 0 + 1 + CF(1)
    assert machine.registers.flags["CF"] == 0


def test_sub_and_cmp_flags_only() -> None:
    machine = assemble_and_load("MOV AL, 5\nCMP AL, 3\nHLT")
    machine.run()
    assert machine.registers.get("AL") == 5  # CMP does not write
    assert machine.registers.flags["CF"] == 0  # 5 - 3: no borrow
    machine2 = assemble_and_load("MOV AL, 3\nCMP AL, 5\nHLT")
    machine2.run()
    assert machine2.registers.flags["CF"] == 1  # 3 - 5: borrow


def test_inc_leaves_cf_unchanged() -> None:
    """CF set by SUB must survive a later INC at wrap (INC never touches CF)."""
    machine = assemble_and_load("SUB AX, 1\nMOV AX, 0xFF\nINC AL\nHLT")
    machine.run()
    assert machine.registers.get("AL") == 0x00
    assert machine.registers.flags["ZF"] == 1
    assert machine.registers.flags["CF"] == 1


def test_neg_sets_cf_for_nonzero() -> None:
    machine = assemble_and_load("MOV AL, 5\nNEG AL\nHLT")
    machine.run()
    assert machine.registers.get("AL") == 0xFB  # -5 & 0xFF
    assert machine.registers.flags["CF"] == 1


def test_memory_write_and_read_back_word() -> None:
    machine = assemble_and_load("MOV WORD [BX], 0xBEEF\nMOV AX, WORD [BX]\nHLT")
    machine.run()
    assert machine.registers.get("AX") == 0xBEEF
    assert machine.memory.read_word(machine.registers.get("DS"), 0) == 0xBEEF


def test_bp_based_addressing_uses_ss() -> None:
    machine = assemble_and_load("MOV WORD [BP], 0x1234\nMOV AX, WORD [BP]\nHLT")
    machine.run()
    assert machine.memory.read_word(machine.registers.get("SS"), 0) == 0x1234


def test_displacement_addressing() -> None:
    machine = assemble_and_load("MOV WORD [BX+4], 0x11\nMOV AX, WORD [BX+4]\nHLT")
    machine.run()
    assert machine.memory.read_word(machine.registers.get("DS"), 4) == 0x11


def test_stack_push_pop() -> None:
    machine = assemble_and_load("MOV AX, 0xAAAA\nPUSH AX\nMOV AX, 0\nPOP BX\nHLT")
    machine.run()
    assert machine.registers.get("BX") == 0xAAAA
    # SP returned to its pre-push value
    assert machine.registers.get("SP") == machine.registers.snapshot()["SP"]


def test_loop_counts_down() -> None:
    machine = assemble_and_load("MOV CX, 3\nMOV AX, 0\ntop:\nINC AX\nLOOP top\nHLT")
    trace, reason = machine.run()
    assert reason == "hlt"
    assert machine.registers.get("AX") == 3
    assert machine.registers.get("CX") == 0
    assert len(trace) == 3 + 3 + 2 + 1  # MOV CX, MOV AX, 3x(INC+LOOP), HLT


def test_conditional_jumps_zero_and_not_zero() -> None:
    machine = assemble_and_load("MOV AX, 1\ntop:\nDEC AX\nJNZ top\nHLT")
    machine.run()
    assert machine.registers.get("AX") == 0


def test_call_ret_roundtrip() -> None:
    machine = assemble_and_load("CALL setup\nJMP done\nsetup:\nMOV AX, 0x77\nRET\ndone:\nHLT")
    trace, reason = machine.run()
    assert reason == "hlt"
    assert machine.registers.get("AX") == 0x77


def test_jc_taken_on_borrow() -> None:
    machine = assemble_and_load("MOV AX, 1\nSUB AX, 2\nJC taken\nMOV BX, 1\ntaken:\nMOV CX, 1\nHLT")
    machine.run()
    # JC taken: the MOV BX, 1 is skipped
    assert machine.registers.get("BX") == 0
    assert machine.registers.get("CX") == 1


def test_hlt_stops_and_step_after_hlt_raises() -> None:
    machine = assemble_and_load("HLT\nMOV AX, 1")
    machine.run()
    assert machine.halted
    import pytest
    from cpu8086 import CpuRuntimeError

    with pytest.raises(CpuRuntimeError):
        machine.step()


def test_breakpoint_stops_before_executing_target() -> None:
    machine = assemble_and_load("MOV AX, 1\nMOV BX, 2\nMOV CX, 3\nHLT")
    trace, reason = machine.run(max_steps=100, breakpoints=(1,))
    assert reason == "breakpoint"
    assert machine.registers.get("AX") == 1
    assert machine.registers.get("BX") == 0  # not yet executed


def test_bounded_run_reports_max_steps() -> None:
    machine = assemble_and_load("top:\nJMP top")
    trace, reason = machine.run(max_steps=10)
    assert reason == "max_steps"
    assert len(trace) == 10


def test_logical_ops_clear_af_deviation_documented() -> None:
    machine = assemble_and_load("MOV AL, 0xFF\nAND AL, 0xFF\nHLT")
    machine.run()
    flags = machine.registers.flags
    assert flags["CF"] == 0
    assert flags["OF"] == 0
    assert flags["AF"] == 0  # documented deviation: Intel leaves AF undefined


def test_word_wraparound_at_segment_boundary() -> None:
    """A word at 0xFFFF spans into the next physical byte: 0x10000, addressable
    as segment 0x1000, offset 0 (0x1000*16 == 0x10000)."""
    from cpu8086.memory import Memory

    memory = Memory()
    memory.write_word(0x0000, 0xFFFF, 0xBEEF)
    assert memory.read_byte(0x0000, 0xFFFF) == 0xEF
    assert memory.read_byte(0x1000, 0x0000) == 0xBE


def test_physical_address_formula() -> None:
    assert physical(0x1234, 0x5678) == 0x179B8  # 0x1234*16 + 0x5678
    assert physical(0x1000, 0x0000) == 0x10000  # segment 0x1000 page zero
    # A20-style wrap: (0xFFFF*16 + 0xFFFF) mod 0x100000 == 0xFFEF (contract rule)
    assert physical(0xFFFF, 0xFFFF) == 0xFFEF
    assert physical(0xFFFF, 0xFFFF + 5) == 0xFFF4


def test_trace_records_register_and_flag_changes() -> None:
    machine = assemble_and_load("MOV AL, 0x7F\nADD AL, 1\nHLT")
    trace, reason = machine.run()
    assert reason == "hlt"
    assert trace[0].register_changes == {"AX": 0x7F, "IP": 1}
    assert trace[1].flag_changes["OF"] == 1
    assert trace[1].flag_changes["SF"] == 1


def test_trace_memory_changes_recorded() -> None:
    machine = assemble_and_load("MOV BYTE [SI], 0xAB\nHLT")
    trace, _ = machine.run()
    assert trace[0].memory_changes == ((physical(0, 0), 0xAB),)
