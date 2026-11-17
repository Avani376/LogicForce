"""Complete v2 validation (v1 codes + sequential additions).

Normative codes: ``docs/semantics/circuit-graph-schema.md`` (v1) and
``docs/semantics/circuit-graph-schema-v2.md`` (additions). Validation is complete,
not fail-fast. State components *cut* combinational cycles: a cycle is an error
only when it passes through no state component.
"""

from __future__ import annotations

from collections.abc import Mapping

from logic_engine.components import ALLOWED_PARAMS, Component, component_kind
from logic_engine.components import SUPPORTED_TYPES as V1_TYPES
from logic_engine.graph import Net, PinRef
from logic_engine.validation import ValidationIssue, ValidationReport

from sequential_engine.graph import (
    MULTI_BIT_TYPES,
    RESERVED_ID_PREFIXES,
    SUPPORTED_SEQUENTIAL_TYPES,
    StateComponentSpec,
    input_pins_for_seq,
    output_pins_for_seq,
    resolve_state_spec,
    state_width,
)
from sequential_engine.version import MAX_STATE_WIDTH

ALL_TYPES = frozenset({*V1_TYPES, *SUPPORTED_SEQUENTIAL_TYPES})

#: params allowed per v2 type (v1 types reuse the v1 table).
V2_PARAM_ALLOWANCE: dict[str, frozenset[str]] = {
    **{ff: frozenset() for ff in SUPPORTED_SEQUENTIAL_TYPES if ff not in MULTI_BIT_TYPES},
    "REGISTER": frozenset({"width"}),
    "COUNTER": frozenset({"width"}),
}


