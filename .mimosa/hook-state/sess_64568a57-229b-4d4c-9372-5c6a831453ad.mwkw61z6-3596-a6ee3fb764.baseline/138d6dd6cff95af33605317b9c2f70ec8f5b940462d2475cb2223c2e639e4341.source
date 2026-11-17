"""Boolean expression parser, canonical forms, theorems, NAND/NOR transform (boolean-engine.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from logic_engine import SchemaError


@dataclass(frozen=True)
class BoolExpr:
    kind: str  # "var" | "not" | "and" | "or" | "xor" | "lit"
    value: str = ""
    left: BoolExpr | None = None
    right: BoolExpr | None = None


def parse(text: str) -> BoolExpr:
    """Parse a boolean expression; raises BOOLEAN_SYNTAX_ERROR on malformed input."""
    tokens = _tokenize(text)
    if not tokens:
        raise SchemaError("BOOLEAN_SYNTAX_ERROR", "empty expression")
    parser = _Parser(tokens)
    result = parser.parse_or()
    if parser.peek() is not None:
        raise SchemaError("BOOLEAN_SYNTAX_ERROR", f"unexpected token at position {parser.pos}")
    return result


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "!&|^()":
            tokens.append(("op", c))
            i += 1
        elif c.isalnum() or c == "_":
            start = i
            while i < len(text) and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i].upper()
            if word in ("0", "1"):
                tokens.append(("lit", word))
            else:
                tokens.append(("var", word))
        else:
            raise SchemaError("BOOLEAN_SYNTAX_ERROR", f"unexpected character {c!r} at position {i}")
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> tuple[str, str]:
        if self.pos >= len(self.tokens):
            raise SchemaError("BOOLEAN_SYNTAX_ERROR", "unexpected end of expression")
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def parse_or(self) -> BoolExpr:
        node = self.parse_xor()
        while (t := self.peek()) and t == ("op", "|"):
            self.advance()
            node = BoolExpr("or", left=node, right=self.parse_xor())
        return node

    def parse_xor(self) -> BoolExpr:
        node = self.parse_and()
        while (t := self.peek()) and t == ("op", "^"):
            self.advance()
            node = BoolExpr("xor", left=node, right=self.parse_and())
        return node

    def parse_and(self) -> BoolExpr:
        node = self.parse_unary()
        while (t := self.peek()) and t == ("op", "&"):
            self.advance()
            node = BoolExpr("and", left=node, right=self.parse_unary())
        return node

    def parse_unary(self) -> BoolExpr:
        t = self.peek()
        if t and t == ("op", "!"):
            self.advance()
            return BoolExpr("not", left=self.parse_unary())
        return self.parse_atom()

    def parse_atom(self) -> BoolExpr:
        if self.pos >= len(self.tokens):
            raise SchemaError("BOOLEAN_SYNTAX_ERROR", "unexpected end of expression")
        t = self.advance()
        if t[0] == "lit":
            return BoolExpr("lit", value=t[1])
        if t[0] == "var":
            return BoolExpr("var", value=t[1])
        if t == ("op", "("):
            node = self.parse_or()
            closing = self.advance()
            if closing != ("op", ")"):
                raise SchemaError("BOOLEAN_SYNTAX_ERROR", "expected ')'")
            return node
        raise SchemaError("BOOLEAN_SYNTAX_ERROR", f"unexpected token {t[1]!r}")


def evaluate(expr: BoolExpr, env: dict[str, bool]) -> bool:
    if expr.kind == "lit":
        return expr.value == "1"
    if expr.kind == "var":
        return env.get(expr.value, False)
    if expr.kind == "not":
        return not evaluate(cast(BoolExpr, expr.left), env)
    left = evaluate(cast(BoolExpr, expr.left), env)
    right = evaluate(cast(BoolExpr, expr.right), env)
    if expr.kind == "and":
        return left and right
    if expr.kind == "or":
        return left or right
    if expr.kind == "nand":
        return not (left and right)
    if expr.kind == "nor":
        return not (left or right)
    return left != right  # xor


def variables(expr: BoolExpr) -> list[str]:
    if expr.kind == "var":
        return [expr.value]
    result: list[str] = []
    for child in (expr.left, expr.right):
        if child is not None:
            result.extend(variables(child))
    seen: set[str] = set()
    ordered: list[str] = []
    for v in result:
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return sorted(ordered)


def truth_table(expr: BoolExpr) -> list[tuple[dict[str, bool], bool]]:
    """Exhaustive truth table over all variable assignments (sorted name order)."""
    names = variables(expr)
    result = []
    for i in range(1 << len(names)):
        env = {name: bool((i >> (len(names) - 1 - pos)) & 1) for pos, name in enumerate(names)}
        result.append((env, evaluate(expr, env)))
    return result


def to_sop(expr: BoolExpr) -> dict[str, object]:
    """Canonical SOP (sum of minterms) from the truth table."""
    table = truth_table(expr)
    names = variables(expr)
    minterms = [i for i, (_, out) in enumerate(table) if out]
    sop_terms = []
    for minterm in minterms:
        terms = [f"{name}" if (minterm >> (len(names) - 1 - pos)) & 1 else f"!{name}" for pos, name in enumerate(names)]
        sop_terms.append("(" + " & ".join(terms) + ")" if len(names) > 1 else terms[0])
    expression = " | ".join(sop_terms) if sop_terms else "0"
    return {
        "minterms": minterms,
        "expression": expression,
        "canonical_form": "Σ" + str(tuple(minterms)),
        "variables": names,
        "scope_label": f"EXHAUSTIVE({1 << len(names)})",
    }


def to_pos(expr: BoolExpr) -> dict[str, object]:
    """Canonical POS (product of maxterms) from the truth table."""
    table = truth_table(expr)
    names = variables(expr)
    maxterms = [i for i, (_, out) in enumerate(table) if not out]
    pos_terms = []
    for maxterm in maxterms:
        terms = [f"!{name}" if (maxterm >> (len(names) - 1 - pos)) & 1 else f"{name}" for pos, name in enumerate(names)]
        pos_terms.append("(" + " | ".join(terms) + ")" if len(names) > 1 else terms[0])
    expression = " & ".join(pos_terms) if pos_terms else "1"
    return {
        "maxterms": maxterms,
        "expression": expression,
        "canonical_form": "Π" + str(tuple(maxterms)),
        "variables": names,
        "scope_label": f"EXHAUSTIVE({1 << len(names)})",
    }


def _check_property(name: str, lhs: BoolExpr, rhs: BoolExpr) -> dict[str, object]:
    """Exhaustively verify that lhs and rhs are equivalent over their union of variables."""
    lhs_vars = variables(lhs)
    rhs_vars = variables(rhs)
    all_vars = sorted(set(lhs_vars) | set(rhs_vars))
    n = len(all_vars)
    for i in range(1 << n):
        env = {name_: bool((i >> (n - 1 - pos)) & 1) for pos, name_ in enumerate(all_vars)}
        if evaluate(lhs, env) != evaluate(rhs, env):
            raise SchemaError(
                "THEOREM_VIOLATION",
                f"Theorem {name} violated at {env}",
            )
    return {"theorem": name, "cases": 1 << n, "verified": True, "scope": f"EXHAUSTIVE({1 << n})"}


def verify_theorems() -> list[dict[str, object]]:
    """Verify all boolean theorems exhaustively using truth-table equivalence."""
    a = BoolExpr("var", value="A")
    b = BoolExpr("var", value="B")
    c = BoolExpr("var", value="C")
    not_a = BoolExpr("not", left=a)
    not_b = BoolExpr("not", left=b)

    def conj(x: BoolExpr, y: BoolExpr) -> BoolExpr:
        return BoolExpr("and", left=x, right=y)

    def disj(x: BoolExpr, y: BoolExpr) -> BoolExpr:
        return BoolExpr("or", left=x, right=y)

    zero = BoolExpr("lit", value="0")
    one = BoolExpr("lit", value="1")

    results = []

    def check(name: str, lhs: BoolExpr, rhs: BoolExpr) -> None:
        results.append(_check_property(name, lhs, rhs) | {"lhs": _expr_to_string(lhs), "rhs": _expr_to_string(rhs)})

    check("Identity (AND)", conj(a, one), a)
    check("Identity (OR)", disj(a, zero), a)
    check("Null (AND)", conj(a, zero), zero)
    check("Null (OR)", disj(a, one), one)
    check("Idempotent (AND)", conj(a, a), a)
    check("Idempotent (OR)", disj(a, a), a)
    check("Complement (AND)", conj(a, not_a), zero)
    check("Complement (OR)", disj(a, not_a), one)
    check("Involution", BoolExpr("not", left=not_a), a)
    check("Commutative (AND)", conj(a, b), conj(b, a))
    check("Commutative (OR)", disj(a, b), disj(b, a))
    check("De Morgan (AND)", BoolExpr("not", left=conj(a, b)), disj(not_a, not_b))
    check("De Morgan (OR)", BoolExpr("not", left=disj(a, b)), conj(not_a, not_b))
    check("Absorption", disj(conj(a, b), a), a)
    check("Distributive (AND over OR)", conj(a, disj(b, c)), disj(conj(a, b), conj(a, c)))
    return results


def to_nand_only(expr: BoolExpr) -> dict[str, object]:
    """Convert AND/OR/NOT to NAND-only equivalent, verified by exhaustive truth table."""

    def to_nand(node: BoolExpr) -> BoolExpr:
        if node.kind in ("lit", "var"):
            return node
        if node.kind == "not":
            inner = to_nand(cast(BoolExpr, node.left))
            # NOT(x) = NAND(x, x)
            return BoolExpr("nand", left=inner, right=inner)
        left = to_nand(cast(BoolExpr, node.left))
        right = to_nand(cast(BoolExpr, node.right))
        if node.kind == "and":
            # A & B = NOT(NAND(A, B)) = NAND(NAND(A,B), NAND(A,B))
            nand_ab = BoolExpr("nand", left=left, right=right)
            return BoolExpr("nand", left=nand_ab, right=nand_ab)
        if node.kind == "or":
            # A | B = NAND(NOT(A), NOT(B)) = NAND(NAND(A,A), NAND(B,B))
            return BoolExpr(
                "nand", left=BoolExpr("nand", left=left, right=left), right=BoolExpr("nand", left=right, right=right)
            )
        return node  # xor passthrough (v1)

    nand_expr = to_nand(expr)
    original_tt = truth_table(expr)
    nand_tt = truth_table(nand_expr)
    equivalent = original_tt == nand_tt
    return {
        "nand_expression": _expr_to_string(nand_expr),
        "equivalent": equivalent,
        "scope": f"EXHAUSTIVE({len(original_tt)} rows)",
        "original_expression": _expr_to_string(expr),
    }


def to_nor_only(expr: BoolExpr) -> dict[str, object]:
    """Convert AND/OR/NOT to NOR-only equivalent, verified by exhaustive truth table."""

    def to_nor(node: BoolExpr) -> BoolExpr:
        if node.kind in ("lit", "var"):
            return node
        if node.kind == "not":
            inner = to_nor(cast(BoolExpr, node.left))
            return BoolExpr("nor", left=inner, right=inner)
        left = to_nor(cast(BoolExpr, node.left))
        right = to_nor(cast(BoolExpr, node.right))
        if node.kind == "or":
            nor_ab = BoolExpr("nor", left=left, right=right)
            return BoolExpr("nor", left=nor_ab, right=nor_ab)
        if node.kind == "and":
            return BoolExpr(
                "nor", left=BoolExpr("nor", left=left, right=left), right=BoolExpr("nor", left=right, right=right)
            )
        return node

    nor_expr = to_nor(expr)
    original_tt = truth_table(expr)
    nor_tt = truth_table(nor_expr)
    equivalent = original_tt == nor_tt
    return {
        "nor_expression": _expr_to_string(nor_expr),
        "equivalent": equivalent,
        "scope": f"EXHAUSTIVE({len(original_tt)} rows)",
        "original_expression": _expr_to_string(expr),
    }


def _expr_to_string(expr: BoolExpr) -> str:
    if expr.kind == "lit":
        return expr.value
    if expr.kind == "var":
        return expr.value
    if expr.kind == "not":
        return f"!{_expr_to_string(cast(BoolExpr, expr.left))}"
    op = {"and": " & ", "or": " | ", "xor": " ^ ", "nand": " NAND ", "nor": " NOR "}.get(expr.kind, " ? ")
    left = _expr_to_string(cast(BoolExpr, expr.left))
    right = _expr_to_string(cast(BoolExpr, expr.right))
    return f"({left}{op}{right})" if expr.kind in ("and", "or", "xor", "nand", "nor") else f"{left}{op}{right}"


def evaluate_expression(text: str) -> dict[str, object]:
    """Parse, evaluate, and return SOP/POS for a boolean expression string."""
    expr = parse(text)
    sop = to_sop(expr)
    pos = to_pos(expr)
    return {
        "expression": _expr_to_string(expr),
        "variables": variables(expr),
        "sop": sop,
        "pos": pos,
        "scope": sop["scope_label"],
    }
