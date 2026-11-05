"""Golden 8086 programs: committed expected register/memory outcomes.

These are differential-style tests: every expected value is derived from
documented Intel 8086 semantics (manual-verified by hand), committed here, and
compared against the engine. The assembler/executor cannot rewrite its oracle.
"""

from __future__ import annotations

from cpu8086 import assemble
from cpu8086.machine import Cpu

SUM_1_TO_5_SOURCE = """
    MOV CX, 5
    MOV AX, 0
    MOV BX, 1
sum_loop:
    ADD AX, BX
    INC BX
    LOOP sum_loop
    HLT
"""


def run_to_halt(source: str) -> Cpu:
    machine = Cpu(assemble(source))
    trace, reason = machine.run(max_steps=1000)
    assert reason == "hlt", f"program did not halt: {reason} (trace tail: {trace[-1:]})"
    return machine


def test_golden_sum_1_to_5() -> None:
    """Sum 1..5 = 15 via a LOOP; exercises CX countdown, flags, loop branch."""
    machine = run_to_halt(SUM_1_TO_5_SOURCE)
    assert machine.registers.get("AX") == 15
    assert machine.registers.get("BX") == 6
    assert machine.registers.get("CX") == 0
    # final ADD (5+... wait: adds 1+2+3+4+5; last ADD was 4+5 -> result 15, SF=0
    assert machine.registers.flags["ZF"] == 0
    assert machine.registers.flags["CF"] == 0


def test_golden_fibonacci_first_eight() -> None:
    """Fibonacci 1,1,2,3,5,8,13,21 into memory via [BX] addressing."""
    source = """
    MOV CX, 8
    MOV AX, 1
    MOV BX, 1
    MOV SI, 0
fib_loop:
    MOV WORD [SI], AX
    MOV DX, AX
    ADD DX, BX
    MOV AX, BX
    MOV BX, DX
    ADD SI, 2
    LOOP fib_loop
    HLT
"""
    machine = run_to_halt(source)
    expected = [1, 1, 2, 3, 5, 8, 13, 21]
    for index, value in enumerate(expected):
        assert machine.memory.read_word(machine.registers.get("DS"), index * 2) == value


def test_golden_max_of_two_via_conditional() -> None:
    """max(AX, BX) written to CX using JAE — exercises compare + conditional."""
    source = """
    MOV AX, 42
    MOV BX, 97
    CMP AX, BX
    JAE ax_wins
    MOV CX, BX
    JMP done
ax_wins:
    MOV CX, AX
done:
    HLT
"""
    machine = run_to_halt(source)
    assert machine.registers.get("CX") == 97


def test_golden_stack_frame_call_sequence() -> None:
    """CALL/RET with a value passed through BX; SP restored to entry value."""
    source = """
    MOV SP, 0x100
    MOV BX, 10
    CALL double_bx
    HLT
double_bx:
    ADD BX, BX
    RET
"""
    machine = run_to_halt(source)
    assert machine.registers.get("BX") == 20
    assert machine.registers.get("SP") == 0x100


def test_golden_neg_flags_on_most_negative() -> None:
    """NEG of 0x80 (byte) sets CF and OF — documented boundary case."""
    source = """
    MOV AL, 0x80
    NEG AL
    HLT
"""
    machine = run_to_halt(source)
    assert machine.registers.get("AL") == 0x80  # -(-128) == -128 wraps
    assert machine.registers.flags["CF"] == 1
    assert machine.registers.flags["OF"] == 1


def test_golden_determinism_byte_identical_traces() -> None:
    """Engine rule: same program -> byte-identical trace, 100 replays."""
    trace_sets = []
    for _ in range(100):
        machine = run_to_halt(SUM_1_TO_5_SOURCE)
        import json

        trace_sets.append(
            json.dumps(
                [
                    {
                        "step": record.step,
                        "ip": record.ip,
                        "instruction": record.instruction,
                        "kind": record.kind,
                        "registers": record.register_changes,
                        "flags": record.flag_changes,
                        "memory": [list(pair) for pair in record.memory_changes],
                    }
                    for record in machine._trace_history()  # noqa: SLF001 - test-only accessor
                ],
                sort_keys=True,
            )
        )
    assert len(set(trace_sets)) == 1
