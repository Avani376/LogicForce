"""Phase C8 tests: MUL/IMUL/DIV/IDIV — operand forms, flag policy, typed errors."""

from __future__ import annotations

import pytest

from cpu8086.errors import CpuRuntimeError
from cpu8086.machine import _to_signed, assemble_and_load


def run(src: str):
    machine = assemble_and_load(src)
    machine.run()
    return machine


class TestMul:
    def test_byte_small_product_no_carry(self) -> None:
        machine = run("MOV AL, 12\nMOV BL, 10\nMUL BL\nHLT")
        assert machine.registers.get("AX") == 120
        assert machine.registers.flags["CF"] == 0  # AH = 0
        assert machine.registers.flags["OF"] == 0
        assert machine.registers.flags["ZF"] == 0  # low half 120 ≠ 0 (defined policy)

    def test_byte_product_overflow_sets_cf_of(self) -> None:
        machine = run("MOV AL, 16\nMOV BL, 17\nMUL BL\nHLT")  # 272 = 0x0110
        assert machine.registers.get("AX") == 272
        assert machine.registers.flags["CF"] == 1  # AH = 1 ≠ 0
        assert machine.registers.flags["OF"] == 1

    def test_word_product_high_half_in_dx(self) -> None:
        machine = run("MOV AX, 1000\nMOV BX, 100\nMUL BX\nHLT")  # 100000 = 0x186A0
        assert machine.registers.get("AX") == 0x86A0
        assert machine.registers.get("DX") == 1
        assert machine.registers.flags["CF"] == 1

    def test_word_small_product_no_carry(self) -> None:
        machine = run("MOV AX, 300\nMOV BX, 7\nMUL BX\nHLT")  # 2100
        assert machine.registers.get("AX") == 2100
        assert machine.registers.get("DX") == 0
        assert machine.registers.flags["CF"] == 0

    def test_zero_product(self) -> None:
        machine = run("MOV AL, 0\nMOV BL, 9\nMUL BL\nHLT")
        assert machine.registers.get("AX") == 0
        assert machine.registers.flags["ZF"] == 1  # low half zero (defined policy)
        assert machine.registers.flags["CF"] == 0

    def test_memory_operand(self) -> None:
        machine = run("MOV WORD [0x300], 6\nMOV AL, 7\nMUL BYTE [0x300]\nHLT")
        assert machine.registers.get("AX") == 42


class TestImul:
    def test_negative_times_negative_fits(self) -> None:
        machine = run("MOV AL, 0xFD\nMOV BL, 0xFE\nIMUL BL\nHLT")  # -3 * -2 = 6
        assert _to_signed(machine.registers.get("AX"), 16) == 6
        assert machine.registers.flags["CF"] == 0
        assert machine.registers.flags["OF"] == 0

    def test_negative_result_stored_two_complement(self) -> None:
        machine = run("MOV AL, 250\nMOV BL, 6\nIMUL BL\nHLT")  # -6 * 6 = -36
        assert machine.registers.get("AX") == 0xFFDC
        assert machine.registers.flags["CF"] == 0  # -36 fits a signed byte

    def test_word_product_overflow(self) -> None:
        machine = run("MOV AX, 30000\nMOV BX, 2\nIMUL BX\nHLT")  # 60000 > 32767
        assert machine.registers.get("AX") == 60000 & 0xFFFF
        assert machine.registers.flags["CF"] == 1
        assert machine.registers.flags["OF"] == 1

    def test_word_negative_product(self) -> None:
        machine = run("MOV AX, 0xFFCE\nMOV BX, 3\nIMUL BX\nHLT")  # -50 * 3 = -150
        assert machine.registers.get("AX") == 0xFF6A
        assert machine.registers.get("DX") == 0xFFFF  # sign extension
        assert machine.registers.flags["CF"] == 0  # -150 fits a signed word

    def test_boundary_minus128(self) -> None:
        machine = run("MOV AL, 0x80\nMOV BL, 0xFF\nIMUL BL\nHLT")  # -128 * -1 = 128
        # 128 does NOT fit a signed byte -> CF=OF=1, AX = 0x0080
        assert machine.registers.get("AX") == 128
        assert machine.registers.flags["CF"] == 1


