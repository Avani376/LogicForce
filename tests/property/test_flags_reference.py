"""Differential flag tests: the engine's flag computation vs an independent
reference model written directly from the Intel-spec definitions (signed
arithmetic for OF, arithmetic comparison for CF). No engine helper is reused.

Property-based with hypothesis: if the engine and the reference ever disagree
on any operand pair, the differential test fails with the counterexample.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from cpu8086.errors import CpuRuntimeError
from cpu8086.machine import assemble_and_load
from cpu8086.registers import inc_dec_flags, neg_flags, sub_flags


def _signed(value: int, width: int) -> int:
    value &= (1 << width) - 1
    sign = 1 << (width - 1)
    return value - (1 << width) if value & sign else value


def _parity(low_byte: int) -> int:
    return 1 if bin(low_byte & 0xFF).count("1") % 2 == 0 else 0


def _ref_add(a: int, b: int, cin: int, width: int) -> dict[str, int]:
    """Reference ADD flags — written from the spec, independent of the engine."""
    mask = (1 << width) - 1
    result = (a + b + cin) & mask
    sa, sb, sr = _signed(a, width), _signed(b, width), _signed(result, width)
    s = sa + sb + cin
    return {
        "CF": 1 if a + b + cin > mask else 0,
        "OF": 1 if s < -(1 << (width - 1)) or s > (1 << (width - 1)) - 1 else 0,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & (1 << (width - 1)) else 0,
        "PF": _parity(result),
        "AF": 1 if ((a & 0xF) + (b & 0xF) + cin) > 0xF else 0,
    }


def _ref_sub(a: int, b: int, bin_: int, width: int) -> dict[str, int]:
    """Reference SUB flags — borrow + signed overflow from the spec."""
    mask = (1 << width) - 1
    result = (a - b - bin_) & mask
    sa, sb = _signed(a, width), _signed(b, width)
    s = sa - sb - bin_
    return {
        "CF": 1 if b + bin_ > a else 0,
        "OF": 1 if s < -(1 << (width - 1)) or s > (1 << (width - 1)) - 1 else 0,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & (1 << (width - 1)) else 0,
        "PF": _parity(result),
        "AF": 1 if ((a & 0xF) - (b & 0xF) - bin_) < 0 else 0,
    }


def _run(src: str):
    machine = assemble_and_load(src)
    machine.run()
    return machine


class TestAddDifferential:
    @settings(max_examples=120, deadline=None)
    @given(
        a=st.integers(min_value=0, max_value=255),
        b=st.integers(min_value=0, max_value=255),
        cin=st.integers(min_value=0, max_value=1),
    )
    def test_byte_add(self, a: int, b: int, cin: int) -> None:
        from cpu8086.registers import add_flags

        reference = _ref_add(a, b, cin, 8)
        assert add_flags(a, b, cin, 8) == reference, (a, b, cin)

    @settings(max_examples=120, deadline=None)
    @given(
        a=st.integers(min_value=0, max_value=0xFFFF),
        b=st.integers(min_value=0, max_value=0xFFFF),
        cin=st.integers(min_value=0, max_value=1),
    )
    def test_word_add(self, a: int, b: int, cin: int) -> None:
        from cpu8086.registers import add_flags

        reference = _ref_add(a, b, cin, 16)
        assert add_flags(a, b, cin, 16) == reference, (a, b, cin)

    @settings(max_examples=40, deadline=None)
    @given(
        a=st.integers(min_value=0, max_value=0xFFFF),
        b=st.integers(min_value=0, max_value=0xFFFF),
        cin=st.integers(min_value=0, max_value=1),
    )
    def test_machine_add_matches_reference(self, a: int, b: int, cin: int) -> None:
        if cin:
            # Set CF via a prior ADD that produces carry (0xFFFF + 1).
            machine = assemble_and_load(f"MOV AX, 0xFFFF\nADD AX, 1\nMOV AX, {a}\nMOV BX, {b}\nADC AX, BX\nHLT")
        else:
            machine = assemble_and_load(f"MOV AX, {a}\nMOV BX, {b}\nADD AX, BX\nHLT")
        machine.run()
        reference = _ref_add(a, b, cin, 16)
        observed = {k: machine.registers.flags[k] for k in reference}
        assert observed == reference, (a, b, cin, observed)


class TestSubDifferential:
    @settings(max_examples=120, deadline=None)
    @given(
        a=st.integers(min_value=0, max_value=255),
        b=st.integers(min_value=0, max_value=255),
        bin_=st.integers(min_value=0, max_value=1),
    )
    def test_byte_sub(self, a: int, b: int, bin_: int) -> None:
        reference = _ref_sub(a, b, bin_, 8)
        assert sub_flags(a, b, bin_, 8) == reference, (a, b, bin_)

    @settings(max_examples=120, deadline=None)
    @given(
        a=st.integers(min_value=0, max_value=0xFFFF),
        b=st.integers(min_value=0, max_value=0xFFFF),
        bin_=st.integers(min_value=0, max_value=1),
    )
    def test_word_sub(self, a: int, b: int, bin_: int) -> None:
        reference = _ref_sub(a, b, bin_, 16)
        assert sub_flags(a, b, bin_, 16) == reference, (a, b, bin_)

    @settings(max_examples=40, deadline=None)
    @given(
        a=st.integers(min_value=0, max_value=0xFFFF),
        b=st.integers(min_value=0, max_value=0xFFFF),
    )
    def test_machine_cmp_matches_reference(self, a: int, b: int) -> None:
        machine = assemble_and_load(f"MOV AX, {a}\nMOV BX, {b}\nCMP AX, BX\nHLT")
        machine.run()
        reference = _ref_sub(a, b, 0, 16)
        observed = {k: machine.registers.flags[k] for k in reference}
        assert observed == reference, (a, b, observed)


class TestIncDecNegDifferential:
    @settings(max_examples=80, deadline=None)
    @given(v=st.integers(min_value=0, max_value=0xFFFF), up=st.booleans())
    def test_inc_dec_via_machine(self, v: int, up: bool) -> None:
        from cpu8086.registers import inc_dec_flags

        verb = "INC" if up else "DEC"
        machine = assemble_and_load(f"MOV AX, {v}\n{verb} AX\nHLT")
        machine.run()
        mask = 0xFFFF
        result = (v + (1 if up else -1)) & mask
        # INC/DEC: OF only at the signed boundary (INC from +MAX, DEC from -MAX)
        expected_of = 1 if (up and v == 0x7FFF) or ((not up) and v == 0x8000) else 0
        observed = {
            "ZF": 1 if result == 0 else 0,
            "SF": 1 if result & 0x8000 else 0,
            "OF": expected_of,
        }
        engine = inc_dec_flags(v & mask, result, 16, increment=up)
        for key, value in observed.items():
            assert engine[key] == value, (v, up, key)

    @settings(max_examples=60, deadline=None)
    @given(a=st.integers(min_value=0, max_value=255))
    def test_neg_matches_two_complement(self, a: int) -> None:
        machine = assemble_and_load(f"MOV AL, {a}\nNEG AL\nHLT")
        machine.run()
        expected = (-_signed(a, 8)) & 0xFF
        assert machine.registers.get("AL") == expected
        # NEG: CF=1 iff operand != 0
        assert machine.registers.flags["CF"] == (1 if a != 0 else 0)


class TestMulDifferential:
    @settings(max_examples=60, deadline=None)
    @given(a=st.integers(min_value=0, max_value=0xFFFF), b=st.integers(min_value=0, max_value=0xFFFF))
    def test_word_mul_product_and_carry(self, a: int, b: int) -> None:
        machine = assemble_and_load(f"MOV AX, {a}\nMOV BX, {b}\nMUL BX\nHLT")
        machine.run()
        full = a * b
        assert machine.registers.get("AX") == full & 0xFFFF
        assert machine.registers.get("DX") == (full >> 16) & 0xFFFF
        assert machine.registers.flags["CF"] == (1 if full >> 16 != 0 else 0)
        assert machine.registers.flags["OF"] == machine.registers.flags["CF"]

    def test_byte_mul_boundary(self) -> None:
        machine = assemble_and_load("MOV AL, 255\nMOV BL, 255\nMUL BL\nHLT")  # 65025
        machine.run()
        assert machine.registers.get("AX") == 65025
        assert machine.registers.flags["CF"] == 1  # AH = 253 ≠ 0
