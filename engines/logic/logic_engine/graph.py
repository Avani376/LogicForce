"""Circuit graph parsing: circuit JSON schema v1 into typed objects.

Normative source: ``docs/semantics/circuit-graph-schema.md``.

Parsing is deliberately split from semantic validation: *document-shape* problems that
the graph model cannot represent (wrong container types, unsupported ``schema_version``)
raise :class:`logic_engine.errors.SchemaError` immediately; *semantic* problems
(duplicate ids, dangling pins, cycles, bad params) are preserved in the graph or
reported by ``logic_engine.validation.validate`` as a complete report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from logic_engine.components import Component
from logic_engine.errors import SchemaError
from logic_engine.version import SCHEMA_VERSION


@dataclass(frozen=True)
class PinRef:
    """A reference to one pin of one component."""

    component: str
    pin: str


@dataclass(frozen=True)
class Net:
    """A single-driver net: one output pin drives zero or more input pins.

    ``driver`` is ``None`` when the document omitted it or malformed it; the driver
    entry is then reported by validation as ``UNKNOWN_PIN_REFERENCE``/``MULTI_DRIVER_NET``
    so the report stays complete rather than aborting the walk.
    """

    id: str
    driver: PinRef | None
    sinks: tuple[PinRef, ...]


@dataclass(frozen=True)
class CircuitGraph:
    """Parsed circuit document.

    ``components`` and ``nets`` keep document order *including duplicates* so that
    validation can report ``DUPLICATE_COMPONENT_ID`` / ``DUPLICATE_NET_ID`` precisely.
    ``name`` is display-only metadata.
    """

    schema_version: int
    name: str | None
    components: tuple[Component, ...]
    nets: tuple[Net, ...]


def _require_mapping(raw: object, what: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise SchemaError("INVALID_DOCUMENT", f"{what} must be a JSON object")
    return raw


def _parse_pin_ref(raw: object, net_id: str, role: str) -> PinRef | None:
    """Parse a ``{"component": str, "pin": str}`` object; None if malformed."""
    if not isinstance(raw, Mapping):
        return None
    component = raw.get("component")
    pin = raw.get("pin")
    if not isinstance(component, str) or not isinstance(pin, str):
        return None
    return PinRef(component=component, pin=pin)


def _parse_components(raw: object) -> tuple[Component, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise SchemaError("INVALID_DOCUMENT", "'components' must be a JSON array")
    out: list[Component] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise SchemaError("INVALID_DOCUMENT", "every component must be a JSON object")
        comp_id = entry.get("id")
        comp_type = entry.get("type")
        if not isinstance(comp_id, str) or not comp_id:
            raise SchemaError("INVALID_DOCUMENT", "every component needs a non-empty string 'id'")
        if not isinstance(comp_type, str) or not comp_type:
            raise SchemaError("INVALID_DOCUMENT", f"component {comp_id!r} needs a non-empty string 'type'")
        raw_params = entry.get("params", {})
        if raw_params is None:
            raw_params = {}
        if not isinstance(raw_params, Mapping):
            raise SchemaError("INVALID_DOCUMENT", f"component {comp_id!r}: 'params' must be an object")
        params = {str(k): v for k, v in raw_params.items()}

        label = entry.get("label")
        label = label if isinstance(label, str) else None

        position: tuple[float, float] | None = None
        raw_pos = entry.get("position")
        if isinstance(raw_pos, Mapping):
            try:
                position = (float(raw_pos["x"]), float(raw_pos["y"]))
            except (KeyError, TypeError, ValueError):
                position = None

        out.append(Component(id=comp_id, type=comp_type, params=params, label=label, position=position))
    return tuple(out)


def _parse_nets(raw: object) -> tuple[Net, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise SchemaError("INVALID_DOCUMENT", "'nets' must be a JSON array")
    out: list[Net] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise SchemaError("INVALID_DOCUMENT", "every net must be a JSON object")
        net_id = entry.get("id")
        if not isinstance(net_id, str) or not net_id:
            raise SchemaError("INVALID_DOCUMENT", "every net needs a non-empty string 'id'")
        driver = _parse_pin_ref(entry.get("driver"), net_id, "driver")
        raw_sinks = entry.get("sinks", [])
        if not isinstance(raw_sinks, Sequence) or isinstance(raw_sinks, (str, bytes)):
            raise SchemaError("INVALID_DOCUMENT", f"net {net_id!r}: 'sinks' must be an array")
        sinks: list[PinRef] = []
        for sink_raw in raw_sinks:
            ref = _parse_pin_ref(sink_raw, net_id, "sink")
            if ref is None:
                raise SchemaError(
                    "INVALID_DOCUMENT",
                    f"net {net_id!r}: every sink must be {{component, pin}} strings",
                )
            sinks.append(ref)
        out.append(Net(id=net_id, driver=driver, sinks=tuple(sinks)))
    return tuple(out)


def parse_circuit(raw: object) -> CircuitGraph:
    """Parse a circuit JSON document (schema v1) into a :class:`CircuitGraph`.

    Raises :class:`SchemaError` (code ``UNSUPPORTED_SCHEMA_VERSION`` or
    ``INVALID_DOCUMENT``) for document-level structural problems. Semantic issues are
    the job of ``logic_engine.validation.validate``.
    """
    doc = _require_mapping(raw, "circuit document")
    version = doc.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SchemaError(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"expected schema_version {SCHEMA_VERSION}, got {version!r}",
        )
    name = doc.get("name")
    name = name if isinstance(name, str) else None
    if "components" not in doc or "nets" not in doc:
        raise SchemaError("INVALID_DOCUMENT", "'components' and 'nets' arrays are required")
    components = _parse_components(doc["components"])
    nets = _parse_nets(doc["nets"])
    return CircuitGraph(schema_version=SCHEMA_VERSION, name=name, components=components, nets=nets)


def circuit_to_dict(graph: CircuitGraph) -> dict[str, object]:
    """Serialize a graph back to schema-v1 JSON (used for hashing and persistence)."""
    components: list[object] = []
    for comp in graph.components:
        entry: dict[str, object] = {"id": comp.id, "type": comp.type}
        if comp.params:
            entry["params"] = dict(comp.params)
        if comp.label is not None:
            entry["label"] = comp.label
        if comp.position is not None:
            entry["position"] = {"x": comp.position[0], "y": comp.position[1]}
        components.append(entry)
    nets: list[object] = []
    for net in graph.nets:
        net_entry: dict[str, object] = {
            "id": net.id,
            "driver": ({"component": net.driver.component, "pin": net.driver.pin} if net.driver else None),
            "sinks": [{"component": s.component, "pin": s.pin} for s in net.sinks],
        }
        nets.append(net_entry)
    doc: dict[str, object] = {
        "schema_version": graph.schema_version,
        "components": components,
        "nets": nets,
    }
    if graph.name is not None:
        doc["name"] = graph.name
    return doc
