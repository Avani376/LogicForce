"""Exhaustive gate-table tests against the semantics document (independent oracle).

The tables below are transcriptions of ``docs/semantics/logic-values.md`` — the
normative contract. Any engine change that deviates from the document fails here.
"""

from __future__ import annotations

import pytest
from logic_engine.values import (
    LogicValue,
    and_,
    buffer_,
    nand_,
    nor_,
    normalize_value,
    not_,
    or_,
    xnor_,
    xor_,
)

_0, _1, _X, _Z = (
    LogicValue.ZERO,
    LogicValue.ONE,
    LogicValue.UNKNOWN,
    LogicValue.HIGH_Z,
)
ALL = [_0, _1, _X, _Z]

NOT_TABLE = {_0: _1, _1: _0, _X: _X, _Z: _X}
BUF_TABLE = {_0: _0, _1: _1, _X: _X, _Z: _X}

AND_TABLE = {
    (_0, _0): _0,
    (_0, _1): _0,
    (_0, _X): _0,
    (_0, _Z): _0,
    (_1, _0): _0,
    (_1, _1): _1,
    (_1, _X): _X,
    (_1, _Z): _X,
    (_X, _0): _0,
    (_X, _1): _X,
    (_X, _X): _X,
    (_X, _Z): _X,
    (_Z, _0): _0,
    (_Z, _1): _X,
    (_Z, _X): _X,
    (_Z, _Z): _X,
}

OR_TABLE = {
    (_0, _0): _0,
    (_0, _1): _1,
    (_0, _X): _X,
    (_0, _Z): _X,
    (_1, _0): _1,
    (_1, _1): _1,
    (_1, _X): _1,
    (_1, _Z): _1,
    (_X, _0): _X,
    (_X, _1): _1,
    (_X, _X): _X,
    (_X, _Z): _X,
    (_Z, _0): _X,
    (_Z, _1): _1,
    (_Z, _X): _X,
    (_Z, _Z): _X,
}

XOR_TABLE = {
    (_0, _0): _0,
    (_0, _1): _1,
    (_0, _X): _X,
    (_0, _Z): _X,
    (_1, _0): _1,
    (_1, _1): _0,
    (_1, _X): _X,
    (_1, _Z): _X,
    (_X, _0): _X,
    (_X, _1): _X,
    (_X, _X): _X,
    (_X, _Z): _X,
    (_Z, _0): _X,
    (_Z, _1): _X,
    (_Z, _X): _X,
    (_Z, _Z): _X,
}

NAND_TABLE = {
    (_0, _0): _1,
    (_0, _1): _1,
    (_0, _X): _1,
    (_0, _Z): _1,
    (_1, _0): _1,
    (_1, _1): _0,
    (_1, _X): _X,
    (_1, _Z): _X,
    (_X, _0): _1,
    (_X, _1): _X,
    (_X, _X): _X,
    (_X, _Z): _X,
    (_Z, _0): _1,
    (_Z, _1): _X,
    (_Z, _X): _X,
    (_Z, _Z): _X,
}

NOR_TABLE = {
    (_0, _0): _1,
    (_0, _1): _0,
    (_0, _X): _X,
    (_0, _Z): _X,
    (_1, _0): _0,
    (_1, _1): _0,
    (_1, _X): _0,
    (_1, _Z): _0,
    (_X, _0): _X,
    (_X, _1): _0,
    (_X, _X): _X,
    (_X, _Z): _X,
    (_Z, _0): _X,
    (_Z, _1): _0,
    (_Z, _X): _X,
    (_Z, _Z): _X,
}

XNOR_TABLE = {
    (_0, _0): _1,
    (_0, _1): _0,
    (_0, _X): _X,
    (_0, _Z): _X,
    (_1, _0): _0,
    (_1, _1): _1,
    (_1, _X): _X,
    (_1, _Z): _X,
    (_X, _0): _X,
    (_X, _1): _X,
    (_X, _X): _X,
    (_X, _Z): _X,
    (_Z, _0): _X,
    (_Z, _1): _X,
    (_Z, _X): _X,
    (_Z, _Z): _X,
}


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_and_table(a: LogicValue, b: LogicValue) -> None:
    assert and_(a, b) == AND_TABLE[(a, b)]


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_or_table(a: LogicValue, b: LogicValue) -> None:
    assert or_(a, b) == OR_TABLE[(a, b)]


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_xor_table(a: LogicValue, b: LogicValue) -> None:
    assert xor_(a, b) == XOR_TABLE[(a, b)]


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_nand_table_matches_document(a: LogicValue, b: LogicValue) -> None:
    assert nand_(a, b) == NAND_TABLE[(a, b)]


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_nor_table_matches_document(a: LogicValue, b: LogicValue) -> None:
    assert nor_(a, b) == NOR_TABLE[(a, b)]


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_xnor_table_matches_document(a: LogicValue, b: LogicValue) -> None:
    assert xnor_(a, b) == XNOR_TABLE[(a, b)]


@pytest.mark.parametrize("a", ALL)
def test_not_table(a: LogicValue) -> None:
    assert not_(a) == NOT_TABLE[a]


@pytest.mark.parametrize("a", ALL)
def test_buffer_table(a: LogicValue) -> None:
    assert buffer_(a) == BUF_TABLE[a]


@pytest.mark.parametrize("a", ALL)
@pytest.mark.parametrize("b", ALL)
def test_composed_tables_equal_document_tables(a: LogicValue, b: LogicValue) -> None:
    """NAND/NOR/XNOR are implemented as composition; composition must equal the doc."""
    assert nand_(a, b) == NOT_TABLE[AND_TABLE[(a, b)]]
    assert nor_(a, b) == NOT_TABLE[OR_TABLE[(a, b)]]
    assert xnor_(a, b) == NOT_TABLE[XOR_TABLE[(a, b)]]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", _0),
        ("1", _1),
        ("X", _X),
        ("Z", _Z),
        (0, _0),
        (1, _1),
        (_0, _0),
        (_1, _1),
    ],
)
def test_normalize_accepts_contract_values(raw: object, expected: LogicValue) -> None:
    assert normalize_value(raw) == expected


@pytest.mark.parametrize(
    "raw", ["2", "x", "high", "", "00", True, False, None, 2, 1.5, ["0"], {"v": 1}]
)
def test_normalize_rejects_everything_else(raw: object) -> None:
    with pytest.raises(ValueError, match="invalid logic value"):
        normalize_value(raw)
