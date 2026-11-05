# Semantics: Circuit Graph JSON Schema (v1)

Status: **IMPLEMENTED** (contract for `engines/logic/logic_engine/graph.py`)
Schema version: **1** · Engine version: 0.1.0

## Top-level document

```json
{
  "schema_version": 1,
  "name": "half_adder",              // optional, display only
  "components": [ /* Component[] */ ],
  "nets": [ /* Net[] */ ]
}
```

`schema_version` must be exactly `1` in v1. Other integers are rejected with
`UNSUPPORTED_SCHEMA_VERSION` (forward rejection, not silent coercion).

## Component

```json
{
  "id": "G1",                         // required, non-empty, unique, any string without surrounding whitespace
  "type": "XOR",                      // required, one of the supported types below
  "params": { "name": "a", "width": 2 },  // optional object; type-dependent (strictly validated)
  "label": "carry generator",         // optional string; display-only, ignored by the engine
  "position": { "x": 100.0, "y": 80.0 }   // optional; UI metadata, ignored by the engine
}
```

Supported `type` values and their pins:

| Type | Input pins | Output pin | params |
|---|---|---|---|
| `INPUT` | — | `out` | `name` (required, unique across INPUTs) |
| `OUTPUT` | `in` | — | `name` (required, unique across OUTPUTs) |
| `CONST0` / `CONST1` | — | `out` | — |
| `BUFFER`, `NOT` | `a` | `out` | — |
| `AND`, `OR`, `NAND`, `NOR`, `XOR`, `XNOR` | `a`…(width) | `out` | `width` optional int, 2–16, default 2 |

Input pin names for multi-input gates are the first `width` letters of the alphabet
(`a`, `b`, `c`, …).

## Net

```json
{
  "id": "n1",                          // required, non-empty, unique
  "driver": { "component": "IN_a", "pin": "out" },   // required, exactly one
  "sinks": [ { "component": "G1", "pin": "a" } ]     // required array (may be empty → warning)
}
```

A net has **exactly one driver** (an output-capable pin) and any number of sinks
(input-capable pins). Connecting an output pin to another output pin on the same net is
`MULTI_DRIVER_NET`. A sink pin listed on two nets is also `MULTI_DRIVER_NET` (one input,
one net).

## Validation codes (authoritative list, v1)

| Code | Severity | Meaning |
|---|---|---|
| `MULTI_DRIVER_NET` | error | Net with ≠1 driver, or an input pin fed by more than one net |
| `DANGLING_INPUT_PIN` | error | A gate/OUTPUT input pin not connected to any net |
| `UNKNOWN_PIN_REFERENCE` | error | Net references a component id or pin that does not exist |
| `UNKNOWN_COMPONENT_TYPE` | error | Component type not in the supported set |
| `DUPLICATE_COMPONENT_ID` | error | Two components share an id |
| `DUPLICATE_NET_ID` | error | Two nets share an id |
| `DUPLICATE_IO_NAME` | error | Two INPUTs or two OUTPUTs share `params.name` |
| `MISSING_PARAM` | error | Required param absent (e.g. INPUT without `name`) |
| `INVALID_PARAM` | error | Param present but invalid (width out of 2–16, wrong type) |
| `COMBINATIONAL_LOOP` | error | Output→input dependency cycle (components listed) |
| `UNSUPPORTED_SCHEMA_VERSION` | error | `schema_version` ≠ 1 |
| `UNREAD_NET` | warning | Driven net with zero sinks |

Validation is **complete, not fail-fast**: one call returns every error and warning found.
`ok` is true iff there are zero errors. Simulation and truth-table endpoints refuse circuits
whose validation has any error — a warning-level circuit is simulable.

## Canonical serialization

For hashing (`input_hash`) the engine canonicalizes: JSON with **keys sorted
lexicographically** (so two documents differing only in key order hash identically — the
hash identifies the design, not serialization quirks), lists in document order, no
insignificant whitespace, UTF-8. The hash is SHA-256 over
`schema_version + canonical(circuit) + canonical(inputs)`.