class TestDiv:
    def test_byte_quotient_and_remainder(self) -> None:
        machine = run("MOV AX, 100\nMOV BL, 7\nDIV BL\nHLT")
        assert machine.registers.get("AL") == 14
        assert machine.registers.get("AH") == 2

    def test_word_dividend_dx_ax(self) -> None:
        machine = run("MOV DX, 1\nMOV AX, 0x86A0\nMOV BX, 100\nDIV BX\nHLT")  # 100000 / 100
        assert machine.registers.get("AX") == 1000
        assert machine.registers.get("DX") == 0

    def test_flags_unchanged(self) -> None:
        # ADD 255+1 sets CF=1, ZF=1 (result 0x00); DIV must leave every flag alone
        # (defined policy) — a recomputed result (quotient 14) would give ZF=0.
        machine = run("MOV AL, 255\nMOV AH, 0\nMOV BL, 7\nADD AL, 1\nMOV AX, 100\nMOV BL, 7\nDIV BL\nHLT")
        assert machine.registers.flags["CF"] == 1
        assert machine.registers.flags["ZF"] == 1

    def test_divide_by_zero_is_typed_error(self) -> None:
        with pytest.raises(CpuRuntimeError) as exc:
            run("MOV AX, 5\nMOV BX, 0\nDIV BX\nHLT")
        assert "divide by zero" in str(exc.value)

    def test_byte_quotient_overflow(self) -> None:
        with pytest.raises(CpuRuntimeError) as exc:
            run("MOV AX, 1000\nMOV BL, 1\nDIV BL\nHLT")
        assert "divide overflow" in str(exc.value)


class TestIdiv:
    def test_byte_negative_dividend(self) -> None:
        machine = run("MOV AX, 0xFF9C\nMOV BX, 7\nIDIV BL\nHLT")  # -100 / 7
        assert _to_signed(machine.registers.get("AL"), 8) == -14  # truncates toward zero
        assert _to_signed(machine.registers.get("AH"), 8) == -2  # remainder takes dividend sign

    def test_word_negative_dividend_via_dx(self) -> None:
        machine = run("MOV AX, 0xFF9C\nMOV DX, 0xFFFF\nMOV BX, 7\nIDIV BX\nHLT")
        assert _to_signed(machine.registers.get("AX"), 16) == -14
        assert _to_signed(machine.registers.get("DX"), 16) == -2

    def test_word_negative_divisor(self) -> None:
        machine = run("MOV AX, 100\nMOV DX, 0\nMOV BX, 0xFFFB\nIDIV BX\nHLT")  # 100 / -5
        assert _to_signed(machine.registers.get("AX"), 16) == -20
        assert machine.registers.get("DX") == 0

    def test_truncation_toward_zero(self) -> None:
        machine = run("MOV AX, 0xFF9C\nMOV DX, 0xFFFF\nMOV BX, 10\nIDIV BX\nHLT")  # -100 / 10
        assert _to_signed(machine.registers.get("AX"), 16) == -10
        # -101 / 10: floor would give -11, x86 truncation gives -10, remainder -1
        machine = run("MOV AX, 0xFF9B\nMOV DX, 0xFFFF\nMOV BX, 10\nIDIV BX\nHLT")
        assert _to_signed(machine.registers.get("AX"), 16) == -10
        assert _to_signed(machine.registers.get("DX"), 16) == -1

    def test_divide_by_zero_is_typed_error(self) -> None:
        with pytest.raises(CpuRuntimeError):
            run("MOV AX, 5\nMOV BX, 0\nIDIV BX\nHLT")

    def test_signed_quotient_overflow(self) -> None:
        # 0x7FFFFFFF (2147483647) / 1 does not fit a signed word quotient.
        with pytest.raises(CpuRuntimeError) as exc:
            run("MOV AX, 0xFFFF\nMOV DX, 0x7FFF\nMOV BX, 1\nIDIV BX\nHLT")
        assert "divide overflow" in str(exc.value)


class TestTraceIntegration:
    def test_mul_visible_in_trace_and_timing(self) -> None:
        from cpu8086.timing import get_timing

        machine = assemble_and_load("MOV AL, 12\nMOV BL, 10\nMUL BL\nHLT")
        trace, reason = machine.run(max_steps=10)
        assert reason == "hlt"
        mul_record = [r for r in trace if r.instruction.startswith("MUL")]
        assert len(mul_record) == 1
        assert mul_record[0].register_changes.get("AX") == 120
        # CF was already 0 and stays 0 — unchanged flags appear in no change set.
        assert "CF" not in mul_record[0].flag_changes
        assert machine.registers.flags["CF"] == 0
        assert get_timing("MUL").base_cycles == 70  # published timing still wired

    def test_factorial_5_via_mul_loop(self) -> None:
        machine = run("MOV CX, 5\nMOV AX, 1\nloop:\nMUL CX\nDEC CX\nJNZ loop\nHLT")
        assert machine.registers.get("AX") == 120  # 5!
