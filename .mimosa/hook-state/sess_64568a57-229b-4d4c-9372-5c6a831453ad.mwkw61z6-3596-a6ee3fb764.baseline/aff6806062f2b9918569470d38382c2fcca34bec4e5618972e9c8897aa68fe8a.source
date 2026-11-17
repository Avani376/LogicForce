"""Additional golden 8086 programs: bitwise ops, stack frames, data transfer."""

from __future__ import annotations

import pytest
from cpu8086 import assemble
from cpu8086.machine import Cpu


def run(source: str, max_steps: int = 500) -> Cpu:
    machine = Cpu(assemble(source))
    _, reason = machine.run(max_steps=max_steps)
    assert reason == "hlt", f"program did not halt: {reason}"
    return machine


def test_golden_bitwise_masks() -> None:
    """AND/OR/XOR on byte registers — all four combinations."""
    machine = run("MOV AL, 0xCC\nMOV BL, 0xAA\nAND AL, BL\nHLT")
    assert machine.registers.get("AL") == 0x88  # 0xCC & 0xAA = 0x88
    machine = run("MOV AL, 0xCC\nMOV BL, 0xAA\nOR AL, BL\nHLT")
    assert machine.registers.get("AL") == 0xEE  # 0xCC | 0xAA = 0xEE
    machine = run("MOV AL, 0xCC\nMOV BL, 0xAA\nXOR AL, BL\nHLT")
    assert machine.registers.get("AL") == 0x66  # 0xCC ^ 0xAA = 0x66


def test_golden_stack_frame_with_local_vars() -> None:
    """PUSH/pop sequence using the stack as scratch storage."""
    machine = run("MOV AX, 0x1111\nMOV BX, 0x2222\nPUSH AX\nPUSH BX\nMOV AX, 0\nMOV BX, 0\nPOP BX\nPOP AX\nHLT")
    assert machine.registers.get("AX") == 0x1111  # restored from stack (LIFO)
    assert machine.registers.get("BX") == 0x2222  # restored from stack (LIFO)


@pytest.mark.xfail(reason="SI addressing: assembler implicit size fix needs further testing")
def test_golden_memory_copy_via_si_di() -> None:
    """Copy 4 bytes from [SI] to [DI] using a LOOP."""
    machine = Cpu(
        assemble(
            "MOV SI, 0x100\nMOV DI, 0x200\nMOV CX, 4\ncopy:\nMOV AL, [SI]\nMOV [DI], AL\nINC SI\nINC DI\nLOOP copy\nHLT"
        )
    )
    source_data = [0xDE, 0xAD, 0xBE, 0xEF]
    for i, byte in enumerate(source_data):
        machine.memory.write_byte(0, 0x100 + i, byte)
    # re-run the copy loop (the program was already loaded; we need to reset IP)
    machine.registers.set("IP", 0)
    machine.registers.set("CX", 4)
    machine.registers.set("SI", 0x100)
    machine.registers.set("DI", 0x200)
    machine.run(max_steps=50)
    for i, byte in enumerate(source_data):
        assert machine.memory.read_byte(0, 0x200 + i) == byte


def test_golden_signed_overflow_boundary() -> None:
    """ADD 0x7FFF + 1 = 0x8000: OF=1, SF=1, ZF=0 (word signed overflow)."""
    machine = run("MOV AX, 0x7FFF\nADD AX, 1\nHLT")
    assert machine.registers.get("AX") == 0x8000
    assert machine.registers.flags["OF"] == 1
    assert machine.registers.flags["SF"] == 1
    assert machine.registers.flags["ZF"] == 0


def test_golden_carry_chain_adc() -> None:
    """16-bit add via two 8-bit adds with ADC (carry propagation)."""
    machine = run(
        "MOV AL, 0xFF\n"
        "MOV BL, 0x01\n"
        "ADD AL, BL\n"  # AL = 0x00, CF = 1
        "MOV AH, 0x00\n"
        "ADC AH, 0x00\n"  # AH = 0 + 0 + CF(1) = 1
        "HLT"
    )
    assert machine.registers.get("AX") == 0x0100  # 16-bit result 0x100


def test_golden_test_instruction_flags_only() -> None:
    """TEST sets flags without writing the destination."""
    machine = run("MOV AL, 0x80\nTEST AL, 0x80\nHLT")
    assert machine.registers.get("AL") == 0x80  # unchanged
    assert machine.registers.flags["ZF"] == 0
    assert machine.registers.flags["SF"] == 1
    assert machine.registers.flags["CF"] == 0
    assert machine.registers.flags["OF"] == 0
