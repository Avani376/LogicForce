"""Expression language tests: tokenizing, precedence, four-valued evaluation."""

from __future__ import annotations

import pytest
from logic_engine import LogicValue, SchemaError
from verify_engine.expressions import evaluate_expression, expression_signals, parse_expression

_0, _1, _X = LogicValue.ZERO, LogicValue.ONE, LogicValue.UNKNOWN


def test_parse_and_evaluate_precedence() -> None:
    """! > & > ^ > | — a | b & c parses as a | (b & c)."""
    node = parse_expression("a | b & c")
    env = {"a": _0, "b": _1, "c": _1}
    assert evaluate_expression(node, env) == _1  # 0 | (1 & 1)


def test_xor_binds_tighter_than_or() -> None:
    """a ^ b | c parses as (a ^ b) | c — discriminated by all-ones: (1^1)|1 = 1,
    whereas |-first would give 1^(1|1) = 0."""
    node = parse_expression("a ^ b | c")
    assert evaluate_expression(node, {"a": _1, "b": _1, "c": _1}) == _1


def test_not_binds_tightest() -> None:
    node = parse_expression("!a & b")
    assert evaluate_expression(node, {"a": _1, "b": _1}) == _0
    assert evaluate_expression(node, {"a": _0, "b": _1}) == _1


def test_parentheses_override_precedence() -> None:
    node = parse_expression("(a | b) & c")
    assert evaluate_expression(node, {"a": _0, "b": _1, "c": _0}) == _0
    assert evaluate_expression(node, {"a": _0, "b": _1, "c": _1}) == _1


def test_literals_and_names() -> None:
    node = parse_expression("1 & !0 | ready")
    assert evaluate_expression(node, {"ready": _1}) == _1


def test_unknown_signal_in_env_is_x() -> None:
    node = parse_expression("declared")
    assert evaluate_expression(node, {}) == _X


def test_x_propagates_through_operators() -> None:
    node = parse_expression("a & b")
    assert evaluate_expression(node, {"a": _X, "b": _1}) == _X
    node = parse_expression("!a")
    assert evaluate_expression(node, {"a": _X}) == _X


@pytest.mark.parametrize(
    "text",
    [
        "",
        "a &",
        "& a",
        "(a",
        "a)",
        "a @ b",
        'a & "b"',
        "a b",
    ],
)
def test_syntax_errors_are_typed(text: str) -> None:
    with pytest.raises(SchemaError) as excinfo:
        parse_expression(text)
    assert excinfo.value.code == "PROPERTY_SYNTAX_ERROR"


def test_signal_extraction_in_document_order() -> None:
    node = parse_expression("b | a & !b ^ c")
    assert expression_signals(node) == ("b", "a", "c")
