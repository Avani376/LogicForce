"""Property expression language v1: tokenizer, parser, evaluator.

Grammar (precedence tightest first: ``!``, ``&``, ``^``, ``|``; binary operators
left-associative; parentheses group)::

    expr   := xor ( '|' xor )*
    xor    := and ( '^' and )*
    and    := unary ( '&' unary )*
    unary  := '!' unary | atom
    atom   := '(' expr ')' | '0' | '1' | NAME

Evaluation uses the four-valued domain and the v1 gate tables — there are no
short-circuits, and X propagates honestly (``docs/semantics/verification-engine.md``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from logic_engine.errors import SchemaError
from logic_engine.values import LogicValue, and_, not_, or_, xor_

_NAME_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_NAME_CHARS = _NAME_START | set("0123456789")


@dataclass(frozen=True)
class Token:
    kind: str  # "name" | "literal" | "op" | "lparen" | "rparen"
    value: str
    pos: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in _NAME_START:
            start = index
            while index < len(text) and text[index] in _NAME_CHARS:
                index += 1
            tokens.append(Token("name", text[start:index], start))
            continue
        if char in "01":
            tokens.append(Token("literal", char, index))
            index += 1
            continue
        if char in "!&|^":
            tokens.append(Token("op", char, index))
            index += 1
            continue
        if char == "(":
            tokens.append(Token("lparen", char, index))
            index += 1
            continue
        if char == ")":
            tokens.append(Token("rparen", char, index))
            index += 1
            continue
        raise SchemaError(
            "PROPERTY_SYNTAX_ERROR",
            f"unexpected character {char!r} at position {index}",
        )
    return tokens


@dataclass(frozen=True)
class ExprNode:
    kind: str  # "lit" | "var" | "not" | "bin"
    value: str  # literal bit, signal name, or operator
    left: ExprNode | None = None
    right: ExprNode | None = None


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> Token:
        token = self.peek()
        if token is None:
            raise SchemaError("PROPERTY_SYNTAX_ERROR", "unexpected end of expression")
        self.pos += 1
        return token

    def parse_expr(self) -> ExprNode:
        node = self.parse_xor()
        while True:
            token = self.peek()
            if token is not None and token.kind == "op" and token.value == "|":
                self.advance()
                node = ExprNode(kind="bin", value="|", left=node, right=self.parse_xor())
            else:
                return node

    def parse_xor(self) -> ExprNode:
        node = self.parse_and()
        while True:
            token = self.peek()
            if token is not None and token.kind == "op" and token.value == "^":
                self.advance()
                node = ExprNode(kind="bin", value="^", left=node, right=self.parse_and())
            else:
                return node

    def parse_and(self) -> ExprNode:
        node = self.parse_unary()
        while True:
            token = self.peek()
            if token is not None and token.kind == "op" and token.value == "&":
                self.advance()
                node = ExprNode(kind="bin", value="&", left=node, right=self.parse_unary())
            else:
                return node

    def parse_unary(self) -> ExprNode:
        token = self.peek()
        if token is not None and token.kind == "op" and token.value == "!":
            self.advance()
            return ExprNode(kind="not", value="!", left=self.parse_unary())
        return self.parse_atom()

    def parse_atom(self) -> ExprNode:
        token = self.advance()
        if token.kind == "literal":
            return ExprNode(kind="lit", value=token.value)
        if token.kind == "name":
            return ExprNode(kind="var", value=token.value)
        if token.kind == "lparen":
            node = self.parse_expr()
            closing = self.advance()
            if closing.kind != "rparen":
                raise SchemaError(
                    "PROPERTY_SYNTAX_ERROR",
                    f"expected ')' at position {closing.pos}",
                )
            return node
        raise SchemaError(
            "PROPERTY_SYNTAX_ERROR",
            f"unexpected token {token.value!r} at position {token.pos}",
        )


def parse_expression(text: str) -> ExprNode:
    """Parse a property expression; raises ``PROPERTY_SYNTAX_ERROR`` (typed)."""
    if not isinstance(text, str) or not text.strip():
        raise SchemaError("PROPERTY_SYNTAX_ERROR", "expression must be a non-empty string")
    parser = _Parser(tokenize(text))
    node = parser.parse_expr()
    leftover = parser.peek()
    if leftover is not None:
        raise SchemaError(
            "PROPERTY_SYNTAX_ERROR",
            f"unexpected token {leftover.value!r} at position {leftover.pos}",
        )
    return node


def expression_signals(node: ExprNode) -> tuple[str, ...]:
    """Signal names referenced by the expression, in document order, deduped."""
    if node.kind == "var":
        return (node.value,)
    if node.kind == "lit":
        return ()
    signals: list[str] = []
    if node.left is not None:
        signals.extend(expression_signals(node.left))
    if node.right is not None:
        signals.extend(expression_signals(node.right))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in signals:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def evaluate_expression(node: ExprNode, env: Mapping[str, LogicValue]) -> LogicValue:
    """Evaluate the AST in the four-valued domain (no short-circuits).

    A signal missing from ``env`` evaluates to ``X`` — honest for partial output
    vectors (e.g. FSM transitions that declare only some outputs).
    """
    if node.kind == "lit":
        return LogicValue.ONE if node.value == "1" else LogicValue.ZERO
    if node.kind == "var":
        return env.get(node.value, LogicValue.UNKNOWN)
    if node.kind == "not":
        return not_(evaluate_expression(node.left, env))  # type: ignore[arg-type]
    left = evaluate_expression(node.left, env)  # type: ignore[arg-type]
    right = evaluate_expression(node.right, env)  # type: ignore[arg-type]
    if node.value == "&":
        return and_(left, right)
    if node.value == "|":
        return or_(left, right)
    return xor_(left, right)
