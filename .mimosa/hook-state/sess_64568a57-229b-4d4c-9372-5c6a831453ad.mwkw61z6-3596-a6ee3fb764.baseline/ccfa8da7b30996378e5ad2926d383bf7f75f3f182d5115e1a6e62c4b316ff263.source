"""Flag semantics tests against documented Intel behavior (cpu8086.md table)."""

from __future__ import annotations

import pytest
from cpu8086.registers import (
    BYTE_HALVES,
    Registers,
    add_flags,
    inc_dec_flags,
    logic_flags,
    neg_flags,
    parity_of_low_byte,
    sub_flags,
)

_0, _1 = 0, 1


class TestKnownVectors8Bit:
    """Classic documented vectors for 8-bit AL operations."""

    def test_add_7f_plus_01_sets_of_sf_af_clears_cf_zf(self) -> None:
        flags = add_flags(0x7F, 0x01, 0, 8)
        assert flags["CF"] == _0
        assert flags["OF"] == _1
        assert flags["SF"] == _1
        assert flags["ZF"] == _0
        assert flags["AF"] == _1

    def test_add_ff_plus_01_sets_cf_zf_af_pf(self) -> None:
        flags = add_flags(0xFF, 0x01, 0, 8)
        assert flags["CF"] == _1
        assert flags["ZF"] == _1
        assert flags["AF"] == _1
        assert flags["PF"] == _1  # 0x00 -> even parity

    def test_add_7fff_plus_1_word_overflows(self) -> None:
        flags = add_flags(0x7FFF, 0x0001, 0, 16)
        assert flags["OF"] == _1
        assert flags["SF"] == _1
        assert flags["CF"] == _0

    def test_sub_00_minus_01_sets_cf_sf_af(self) -> None:
        flags = sub_flags(0x00, 0x01, 0, 8)
        assert flags["CF"] == _1
        assert flags["SF"] == _1
        assert flags["AF"] == _1
        assert flags["OF"] == _0

    def test_sub_80_minus_01_sets_of(self) -> None:
        flags = sub_flags(0x80, 0x01, 0, 8)
        assert flags["OF"] == _1
        assert flags["CF"] == _0
        assert flags["ZF"] == _0
        assert flags["SF"] == _0

    def test_sub_equal_operands_zero_flag(self) -> None:
        flags = sub_flags(0x42, 0x42, 0, 8)
        assert flags["ZF"] == _1
        assert flags["CF"] == _0
        assert flags["PF"] == _1  # 0x00 even parity


class TestParity:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(0x00, 1), (0x01, 0), (0x03, 1), (0x07, 0), (0xFF, 1), (0x80, 0), (0xC0, 1)],
    )
    def test_parity_of_low_byte(self, value: int, expected: int) -> None:
        assert parity_of_low_byte(value) == expected

    def test_pf_uses_low_byte_only(self) -> None:
        """0x1FF has low byte 0xFF (even parity -> PF=1); word value ignored."""
        assert parity_of_low_byte(0x1FF) == 1


class TestIncDec:
    def test_inc_ff_wraps_and_sets_zf_keeps_cf_unchanged(self) -> None:
        deltas = inc_dec_flags(0xFF, 0x00, 8, increment=True)
        assert deltas["ZF"] == _1
        assert deltas["AF"] == _1
        assert "CF" not in deltas  # INC/DEC do not touch CF (documented)

    def test_dec_00_wraps_and_sets_borrow_flags(self) -> None:
        deltas = inc_dec_flags(0x00, 0xFF, 8, increment=False)
        assert deltas["SF"] == _1
        assert deltas["AF"] == _1
        # 0 -> 0xFF: pre-value 0 (non-negative) and result 0xFF (negative) — but
        # DEC of 0 to -1 does NOT overflow in two's complement, so OF = 0
        assert deltas["OF"] == _0

    def test_inc_7f_sets_of(self) -> None:
        deltas = inc_dec_flags(0x7F, 0x80, 8, increment=True)
        assert deltas["OF"] == _1


class TestNeg:
    def test_neg_00_cf_zero(self) -> None:
        flags = neg_flags(0x00, 8)
        assert flags["CF"] == _0
        assert flags["ZF"] == _1

    def test_neg_80_byte_of_and_cf(self) -> None:
        flags = neg_flags(0x80, 8)
        assert flags["CF"] == _1
        assert flags["OF"] == _1
        assert flags["ZF"] == _0


class TestLogic:
    def test_logic_clears_cf_of_af(self) -> None:
        flags = logic_flags(0x00, 8)
        assert flags["CF"] == _0
        assert flags["OF"] == _0
        assert flags["AF"] == _0

    def test_logic_sets_zf_sf_pf(self) -> None:
        assert logic_flags(0x00, 8)["ZF"] == _1
        assert logic_flags(0x80, 8)["SF"] == _1
        assert logic_flags(0x03, 8)["PF"] == _1


class TestRegisterModel:
    def test_byte_halves_map_to_word(self) -> None:
        regs = Registers()
        regs.set("AX", 0x1234)
        assert regs.get("AL") == 0x34
        assert regs.get("AH") == 0x12
        regs.set("AL", 0x88)
        assert regs.get("AX") == 0x1288
        regs.set("AH", 0x7B)
        assert regs.get("AX") == 0x7B88

    def test_word_register_masked_to_16_bits(self) -> None:
        regs = Registers()
        regs.set("AX", 0x1FFFF)
        assert regs.get("AX") == 0xFFFF

    def test_unknown_register_raises(self) -> None:
        regs = Registers()
        with pytest.raises(KeyError):
            regs.get("QX")

    def test_byte_half_names_complete(self) -> None:
        assert set(BYTE_HALVES) == {"AL", "AH", "BL", "BH", "CL", "CH", "DL", "DH"}

    def test_snapshot_combines_words_and_flags(self) -> None:
        regs = Registers()
        regs.set("AX", 5)
        regs.set_flags({"ZF": 1})
        snapshot = regs.snapshot()
        assert snapshot["AX"] == 5
        assert snapshot["ZF"] == 1
