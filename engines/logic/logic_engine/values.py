"""Logic values and gate truth tables.

Normative source: ``docs/semantics/logic-values.md``. The tables here implement that
contract exactly; ``tests/unit/test_values.py`` checks every entry of every table.
"""

from __future__ import annotations

import enum


class LogicValue(enum.StrEnum):
    """Four-valued logic domain.

    Values serialize as the JSON strings ``"0"``, ``"1"``, ``"X"``, ``"Z"``. ``X`` means
    "exists but unknown" (unresolved or unset input); ``Z`` means high impedance. No v1
    component drives ``Z``; the value is kept for schema stability.
    """

    ZERO = "0"
    ONE = "1"
    UNKNOWN = "X"
    HIGH_Z = "Z"


def not_(a: LogicValue) -> LogicValue:
    """Inverter: 0->1, 1->0, X->X, Z->X."""
    return _NOT[a]


def buffer_(a: LogicValue) -> LogicValue:
    """Buffer: 0->0, 1->1, X->X, Z->X (a driven-Z input reads as unknown)."""
    return _BUF[a]


def and_(a: LogicValue, b: LogicValue) -> LogicValue:
    """AND: 0 is dominant; 1 only if both are 1; otherwise X."""
    return _AND[(a, b)]


def or_(a: LogicValue, b: LogicValue) -> LogicValue:
    """OR: 1 is dominant; 0 only if both are 0; otherwise X."""
    return _OR[(a, b)]


def xor_(a: LogicValue, b: LogicValue) -> LogicValue:
    """XOR: difference of two known bits; any X/Z operand yields X."""
    return _XOR[(a, b)]


def nand_(a: LogicValue, b: LogicValue) -> LogicValue:
    """NAND is NOT(AND) applied to the AND table result."""
    return not_(and_(a, b))


def nor_(a: LogicValue, b: LogicValue) -> LogicValue:
    """NOR is NOT(OR) applied to the OR table result."""
    return not_(or_(a, b))


def xnor_(a: LogicValue, b: LogicValue) -> LogicValue:
    """XNOR is NOT(XOR) applied to the XOR table result."""
    return not_(xor_(a, b))


#: Binary gate evaluation functions keyed by component type (multi-input gates fold
#: this binary function left-to-right in ascending pin-name order; see simulator.py).
BINARY_FUNCS = {
    "AND": and_,
    "OR": or_,
    "NAND": nand_,
    "NOR": nor_,
    "XOR": xor_,
    "XNOR": xnor_,
}

_NOT: dict[LogicValue, LogicValue] = {
    LogicValue.ZERO: LogicValue.ONE,
    LogicValue.ONE: LogicValue.ZERO,
    LogicValue.UNKNOWN: LogicValue.UNKNOWN,
    LogicValue.HIGH_Z: LogicValue.UNKNOWN,
}

_BUF: dict[LogicValue, LogicValue] = {
    LogicValue.ZERO: LogicValue.ZERO,
    LogicValue.ONE: LogicValue.ONE,
    LogicValue.UNKNOWN: LogicValue.UNKNOWN,
    LogicValue.HIGH_Z: LogicValue.UNKNOWN,
}

_V = LogicValue
_Z, _X, _0, _1 = _V.HIGH_Z, _V.UNKNOWN, _V.ZERO, _V.ONE

_AND: dict[tuple[LogicValue, LogicValue], LogicValue] = {
    (_0, _0): _0, (_0, _1): _0, (_1, _0): _0, (_1, _1): _1,
    (_0, _X): _0, (_X, _0): _0, (_0, _Z): _0, (_Z, _0): _0,
    (_1, _X): _X, (_X, _1): _X, (_1, _Z): _X, (_Z, _1): _X,
    (_X, _X): _X, (_X, _Z): _X, (_Z, _X): _X, (_Z, _Z): _X,
}

_OR: dict[tuple[LogicValue, LogicValue], LogicValue] = {
    (_1, _0): _1, (_0, _1): _1, (_1, _1): _1,
    (_1, _X): _1, (_X, _1): _1, (_1, _Z): _1, (_Z, _1): _1,
    (_0, _0): _0,
    (_0, _X): _X, (_X, _0): _X, (_0, _Z): _X, (_Z, _0): _X,
    (_X, _X): _X, (_X, _Z): _X, (_Z, _X): _X, (_Z, _Z): _X,
}

_XOR: dict[tuple[LogicValue, LogicValue], LogicValue] = {
    (_0, _0): _0, (_0, _1): _1, (_1, _0): _1, (_1, _1): _0,
    (_0, _X): _X, (_X, _0): _X, (_0, _Z): _X, (_Z, _0): _X,
    (_1, _X): _X, (_X, _1): _X, (_1, _Z): _X, (_Z, _1): _X,
    (_X, _X): _X, (_X, _Z): _X, (_Z, _X): _X, (_Z, _Z): _X,
}


def normalize_value(raw: object) -> LogicValue:
    """Normalize an external value into :class:`LogicValue`.

    Accepts ``LogicValue`` instances, the strings ``"0"``, ``"1"``, ``"X"``, ``"Z"`` and
    the integers ``0``/``1`` (bools are rejected even though ``bool`` subclasses ``int``).
    Anything else raises :class:`ValueError` with a stable message; callers at API level
    map it to HTTP 400. Strictness is deliberate: silently coercing ``"x"`` or ``"high"``
    would make results depend on undocumented coercions.
    """
    if isinstance(raw, LogicValue):
        return raw
    if isinstance(raw, bool):
        raise ValueError(f"invalid logic value: {raw!r}")
    if isinstance(raw, int) and raw in (0, 1):
        return LogicValue.ONE if raw == 1 else LogicValue.ZERO
    if isinstance(raw, str):
        try:
            return LogicValue(raw)
        except ValueError:
            raise ValueError(f"invalid logic value: {raw!r}") from None
    raise ValueError(f"invalid logic value: {raw!r}")
