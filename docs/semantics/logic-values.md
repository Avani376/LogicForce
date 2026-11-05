# Semantics: Logic Values and Gate Truth Tables

Status: **IMPLEMENTED** (contract for `engines/logic/logic_engine/values.py`)
Engine version: 0.1.0 · Schema version: 1

## Logic value domain

The engine uses a four-valued domain. Every net, pin, and primary I/O carries exactly one of:

| Value | Name | Meaning |
|---|---|---|
| `0` | Logic zero | Driven low |
| `1` | Logic one | Driven high |
| `X` | Unknown | Value exists but is not known (unresolved, conflicting resolution, unset input) |
| `Z` | High impedance | Not driven |

Serialization: JSON strings `"0"`, `"1"`, `"X"`, `"Z"`. Nothing else is accepted at engine boundaries.

## Gate truth tables (binary form)

These tables are the **normative** definition; the implementation is tested against them exhaustively (all 16 input pairs per gate, plus N-input fold cases).

### NOT (inverter)

| a | NOT a |
|---|---|
| 0 | 1 |
| 1 | 0 |
| X | X |
| Z | X |

### BUFFER

| a | BUF a |
|---|---|
| 0 | 0 |
| 1 | 1 |
| X | X |
| Z | X |

### AND

`0` is dominant: if any input is `0` the result is `0`. If all inputs are `1` the result is `1`. Otherwise `X`.

| AND | 0 | 1 | X | Z |
|---|---|---|---|---|
| **0** | 0 | 0 | 0 | 0 |
| **1** | 0 | 1 | X | X |
| **X** | 0 | X | X | X |
| **Z** | 0 | X | X | X |

### OR

`1` is dominant: if any input is `1` the result is `1`. If all inputs are `0` the result is `0`. Otherwise `X`.

| OR | 0 | 1 | X | Z |
|---|---|---|---|---|
| **0** | 0 | 1 | X | X |
| **1** | 1 | 1 | 1 | 1 |
| **X** | X | 1 | X | X |
| **Z** | X | 1 | X | X |

### NAND = NOT(AND)

| NAND | 0 | 1 | X | Z |
|---|---|---|---|---|
| **0** | 1 | 1 | 1 | 1 |
| **1** | 1 | 0 | X | X |
| **X** | 1 | X | X | X |
| **Z** | 1 | X | X | X |

### NOR = NOT(OR)

| NOR | 0 | 1 | X | Z |
|---|---|---|---|---|
| **0** | 1 | 0 | X | X |
| **1** | 0 | 0 | 0 | 0 |
| **X** | X | 0 | X | X |
| **Z** | X | 0 | X | X |

### XOR

| XOR | 0 | 1 | X | Z |
|---|---|---|---|---|
| **0** | 0 | 1 | X | X |
| **1** | 1 | 0 | X | X |
| **X** | X | X | X | X |
| **Z** | X | X | X | X |

### XNOR = NOT(XOR)

| XNOR | 0 | 1 | X | Z |
|---|---|---|---|---|
| **0** | 1 | 0 | X | X |
| **1** | 0 | 1 | X | X |
| **X** | X | X | X | X |
| **Z** | X | X | X | X |

## Multi-input gates

`AND`, `OR`, `NAND`, `NOR`, `XOR`, `XNOR` accept `width` inputs (2 ≤ width ≤ 16; default 2).
Input pin names are `a`, `b`, `c`, … in alphabet order. Evaluation is a **left fold of the
binary table applied in ascending pin-name order**:

```
result = table(input_a, input_b); then result = table(result, input_c); …
```

This order is normative for trace determinism (it fixes *when* X-propagation is observed),
not for the final combinational value, which the tables make fold-order-independent.

## Constants and primary I/O

- `CONST0` / `CONST1`: components that constantly drive `0` / `1` on their `out` pin.
- `INPUT` (primary input): drives the value provided in the simulation input vector on its `out` pin. **If the vector omits the input, it defaults to `X`.** The default is deterministic and part of the contract.
- `OUTPUT` (primary output): reads the single net attached to its `in` pin.

## Out of scope for v1

Tri-state resolution (multiple `Z`-capable drivers on one net), wired-AND/OR nets, strengths.
A net with more than one driver is a **validation error** (`MULTI_DRIVER_NET`); this will be
revisited only when tri-state buses become a requirement.
