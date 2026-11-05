"""Complete circuit validation.

Normative source: ``docs/semantics/circuit-graph-schema.md`` (authoritative code table).
Validation is *complete, not fail-fast*: one call returns every error and warning found.
``ok`` is true iff there are zero errors; warnings never block simulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from logic_engine.components import (
    ALLOWED_PARAMS,
    MULTI_INPUT_GATES,
    SUPPORTED_TYPES,
    TYPE_CONST0,
    TYPE_CONST1,
    TYPE_INPUT,
    component_kind,
    input_pins_for,
    output_pins_for,
)
from logic_engine.errors import CircuitNotValidError
from logic_engine.graph import CircuitGraph, Net, PinRef
from logic_engine.version import MAX_GATE_WIDTH


@dataclass(frozen=True)
class ValidationIssue:
    """One validation finding, with optional component/net attribution."""

    code: str
    message: str
    component_id: str | None = None
    net_id: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Complete validation result. ``ok`` is true iff ``errors`` is empty."""

    ok: bool
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]


def _sorted_unique(items: list[str]) -> list[str]:
    return sorted(set(items))


def validate(graph: CircuitGraph) -> ValidationReport:
    """Validate a parsed circuit graph; returns the complete report."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # --- component-level checks -------------------------------------------------
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for comp in graph.components:
        if comp.id in seen_ids:
            duplicate_ids.add(comp.id)
        seen_ids.add(comp.id)
    for comp_id in _sorted_unique(list(duplicate_ids)):
        errors.append(
            ValidationIssue(
                code="DUPLICATE_COMPONENT_ID",
                message=f"component id {comp_id!r} is used more than once",
                component_id=comp_id,
            )
        )

    io_names: dict[str, list[str]] = {"input": [], "output": []}
    for comp in graph.components:
        if comp.type not in SUPPORTED_TYPES:
            errors.append(
                ValidationIssue(
                    code="UNKNOWN_COMPONENT_TYPE",
                    message=f"component {comp.id!r} has unsupported type {comp.type!r}",
                    component_id=comp.id,
                )
            )
            continue
        allowed = ALLOWED_PARAMS[comp.type]
        for param_name in sorted(comp.params):
            if param_name not in allowed:
                errors.append(
                    ValidationIssue(
                        code="INVALID_PARAM",
                        message=(
                            f"component {comp.id!r} ({comp.type}) does not accept "
                            f"param {param_name!r}; allowed: {sorted(allowed)}"
                        ),
                        component_id=comp.id,
                    )
                )
        kind = component_kind(comp.type)
        if kind in ("input", "output"):
            raw_name = comp.params.get("name")
            if raw_name is None:
                errors.append(
                    ValidationIssue(
                        code="MISSING_PARAM",
                        message=f"{kind} component {comp.id!r} requires param 'name'",
                        component_id=comp.id,
                    )
                )
            elif not isinstance(raw_name, str) or not raw_name:
                errors.append(
                    ValidationIssue(
                        code="INVALID_PARAM",
                        message=(
                            f"{kind} component {comp.id!r}: 'name' must be a non-empty string"
                        ),
                        component_id=comp.id,
                    )
                )
            else:
                io_names[kind].append(raw_name)
        if comp.type in MULTI_INPUT_GATES and "width" in comp.params:
            raw_width = comp.params["width"]
            if (
                isinstance(raw_width, bool)
                or not isinstance(raw_width, int)
                or not 2 <= raw_width <= MAX_GATE_WIDTH
            ):
                errors.append(
                    ValidationIssue(
                        code="INVALID_PARAM",
                        message=(
                            f"component {comp.id!r}: 'width' must be an integer in "
                            f"[2, {MAX_GATE_WIDTH}], got {raw_width!r}"
                        ),
                        component_id=comp.id,
                    )
                )

    for kind in ("input", "output"):
        names = io_names[kind]
        dupes = _sorted_unique([n for n in names if names.count(n) > 1])
        for name in dupes:
            errors.append(
                ValidationIssue(
                    code="DUPLICATE_IO_NAME",
                    message=f"duplicate {kind} name {name!r}",
                )
            )

    # --- pin capability maps (first occurrence wins for duplicate ids; those
    # components are already reported as errors, so the choice is irrelevant) ----
    comp_type_of: dict[str, str] = {}
    comp_params_of: dict[str, dict[str, object]] = {}
    in_pins: dict[str, frozenset[str]] = {}
    out_pins: dict[str, frozenset[str]] = {}
    for comp in graph.components:
        if comp.id in comp_type_of or comp.type not in SUPPORTED_TYPES:
            continue
        comp_type_of[comp.id] = comp.type
        comp_params_of[comp.id] = comp.params
        in_pins[comp.id] = frozenset(input_pins_for(comp.type, comp.params))
        out_pins[comp.id] = frozenset(output_pins_for(comp.type))

    def known_output_pin(ref: PinRef) -> bool:
        return ref.component in out_pins and ref.pin in out_pins[ref.component]

    def known_input_pin(ref: PinRef) -> bool:
        return ref.component in in_pins and ref.pin in in_pins[ref.component]

    # --- net-level checks -------------------------------------------------------
    seen_net_ids: set[str] = set()
    duplicate_net_ids: set[str] = set()
    for net in graph.nets:
        if net.id in seen_net_ids:
            duplicate_net_ids.add(net.id)
        seen_net_ids.add(net.id)
    for net_id in _sorted_unique(list(duplicate_net_ids)):
        errors.append(
            ValidationIssue(
                code="DUPLICATE_NET_ID",
                message=f"net id {net_id!r} is used more than once",
                net_id=net_id,
            )
        )

    input_pin_owner: dict[PinRef, str] = {}
    connected_input_pins: set[PinRef] = set()
    for net in graph.nets:
        if net.id in duplicate_net_ids:
            continue
        if net.driver is None:
            errors.append(
                ValidationIssue(
                    code="MULTI_DRIVER_NET",
                    message=(
                        f"net {net.id!r} has no driver; every net needs exactly one "
                        "output-pin driver"
                    ),
                    net_id=net.id,
                )
            )
        elif not known_output_pin(net.driver):
            errors.append(
                ValidationIssue(
                    code="UNKNOWN_PIN_REFERENCE",
                    message=(
                        f"net {net.id!r} driver "
                        f"{net.driver.component}.{net.driver.pin} is not an output "
                        "pin of an existing component"
                    ),
                    net_id=net.id,
                )
            )
        for sink in net.sinks:
            if not known_input_pin(sink):
                errors.append(
                    ValidationIssue(
                        code="UNKNOWN_PIN_REFERENCE",
                        message=(
                            f"net {net.id!r} sink {sink.component}.{sink.pin} is not "
                            "an input pin of an existing component"
                        ),
                        net_id=net.id,
                    )
                )
                continue
            if sink in input_pin_owner and input_pin_owner[sink] != net.id:
                errors.append(
                    ValidationIssue(
                        code="MULTI_DRIVER_NET",
                        message=(
                            f"input pin {sink.component}.{sink.pin} is fed by nets "
                            f"{input_pin_owner[sink]!r} and {net.id!r}; an input pin "
                            "must be fed by exactly one net"
                        ),
                        component_id=sink.component,
                        net_id=net.id,
                    )
                )
            elif sink not in input_pin_owner:
                input_pin_owner[sink] = net.id
                connected_input_pins.add(sink)

        if len(net.sinks) == 0:
            warnings.append(
                ValidationIssue(
                    code="UNREAD_NET",
                    message=f"net {net.id!r} is driven but read by no input pin",
                    net_id=net.id,
                )
            )

    # --- dangling input pins ----------------------------------------------------
    for comp_id in comp_type_of:
        for pin in sorted(in_pins[comp_id]):
            if PinRef(component=comp_id, pin=pin) not in connected_input_pins:
                errors.append(
                    ValidationIssue(
                        code="DANGLING_INPUT_PIN",
                        message=(f"input pin {comp_id}.{pin} is not connected to any net"),
                        component_id=comp_id,
                    )
                )

    # --- combinational cycle detection (Kahn over known components) -------------
    errors.extend(_detect_cycles(graph.nets, comp_type_of, in_pins, input_pin_owner))

    return ValidationReport(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def _detect_cycles(
    nets: tuple[Net, ...],
    comp_type_of: Mapping[str, str],
    in_pins: Mapping[str, frozenset[str]],
    input_pin_owner: Mapping[PinRef, str],
) -> tuple[ValidationIssue, ...]:
    """Kahn's algorithm; leftovers form the reported cycle set."""
    net_by_id: dict[str, Net] = {}
    for net in nets:
        if net.id not in net_by_id:
            net_by_id[net.id] = net

    adjacency: dict[str, set[str]] = {cid: set() for cid in comp_type_of}
    indegree: dict[str, int] = {cid: 0 for cid in comp_type_of}
    for comp_id, comp_type in comp_type_of.items():
        if comp_type in (TYPE_INPUT, TYPE_CONST0, TYPE_CONST1):
            continue
        for pin in in_pins[comp_id]:
            net_id = input_pin_owner.get(PinRef(component=comp_id, pin=pin))
            if net_id is None:
                continue
            net = net_by_id[net_id]
            if net.driver is None:
                continue
            driver_id = net.driver.component
            if driver_id not in adjacency:
                continue
            if comp_id not in adjacency[driver_id]:
                adjacency[driver_id].add(comp_id)
                indegree[comp_id] += 1

    ready = sorted(cid for cid, deg in indegree.items() if deg == 0)
    processed: set[str] = set()
    while ready:
        current = ready.pop(0)
        processed.add(current)
        for downstream in sorted(adjacency[current]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                ready.append(downstream)
        ready.sort()

    remaining = sorted(set(comp_type_of) - processed)
    if not remaining:
        return ()
    return (
        ValidationIssue(
            code="COMBINATIONAL_LOOP",
            message=("combinational dependency cycle through components: " + ", ".join(remaining)),
        ),
    )


def require_valid(graph: CircuitGraph) -> ValidationReport:
    """Validate and raise :class:`CircuitNotValidError` if the report has errors.

    Kept separate from ``validate`` so callers that want the full report (the API)
    and callers that want a hard gate (the simulator) share one code path.
    """
    report = validate(graph)
    if not report.ok:
        raise CircuitNotValidError(report)
    return report


__all__ = ["ValidationIssue", "ValidationReport", "validate", "require_valid"]
