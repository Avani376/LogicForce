"""Schema v2 parsing and pin inventory for sequential circuits.

Reuses :mod:`logic_engine.graph` component/net model wholesale — v2 is a strict
superset of v1 with additional component types. Normative source:
``docs/semantics/circuit-graph-schema-v2.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from logic_engine.components import Component
from logic_engine.errors import SchemaError
from logic_engine.graph import Net, parse_circuit

from sequential_engine.version import MAX_STATE_WIDTH, SCHEMA_VERSION_V2

TYPE_DFF = "DFF"
TYPE_TFF = "TFF"
TYPE_JKFF = "JKFF"
TYPE_SRFF = "SRFF"
TYPE_REGISTER = "REGISTER"
TYPE_COUNTER = "COUNTER"

#: Single-bit flip-flops (explicit per-type capture pins).
FF_TYPES: dict[str, tuple[str, ...]] = {
    TYPE_DFF: ("d",),
    TYPE_TFF: ("t",),
    TYPE_JKFF: ("j", "k"),
    TYPE_SRFF: ("s", "r"),
}

#: Types that require a `width` param.
MULTI_BIT_TYPES = (TYPE_REGISTER, TYPE_COUNTER)

SUPPORTED_SEQUENTIAL_TYPES = frozenset({*FF_TYPES, *MULTI_BIT_TYPES})

RESERVED_ID_PREFIXES = ("SQ:", "SP:")


@dataclass(frozen=True)
class StateComponentSpec:
    """Resolved pin inventory for one sequential (state-holding) component."""

    id: str
    type: str
    width: int
    capture_pins: tuple[str, ...]
    async_pins: tuple[str, ...]
    state_bits: tuple[str, ...]
    has_complement: bool


def is_state_component(component_type: str) -> bool:
    return component_type in SUPPORTED_SEQUENTIAL_TYPES


def state_width(component: Component) -> int | None:
    """Width for REGISTER/COUNTER (None = invalid/missing, validation reports it)."""
    if component.type not in MULTI_BIT_TYPES:
        return 1
    raw = component.params.get("width")
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    if not 1 <= raw <= MAX_STATE_WIDTH:
        return None
    return raw


def resolve_state_spec(component: Component) -> StateComponentSpec | None:
    """Resolve the pin inventory; ``None`` when the component is not a state type.

    Width problems are NOT resolved here (returns spec with width 1 for reporting
    by validation) — ``validation.py`` owns the INVALID_STATE_WIDTH code.
    """
    if not is_state_component(component.type):
        return None
    comp_type = component.type
    if comp_type in FF_TYPES:
        capture = FF_TYPES[comp_type]
        return StateComponentSpec(
            id=component.id,
            type=comp_type,
            width=1,
            capture_pins=capture,
            async_pins=("pre", "clr"),
            state_bits=("q",),
            has_complement=True,
        )
    width = state_width(component) or 1
    if comp_type == TYPE_REGISTER:
        return StateComponentSpec(
            id=component.id,
            type=comp_type,
            width=width,
            capture_pins=tuple(f"d{i}" for i in range(width)),
            async_pins=("pre", "clr"),
            state_bits=tuple(f"q{i}" for i in range(width)),
            has_complement=False,
        )
    return StateComponentSpec(
        id=component.id,
        type=comp_type,
        width=width,
        capture_pins=("en",),
        async_pins=("clr",),
        state_bits=tuple(f"q{i}" for i in range(width)),
        has_complement=False,
    )


def input_pins_for_seq(component: Component) -> tuple[str, ...] | None:
    """All input pin names of a v2 component (gates reuse the v1 helper).

    Returns ``None`` for unknown types so validation can flag them.
    """
    spec = resolve_state_spec(component)
    if spec is not None:
        return (*spec.capture_pins, *spec.async_pins)
    from logic_engine.components import input_pins_for

    return input_pins_for(component.type, component.params)


def output_pins_for_seq(component: Component) -> tuple[str, ...] | None:
    """All output pin names of a v2 component (None for unknown types)."""
    spec = resolve_state_spec(component)
    if spec is not None:
        pins: list[str] = list(spec.state_bits)
        if spec.has_complement:
            pins.append("qn")
        return tuple(pins)
    from logic_engine.components import output_pins_for

    return output_pins_for(component.type)


def parse_circuit_v2(raw: object) -> tuple[list[Component], list[Net], str | None]:
    """Parse a schema-v2 document into components + nets (v1 model reused).

    Raises :class:`SchemaError` for unsupported schema versions or structural
    garbage (v1 error codes, same as ``logic_engine.parse_circuit``).
    """
    if not isinstance(raw, dict):
        raise SchemaError("INVALID_DOCUMENT", "circuit document must be a JSON object")
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION_V2:
        raise SchemaError(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"sequential engine requires schema_version {SCHEMA_VERSION_V2}, got {version!r}",
        )
    # Reuse the v1 structural parser (components/nets arrays, ids, pin refs) by
    # lending it a v1-compatible view: it checks schema_version itself, so hand it
    # a shallow copy with schema_version 1 and re-attach the true version after.
    view = dict(raw)
    view["schema_version"] = 1
    graph = parse_circuit(view)
    if graph.schema_version != 1:  # defensive; parse_circuit enforces it
        raise SchemaError("INVALID_DOCUMENT", "internal parse mismatch")
    name = raw.get("name")
    name = name if isinstance(name, str) else None
    return list(graph.components), list(graph.nets), name
