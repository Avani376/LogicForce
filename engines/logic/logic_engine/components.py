"""Component and pin model for the circuit graph.

Normative source: ``docs/semantics/circuit-graph-schema.md`` (pin inventory table).
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field

from logic_engine.version import MAX_GATE_WIDTH

# --- component type vocabulary -------------------------------------------------

TYPE_INPUT = "INPUT"
TYPE_OUTPUT = "OUTPUT"
TYPE_CONST0 = "CONST0"
TYPE_CONST1 = "CONST1"
TYPE_BUFFER = "BUFFER"
TYPE_NOT = "NOT"

#: Multi-input gate types (``width`` param, default 2, max 16).
MULTI_INPUT_GATES: frozenset[str] = frozenset({"AND", "OR", "NAND", "NOR", "XOR", "XNOR"})

#: Every component type accepted by schema v1.
SUPPORTED_TYPES: frozenset[str] = frozenset(
    {
        TYPE_INPUT,
        TYPE_OUTPUT,
        TYPE_CONST0,
        TYPE_CONST1,
        TYPE_BUFFER,
        TYPE_NOT,
        *MULTI_INPUT_GATES,
    }
)

#: Params allowed per type (anything else is INVALID_PARAM at validation).
ALLOWED_PARAMS: dict[str, frozenset[str]] = {
    TYPE_INPUT: frozenset({"name"}),
    TYPE_OUTPUT: frozenset({"name"}),
    TYPE_CONST0: frozenset(),
    TYPE_CONST1: frozenset(),
    TYPE_BUFFER: frozenset(),
    TYPE_NOT: frozenset(),
    **{gate: frozenset({"width"}) for gate in sorted(MULTI_INPUT_GATES)},
}

OUT_PIN = "out"
OUTPUT_INPUT_PIN = "in"
SINGLE_INPUT_PIN = "a"

_TYPE_TO_NAME = {
    TYPE_INPUT: "input",
    TYPE_OUTPUT: "output",
    TYPE_CONST0: "constant",
    TYPE_CONST1: "constant",
    TYPE_BUFFER: "gate",
    TYPE_NOT: "gate",
}
for _gate in MULTI_INPUT_GATES:
    _TYPE_TO_NAME[_gate] = "gate"


def component_kind(component_type: str) -> str:
    """Classify a type as ``"input"``, ``"output"``, ``"constant"`` or ``"gate"``."""
    return _TYPE_TO_NAME.get(component_type, "unknown")


def input_pins_for(component_type: str, params: dict[str, object]) -> tuple[str, ...]:
    """Input pin names for a component type (empty for sources).

    Multi-input gates expose ``width`` pins named ``a``, ``b``, ``c`` … An invalid or
    missing ``width`` falls back to the default 2 here; ``validation.py`` is responsible
    for reporting invalid widths, so this helper never raises.
    """
    if component_type == TYPE_OUTPUT:
        return (OUTPUT_INPUT_PIN,)
    if component_type in MULTI_INPUT_GATES:
        raw_width = params.get("width", 2)
        width = raw_width if isinstance(raw_width, int) and not isinstance(raw_width, bool) else 2
        if not 2 <= width <= MAX_GATE_WIDTH:
            width = 2
        return tuple(string.ascii_lowercase[:width])
    if component_type in (TYPE_BUFFER, TYPE_NOT):
        return (SINGLE_INPUT_PIN,)
    return ()


def output_pins_for(component_type: str) -> tuple[str, ...]:
    """Output pin names for a component type (empty for OUTPUT, which only reads)."""
    if component_type in (TYPE_INPUT, TYPE_CONST0, TYPE_CONST1):
        return (OUT_PIN,)
    if component_type in (TYPE_BUFFER, TYPE_NOT, *MULTI_INPUT_GATES):
        return (OUT_PIN,)
    return ()


@dataclass(frozen=True)
class Component:
    """A node of the circuit graph.

    ``params`` is the type-specific parameter mapping (strictly validated elsewhere);
    ``label`` and ``position`` are display-only metadata the engine never interprets.
    """

    id: str
    type: str
    params: dict[str, object] = field(default_factory=dict)
    label: str | None = None
    position: tuple[float, float] | None = None