def validate_sequential(components: list[Component], nets: list[Net], name: str | None) -> ValidationReport:
    """Validate a parsed v2 circuit; returns the complete report."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # --- ids and types ----------------------------------------------------------
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for comp in components:
        if comp.id in seen_ids:
            duplicate_ids.add(comp.id)
        seen_ids.add(comp.id)
    for comp_id in sorted(duplicate_ids):
        errors.append(
            ValidationIssue(
                code="DUPLICATE_COMPONENT_ID",
                message=f"component id {comp_id!r} is used more than once",
                component_id=comp_id,
            )
        )
    for comp in components:
        for prefix in RESERVED_ID_PREFIXES:
            if comp.id.startswith(prefix):
                errors.append(
                    ValidationIssue(
                        code="RESERVED_IO_NAME",
                        message=(f"component id {comp.id!r} uses the reserved {prefix!r} namespace"),
                        component_id=comp.id,
                    )
                )
                break

    comp_by_id: dict[str, object] = {}
    for comp in components:
        comp_by_id.setdefault(comp.id, comp)

    state_specs: dict[str, StateComponentSpec] = {}
    io_names: dict[str, list[str]] = {"input": [], "output": []}
    for comp in components:
        ctype = comp.type
        cid = comp.id
        if ctype not in ALL_TYPES:
            errors.append(
                ValidationIssue(
                    code="UNKNOWN_COMPONENT_TYPE",
                    message=f"component {cid!r} has unsupported type {ctype!r}",
                    component_id=cid,
                )
            )
            continue
        allowed = V2_PARAM_ALLOWANCE.get(ctype) or ALLOWED_PARAMS.get(ctype, frozenset())
        for param_name in sorted(comp.params):
            if param_name not in allowed:
                errors.append(
                    ValidationIssue(
                        code="INVALID_PARAM",
                        message=(
                            f"component {cid!r} ({ctype}) does not accept param "
                            f"{param_name!r}; allowed: {sorted(allowed)}"
                        ),
                        component_id=cid,
                    )
                )
        if ctype in MULTI_BIT_TYPES:
            width = state_width(comp)
            if width is None:
                errors.append(
                    ValidationIssue(
                        code="INVALID_STATE_WIDTH",
                        message=(
                            f"component {cid!r}: 'width' must be an integer in "
                            f"[1, {MAX_STATE_WIDTH}], got "
                            f"{comp.params.get('width')!r}"
                        ),
                        component_id=cid,
                    )
                )
        spec = resolve_state_spec(comp)
        if spec is not None:
            state_specs[cid] = spec
        kind = component_kind(ctype)
        if kind in ("input", "output"):
            raw_name = comp.params.get("name")
            if raw_name is None:
                errors.append(
                    ValidationIssue(
                        code="MISSING_PARAM",
                        message=f"{kind} component {cid!r} requires param 'name'",
                        component_id=cid,
                    )
                )
            elif not isinstance(raw_name, str) or not raw_name:
                errors.append(
                    ValidationIssue(
                        code="INVALID_PARAM",
                        message=(f"{kind} component {cid!r}: 'name' must be a non-empty string"),
                        component_id=cid,
                    )
                )
            else:
                for prefix in RESERVED_ID_PREFIXES:
                    if raw_name.startswith(prefix):
                        errors.append(
                            ValidationIssue(
                                code="RESERVED_IO_NAME",
                                message=(f"{kind} name {raw_name!r} uses the reserved {prefix!r} namespace"),
                                component_id=cid,
                            )
                        )
                        break
                io_names[kind].append(raw_name)

    for kind in ("input", "output"):
        names = io_names[kind]
        dupes = sorted({n for n in names if names.count(n) > 1})
        for name_value in dupes:
            errors.append(
                ValidationIssue(
                    code="DUPLICATE_IO_NAME",
                    message=f"duplicate {kind} name {name_value!r}",
                )
            )

    # --- pin capability maps ----------------------------------------------------
    in_pins: dict[str, frozenset[str]] = {}
    out_pins: dict[str, frozenset[str]] = {}
    for comp in components:
        cid = comp.id
        if cid in in_pins or comp.type not in ALL_TYPES:
            continue
        seq_in = input_pins_for_seq(comp)
        seq_out = output_pins_for_seq(comp)
        if seq_in is None or seq_out is None:
            continue
        in_pins[cid] = frozenset(seq_in)
        out_pins[cid] = frozenset(seq_out)

    def known_output_pin(ref: PinRef) -> bool:
        return ref.component in out_pins and ref.pin in out_pins[ref.component]

    def known_input_pin(ref: PinRef) -> bool:
        return ref.component in in_pins and ref.pin in in_pins[ref.component]

    # --- nets -------------------------------------------------------------------
    seen_net_ids: set[str] = set()
    duplicate_net_ids: set[str] = set()
    for net in nets:
        if net.id in seen_net_ids:
            duplicate_net_ids.add(net.id)
        seen_net_ids.add(net.id)
    for net_id in sorted(duplicate_net_ids):
        errors.append(
            ValidationIssue(
                code="DUPLICATE_NET_ID",
                message=f"net id {net_id!r} is used more than once",
                net_id=net_id,
            )
        )

    input_pin_owner: dict[PinRef, str] = {}
    connected_input_pins: set[PinRef] = set()
    for net in nets:
        if net.id in duplicate_net_ids:
            continue
        if net.driver is None:
            errors.append(
                ValidationIssue(
                    code="MULTI_DRIVER_NET",
                    message=(f"net {net.id!r} has no driver; every net needs exactly one output-pin driver"),
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
                        code="UNKNOWN_STATE_PIN" if sink.component in state_specs else "UNKNOWN_PIN_REFERENCE",
                        message=(
                            f"net {net.id!r} sink {sink.component}.{sink.pin} is not "
                            "an input pin of an existing component"
                        ),
                        component_id=sink.component,
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
                            f"{input_pin_owner[sink]!r} and {net.id!r}"
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
    for comp_id, pins in in_pins.items():
        for pin in sorted(pins):
            if PinRef(component=comp_id, pin=pin) not in connected_input_pins:
                errors.append(
                    ValidationIssue(
                        code="DANGLING_INPUT_PIN",
                        message=f"input pin {comp_id}.{pin} is not connected to any net",
                        component_id=comp_id,
                    )
                )

    # --- combinational cycle detection (state components cut cycles) ------------
    errors.extend(_detect_combinational_cycles(nets, state_specs, in_pins, input_pin_owner))

    return ValidationReport(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def _detect_combinational_cycles(
    nets: list[Net],
    state_specs: Mapping[str, StateComponentSpec],
    in_pins: Mapping[str, frozenset[str]],
    input_pin_owner: Mapping[PinRef, str],
) -> tuple[ValidationIssue, ...]:
    """Kahn over combinational components; state outputs break the edges."""
    net_by_id: dict[str, Net] = {}
    for net in nets:
        if net.id not in net_by_id:
            net_by_id[net.id] = net

    combinational = {cid for cid in in_pins if cid not in state_specs}
    adjacency: dict[str, set[str]] = {cid: set() for cid in combinational}
    indegree: dict[str, int] = {cid: 0 for cid in combinational}
    for comp_id in combinational:
        for pin in in_pins[comp_id]:
            net_id = input_pin_owner.get(PinRef(component=comp_id, pin=pin))
            if net_id is None:
                continue
            net = net_by_id[net_id]
            if net.driver is None:
                continue
            driver_id = net.driver.component
            if driver_id in combinational and comp_id not in adjacency[driver_id]:
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

    remaining = sorted(combinational - processed)
    if not remaining:
        return ()
    return (
        ValidationIssue(
            code="COMBINATIONAL_LOOP",
            message=(
                "combinational dependency cycle through components (state "
                "components would cut cycles; this one does not): " + ", ".join(remaining)
            ),
        ),
    )
