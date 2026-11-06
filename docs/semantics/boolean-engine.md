# Semantics: Boolean Engine v1

Status: **CONTRACT for Phase C2** (implemented in `engines/boolean/boolean_engine`)
Engine version: 0.1.0

## Expression parser

Parses boolean expressions with variables (single letters), `!` (NOT), `&` (AND),
`|` (OR), `^` (XOR), parentheses, and literals `0`/`1`. Precedence: `!` > `&` >
`^` > `|`. Typed `BOOLEAN_SYNTAX_ERROR` on malformed input.

## Canonical forms

From a truth table (variables ≤ 8):
- **SOP** (Σm): sum of minterms where output = 1
- **POS** (ΠM): product of maxterms where output = 0
- Both include minterm/maxterm numbering

## Theorem library (12 theorems, each exhaustively verified)

Identity, Null, Idempotent, Complement, Involution, Commutative (AND/OR),
Associative (AND/OR), Distributive (AND over OR, OR over AND), Absorption (2 forms),
Consensus, De Morgan (2 forms). Each returns a step-by-step proof with the theorem name.

## NAND/NOR transform

Converts any gate (AND, OR, NOT) to NAND-only or NOR-only equivalent, proven
equivalent by exhaustive truth-table comparison.
