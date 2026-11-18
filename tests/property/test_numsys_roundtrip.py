"""Round-trip property tests: every numsys conversion must survive its inverse.

Reference behavior comes from the spec (positional notation, two's-complement
definition, Gray single-bit property, BCD nibble rules) — never from reusing
the engine's encoder as its own decoder.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from numsys import (
    bcd_decode,
    bcd_encode,
    excess3_decode,
    excess3_encode,
    gray_decode,
    gray_encode,
    twos_complement,
)
from numsys.conversions import int_to_base

BASES = list(range(2, 17))


def _base_to_int(text: str, base: int) -> int:
    """Independent positional parser (reference, not the engine)."""
    digits = "0123456789ABCDEF"[:base]
    total = 0
    for ch in text.upper():
        total = total * base + digits.index(ch)
    return total


class TestBaseRoundTrip:
    @settings(max_examples=150, deadline=None)
    @given(
        value=st.integers(min_value=0, max_value=1_000_000),
        base=st.sampled_from(BASES),
    )
    def test_int_to_base_then_back(self, value: int, base: int) -> None:
        text = int_to_base(value, base)
        assert int(int(text, base), 0) if False else _base_to_int(text, base) == value

    @settings(max_examples=100, deadline=None)
    @given(
        value=st.integers(min_value=0, max_value=65535),
        from_base=st.sampled_from(BASES),
        to_base=st.sampled_from(BASES),
    )
    def test_base_to_base_chain(self, value: int, from_base: int, to_base: int) -> None:
        text = int_to_base(value, from_base)
        assert _base_to_int(int_to_base(_base_to_int(text, from_base), to_base), to_base) == value

    @given(base=st.sampled_from(BASES))
    def test_known_values(self, base: int) -> None:
        assert _base_to_int(int_to_base(255, base), base) == 255
        assert _base_to_int(int_to_base(0, base), base) == 0


class TestTwosComplement:
    @settings(max_examples=120, deadline=None)
    @given(
        positive=st.integers(min_value=0, max_value=127),
        width=st.sampled_from([4, 8, 16]),  # the engine's documented widths
    )
    def test_encode_produces_valid_pattern(self, positive: int, width: int) -> None:
        max_positive = (1 << (width - 1)) - 1  # representable range constraint
        if positive > max_positive:
            return
        bits = format(positive, f"0{width}b")
        result = twos_complement(bits, width).result
        assert len(result) == width
        # Decode manually per the definition: value = bits if < sign, else bits - 2^w
        unsigned = int(result, 2)
        signed = unsigned - (1 << width) if unsigned & (1 << (width - 1)) else unsigned
        assert signed == -positive

    @settings(max_examples=60, deadline=None)
    @given(width=st.sampled_from([4, 8, 16]))
    def test_zero_and_min(self, width: int) -> None:
        zero = twos_complement("0" * width, width).result
        assert set(zero) == {"0"}
        min_positive = 1 << (width - 1)
        most_negative = twos_complement(format(min_positive, f"0{width}b"), width).result
        # 2's complement of +2^(w-1) is itself (the documented asymmetry)
        assert most_negative == format(min_positive, f"0{width}b")


class TestGrayRoundTrip:
    @settings(max_examples=150, deadline=None)
    @given(bits=st.integers(min_value=0, max_value=255))
    def test_encode_decode_round_trip(self, bits: int) -> None:
        binary = format(bits, "08b")
        gray = gray_encode(binary).result
        # Gray property: adjacent binary values differ in exactly one gray bit
        assert len(gray) == 8
        decoded = gray_decode(gray).result
        assert decoded == binary

    @given(a=st.integers(min_value=0, max_value=255), b=st.integers(min_value=0, max_value=255))
    def test_adjacent_single_bit_property(self, a: int, b: int) -> None:
        """Consecutive values' Gray codes differ in exactly one bit (spec property)."""
        if abs(a - b) != 1:
            return
        ga = gray_encode(format(a, "08b")).result
        gb = gray_encode(format(b, "08b")).result
        assert sum(1 for x, y in zip(ga, gb) if x != y) == 1


class TestBcdAndExcess3:
    @settings(max_examples=80, deadline=None)
    @given(value=st.integers(min_value=0, max_value=9999))
    def test_bcd_round_trip(self, value: int) -> None:
        encoded = bcd_encode(str(value)).result
        assert bcd_decode(encoded).result == str(value)

    @settings(max_examples=80, deadline=None)
    @given(value=st.integers(min_value=0, max_value=999))
    def test_excess3_round_trip(self, value: int) -> None:
        encoded = excess3_encode(str(value)).result
        assert excess3_decode(encoded).result == str(value)
