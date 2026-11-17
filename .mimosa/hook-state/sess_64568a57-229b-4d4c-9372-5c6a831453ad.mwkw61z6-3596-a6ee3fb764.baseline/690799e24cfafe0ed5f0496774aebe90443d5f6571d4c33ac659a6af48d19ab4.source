"""Exhaustive flip-flop characteristic-table tests vs the semantics contract.

Oracle tables transcribed from ``docs/semantics/clock-edge-rules.md``.
"""

from __future__ import annotations

import pytest
from logic_engine.values import LogicValue
from sequential_engine.flipflops import (
    async_apply,
    counter_next,
    dff_next,
    jkff_next,
    srff_next,
    tff_next,
)

_0, _1, _X, _Z = (
    LogicValue.ZERO,
    LogicValue.ONE,
    LogicValue.UNKNOWN,
    LogicValue.HIGH_Z,
)
ALL = [_0, _1, _X, _Z]
KNOWN = [_0, _1]

D_TABLE = {_0: _0, _1: _1, _X: _X, _Z: _X}
T_TABLE = {_0: "hold", _1: "toggle", _X: _X, _Z: _X}
JK_TABLE = {
    (_0, _0): "hold",
    (_0, _1): _0,
    (_1, _0): _1,
    (_1, _1): "toggle",
}
SR_TABLE = {
    (_0, _0): "hold",
    (_0, _1): _0,
    (_1, _0): _1,
    (_1, _1): _X,
}
ASYNC_TABLE = {
    (_1, _0): _1,
    (_0, _1): _0,
    (_1, _1): _X,
}


def _expected(value: object, q: LogicValue) -> LogicValue:
    if value == "hold":
        return q
    if value == "toggle":
        return LogicValue.ONE if q is _0 else LogicValue.ZERO
    assert isinstance(value, LogicValue)
    return value


@pytest.mark.parametrize("d", ALL)
def test_dff_table(d: LogicValue) -> None:
    assert dff_next(d) == D_TABLE[d]


@pytest.mark.parametrize("t", ALL)
@pytest.mark.parametrize("q", KNOWN)
def test_tff_table(t: LogicValue, q: LogicValue) -> None:
    assert tff_next(t, q) == _expected(T_TABLE[t], q)


@pytest.mark.parametrize("j", ALL)
@pytest.mark.parametrize("k", ALL)
@pytest.mark.parametrize("q", KNOWN)
def test_jkff_table(j: LogicValue, k: LogicValue, q: LogicValue) -> None:
    if (j, k) in JK_TABLE:
        assert jkff_next(j, k, q) == _expected(JK_TABLE[(j, k)], q)
    else:
        assert jkff_next(j, k, q) == _X


@pytest.mark.parametrize("s", ALL)
@pytest.mark.parametrize("r", ALL)
@pytest.mark.parametrize("q", KNOWN)
def test_srff_table(s: LogicValue, r: LogicValue, q: LogicValue) -> None:
    if (s, r) in SR_TABLE:
        assert srff_next(s, r, q) == _expected(SR_TABLE[(s, r)], q)
    else:
        assert srff_next(s, r, q) == _X


@pytest.mark.parametrize("pre", ALL)
@pytest.mark.parametrize("clr", ALL)
def test_async_table(pre: LogicValue, clr: LogicValue) -> None:
    if (pre, clr) == (_0, _0):
        assert async_apply(pre, clr) is None
    elif (pre, clr) in ASYNC_TABLE:
        assert async_apply(pre, clr) == ASYNC_TABLE[(pre, clr)]
    else:
        # any X/Z control, or both asserted: invalid -> X (honesty rule)
        assert async_apply(pre, clr) == _X


def test_counter_wraps_at_two_to_the_w() -> None:
    # bit lists are [q0, q1, q2] — q0 is the LSB (contract)
    assert counter_next(_1, [_0, _0, _0]) == [_1, _0, _0]  # 0 -> 1
    assert counter_next(_1, [_1, _0, _1]) == [_0, _1, _1]  # 5 -> 6
    assert counter_next(_1, [_1, _1, _1]) == [_0, _0, _0]  # 7 -> 0 wrap
    assert counter_next(_0, [_1, _0, _1]) == [_1, _0, _1]  # hold


def test_counter_unknowns_are_honest() -> None:
    assert counter_next(_X, [_0, _0, _0]) == [_X, _X, _X]
    assert counter_next(_Z, [_0, _0, _0]) == [_X, _X, _X]
    assert counter_next(_1, [_X, _0, _0]) == [_X, _X, _X]  # unknown value -> unknown successor
