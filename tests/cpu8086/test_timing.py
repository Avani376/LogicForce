"""Phase C6 tests: timing model, addressing modes, expanded instruction set."""

from __future__ import annotations

from cpu8086.machine import assemble_and_load
from cpu8086.timing import get_timing


class TestTimingModel:
    def test_mov_timing(self) -> None:
        t = get_timing("MOV")
        assert t.base_cycles == 2

    def test_mul_timing(self) -> None:
        t = get_timing("MUL")
        assert t.base_cycles == 70

    def test_ea_penalty(self) -> None:
        t = get_timing("ADD", has_memory_operand=True, ea_mode="based_indexed")
        assert t.ea_cycles == 11
        assert t.total_cycles == 14

    def test_unknown_mnemonic_zero(self) -> None:
        t = get_timing("UNKNOWN")
        assert t.base_cycles == 0


class TestExpandedInstructions:
    def test_xchg(self) -> None:
        machine = assemble_and_load("MOV AX, 1\nMOV BX, 2\nXCHG AX, BX\nHLT")
        machine.run()
        assert machine.registers.get("AX") == 2
        assert machine.registers.get("BX") == 1

    def test_shl(self) -> None:
        machine = assemble_and_load("MOV AL, 3\nSHL AL, 1\nHLT")
        machine.run()
        assert machine.registers.get("AL") == 6

    def test_shr(self) -> None:
        machine = assemble_and_load("MOV AL, 8\nSHR AL, 1\nHLT")
        machine.run()
        assert machine.registers.get("AL") == 4


class TestAddressingModes:
    def test_direct_addressing(self) -> None:
        machine = assemble_and_load("MOV WORD [0x300], 0xAB\nMOV AX, WORD [0x300]\nHLT")
        machine.run()
        assert machine.registers.get("AX") == 0xAB

    def test_based_addressing_bx(self) -> None:
        machine = assemble_and_load("MOV BX, 0x100\nMOV WORD [BX], 0xCD\nMOV AX, WORD [BX]\nHLT")
        machine.run()
        assert machine.registers.get("AX") == 0xCD

    def test_based_indexed_disp(self) -> None:
        machine = assemble_and_load(
            "MOV BX, 0x100\nMOV SI, 0x10\nMOV WORD [BX+SI+4], 0xEF\nMOV AX, WORD [BX+SI+4]\nHLT"
        )
        machine.run()
        assert machine.registers.get("AX") == 0xEF
