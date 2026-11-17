"""Boolean engine tests: parser, canonical forms, theorems, NAND/NOR transform."""

from __future__ import annotations

import pytest
from boolean_engine import (
    evaluate,
    parse,
    to_nand_only,
    to_nor_only,
    to_pos,
    to_sop,
    variables,
    verify_theorems,
)
from logic_engine import SchemaError


class TestParser:
    def test_simple_and(self) -> None:
        expr = parse("A & B")
        assert expr.kind == "and"
        assert variables(expr) == ["A", "B"]

    def test_precedence_not_and_or(self) -> None:
        expr = parse("A | B & C")
        assert expr.kind == "or"  # B & C binds first
        assert variables(expr) == ["A", "B", "C"]

    def test_parentheses_override(self) -> None:
        expr = parse("(A | B) & C")
        assert expr.kind == "and"

    def test_not_chain(self) -> None:
        expr = parse("!!A")
        assert expr.kind == "not"
        assert expr.left is not None and expr.left.kind == "not"

    def test_literals(self) -> None:
        expr = parse("1 & 0")
        assert evaluate(expr, {}) is False

    @pytest.mark.parametrize("text", ["", "A &", "& A", "(A", "A @ B"])
    def test_syntax_errors(self, text: str) -> None:
        with pytest.raises(SchemaError) as excinfo:
            parse(text)
        assert excinfo.value.code == "BOOLEAN_SYNTAX_ERROR"

    def test_evaluate(self) -> None:
        expr = parse("A & !B")
        assert evaluate(expr, {"A": True, "B": False}) is True
        assert evaluate(expr, {"A": True, "B": True}) is False


class TestCanonicalForms:
    def test_sop_simple(self) -> None:
        expr = parse("A & B")
        sop = to_sop(expr)
        assert sop["minterms"] == [3]  # only A=1, B=1
        assert "Σ(3,)" in sop["canonical_form"] or "Σ(3)" in sop["canonical_form"]

    def test_pos_simple(self) -> None:
        expr = parse("A & B")
        pos = to_pos(expr)
        assert pos["maxterms"] == [0, 1, 2]

    def test_sop_pos_roundtrip(self) -> None:
        """SOP and POS describe the same truth table."""
        expr = parse("A & !B | !A & C")
        sop = to_sop(expr)
        pos = to_pos(expr)
        minterms = set(sop["minterms"])  # type: ignore[union-attr]
        maxterms = set(pos["maxterms"])  # type: ignore[union-attr]
        total = set(range(1 << len(sop["variables"])))  # type: ignore[union-attr]
        assert minterms | maxterms == total  # every row is either a minterm or maxterm
        assert not (minterms & maxterms)  # no overlap


class TestTheorems:
    def test_all_theorems_verified(self) -> None:
        results = verify_theorems()
        assert len(results) >= 12
        for result in results:
            assert result["verified"] is True
            assert result["scope"].startswith("EXHAUSTIVE(")

    def test_theorem_count(self) -> None:
        results = verify_theorems()
        names = [r["theorem"] for r in results]
        assert len(names) >= 14  # identity×2, null×2, idempotent×2, complement×2,
        # involution, commutative, De Morgan×2, absorption, distributive


class TestNANDNOR:
    def test_nand_only_and_gate(self) -> None:
        expr = parse("A & B")
        result = to_nand_only(expr)
        assert result["equivalent"] is True
        assert "NAND" in result["nand_expression"]  # type: ignore[operator]

    def test_nand_only_or_gate(self) -> None:
        expr = parse("A | B")
        result = to_nand_only(expr)
        assert result["equivalent"] is True

    def test_nor_only_or_gate(self) -> None:
        expr = parse("A | B")
        result = to_nor_only(expr)
        assert result["equivalent"] is True

    def test_nor_only_and_gate(self) -> None:
        expr = parse("A & B")
        result = to_nor_only(expr)
        assert result["equivalent"] is True

    def test_nand_only_complex(self) -> None:
        expr = parse("A & !B | !A & C")
        result = to_nand_only(expr)
        assert result["equivalent"] is True
