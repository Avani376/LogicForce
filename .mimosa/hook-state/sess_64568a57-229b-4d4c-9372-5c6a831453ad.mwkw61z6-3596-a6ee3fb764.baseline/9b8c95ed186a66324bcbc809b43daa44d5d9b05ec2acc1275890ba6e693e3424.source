"""Flip-flop and counter characteristic tables (normative per clock-edge-rules.md).

Pure functions over :class:`logic_engine.values.LogicValue`. Every entry is checked
exhaustively by tests against the semantics document.
"""

from __future__ import annotations

from logic_engine.values import LogicValue, not_

_0 = LogicValue.ZERO
_1 = LogicValue.ONE
_X = LogicValue.UNKNOWN
_Z = LogicValue.HIGH_Z


def _is_known(value: LogicValue) -> bool:
    return value in (_0, _1)


def dff_next(d: LogicValue) -> LogicValue:
    """D capture: 0->0, 1->1, X/Z -> X."""
    if d is _0:
        return _0
    if d is _1:
        return _1
    return _X


def tff_next(t: LogicValue, q: LogicValue) -> LogicValue:
    """T: 0 holds, 1 toggles, X/Z -> X."""
    if t is _0:
        return q
    if t is _1:
        return not_(q)
    return _X


def jkff_next(j: LogicValue, k: LogicValue, q: LogicValue) -> LogicValue:
    """JK: 00 hold, 01 reset, 10 set, 11 toggle; any X/Z operand -> X."""
    if not (_is_known(j) and _is_known(k)):
        return _X
    if j is _0 and k is _0:
        return q
    if j is _0 and k is _1:
        return _0
    if j is _1 and k is _0:
        return _1
    return not_(q)  # j=1, k=1


def srff_next(s: LogicValue, r: LogicValue, q: LogicValue) -> LogicValue:
    """SR: 00 hold, 01 reset, 10 set, 11 forbidden -> X; any X/Z operand -> X."""
    if not (_is_known(s) and _is_known(r)):
        return _X
    if s is _0 and r is _0:
        return q
    if s is _0 and r is _1:
        return _0
    if s is _1 and r is _0:
        return _1
    return _X  # s=1, r=1 forbidden


def async_apply(pre: LogicValue, clr: LogicValue) -> LogicValue | None:
    """Async override decision per the contract's stage-2 table.

    Returns the forced value (``ONE``/``ZERO``), ``UNKNOWN`` for the invalid
    combinations (both asserted, or any X/Z control), or ``None`` when no override
    applies (``pre=0, clr=0``).
    """
    if pre is _1 and clr is _0:
        return _1
    if pre is _0 and clr is _1:
        return _0
    if pre is _1 and clr is _1:
        return _X
    if not (_is_known(pre) and _is_known(clr)):
        return _X
    return None


def counter_next(en: LogicValue, q_bits: list[LogicValue]) -> list[LogicValue]:
    """Counter: en=0 holds, en=1 increments (q0 is LSB, wraps mod 2^w), else all X.

    An increment over unknown state bits yields all-X (the value is unknown, so the
    successor is unknown — the honest reading).
    """
    if en is _0:
        return list(q_bits)
    if en is not _1:
        return [_X for _ in q_bits]
    if all(_is_known(bit) for bit in q_bits):
        value = 0
        for index, bit in enumerate(q_bits):
            if bit is _1:
                value += 1 << index
        value = (value + 1) % (1 << len(q_bits))
        return [LogicValue.ONE if (value >> i) & 1 else LogicValue.ZERO for i in range(len(q_bits))]
    return [_X for _ in q_bits]
