"""NumSys tests: conversions, complements, codes — cross-checked against Python builtins."""

from __future__ import annotations

import pytest
from numsys import (
    ascii_lookup,
    bcd_decode,
    bcd_encode,
    complement_add,
    convert_with_steps,
    excess3_decode,
    excess3_encode,
    gray_decode,
    gray_encode,
    ones_complement,
    twos_complement,
)


class TestBaseConversion:
    @pytest.mark.parametrize(
        "value,from_base,to_base,expected",
        [
            ("255", 10, 2, "11111111"),
            ("255", 10, 16, "FF"),
            ("11111111", 2, 10, "255"),
            ("FF", 16, 10, "255"),
            ("FF", 16, 2, "11111111"),
            ("777", 8, 10, "511"),
            ("0", 10, 2, "0"),
            ("1", 10, 16, "1"),
            ("-42", 10, 2, "-101010"),
            ("-FF", 16, 10, "-255"),
        ],
    )
    def test_cross_checked_against_python(self, value: str, from_base: int, to_base: int, expected: str) -> None:
        result = convert_with_steps(value, from_base, to_base)
        assert result.result == expected
        # cross-check against Python builtins
        assert int(result.result, to_base) == int(value, from_base)

    @pytest.mark.parametrize("value,from_base", [("GG", 16), ("12", 2), ("AB", 8)])
    def test_invalid_digits_raise(self, value: str, from_base: int) -> None:
        with pytest.raises(ValueError, match="invalid digit"):
            convert_with_steps(value, from_base, 10)

    def test_steps_present(self) -> None:
        result = convert_with_steps("255", 10, 2)
        assert len(result.steps) >= 1
        assert result.scope_label == "EXHAUSTIVE"


class TestComplements:
    def test_ones_complement_8bit(self) -> None:
        assert ones_complement("01010101", 8).result == "10101010"
        assert ones_complement("11111111", 8).result == "00000000"

    def test_twos_complement_8bit(self) -> None:
        assert twos_complement("00000001", 8).result == "11111111"
        assert twos_complement("00000000", 8).result == "00000000"

    def test_twos_complement_negative_range(self) -> None:
        result = twos_complement("00000001", 8)
        assert "-128 to +127" in result.assumptions[0]

    def test_complement_add_positive(self) -> None:
        result = complement_add("00000101", "00000011", 8, use_twos=True)
        assert result.result == "00001000"  # 5 + 3 = 8

    def test_complement_add_negative(self) -> None:
        # -1 (11111111) + +1 (00000001) = 0
        result = complement_add("11111111", "00000001", 8, use_twos=True)
        assert result.result == "00000000"

    def test_invalid_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            ones_complement("01", 3)


class TestBCD:
    def test_bcd_encode(self) -> None:
        assert bcd_encode("25").result == "0010 0101"

    def test_bcd_decode(self) -> None:
        assert bcd_decode("0010 0101").result == "25"

    def test_bcd_invalid_nibble(self) -> None:
        with pytest.raises(ValueError, match="invalid BCD"):
            bcd_decode("1010")

    def test_bcd_roundtrip(self) -> None:
        for value in ("0", "9", "42", "99", "123"):
            encoded = bcd_encode(value)
            assert bcd_decode(encoded.result).result == value


class TestExcess3:
    def test_excess3_encode(self) -> None:
        assert excess3_encode("0").result == "0011"  # 0 + 3 = 3

    def test_excess3_roundtrip(self) -> None:
        for value in ("0", "5", "42", "99"):
            encoded = excess3_encode(value)
            assert excess3_decode(encoded.result).result == value


class TestGray:
    def test_gray_encode_known_values(self) -> None:
        assert gray_encode("000").result == "000"
        assert gray_encode("001").result == "001"
        assert gray_encode("010").result == "011"
        assert gray_encode("011").result == "010"

    def test_gray_roundtrip(self) -> None:
        for i in range(16):
            binary = format(i, "04b")
            gray = gray_encode(binary)
            decoded = gray_decode(gray.result)
            assert decoded.result == binary

    def test_gray_adjacent_codes_differ_by_one_bit(self) -> None:
        prev = gray_encode(format(0, "04b")).result
        for i in range(1, 16):
            current = gray_encode(format(i, "04b")).result
            diff_count = sum(a != b for a, b in zip(prev, current, strict=False))
            assert diff_count == 1
            prev = current


class TestASCII:
    def test_ascii_lookup(self) -> None:
        result = ascii_lookup("A")
        assert "0x41" in result.result
        assert result.steps[0].output == "0x41"
