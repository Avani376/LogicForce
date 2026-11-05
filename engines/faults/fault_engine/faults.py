"""Fault operators: pure document->document transformations (faults-and-repair.md).

The nominal model is never mutated. Applying the same fault to the same model
yields a byte-identical faulty model. Application errors are typed
(``FAULT_SCHEMA_ERROR`` / ``FAULT_TARGET_NOT_FOUND`` / ``FAULT_APPLICATION_ERROR``).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import cast

from logic_engine import SchemaError
from logic_engine.components import SUPPORTED_TYPES as V1_TYPES
from logic_engine.components import input_pins_for

from fault_engine.version import FAULT_SCHEMA_VERSION

FSM_OPERATORS = ("transition_redirect", "transition_remove", "output_flip")
COMB_OPERATORS = ("gate_swap", "stuck_at")
ALL_OPERATORS = (*FSM_OPERATORS, *COMB_OPERATORS)

FAULT_MODEL_KINDS = ("fsm", "combinational")


def parse_fault(raw: object) -> dict[str, object]:
    """Validate a fault document (schema 1) and return it as a plain dict."""
    if not isinstance(raw, Mapping):
        raise SchemaError("FAULT_SCHEMA_ERROR", "fault document must be a JSON object")
    version = raw.get("fault_schema_version")
    if version != FAULT_SCHEMA_VERSION:
        raise SchemaError(
            "FAULT_SCHEMA_ERROR",
            f"expected fault_schema_version {FAULT_SCHEMA_VERSION}, got {version!r}",
        )
    fault_id = raw.get("id")
    if not isinstance(fault_id, str) or not fault_id:
        raise SchemaError("FAULT_SCHEMA_ERROR", "'id' must be a non-empty string")
    operator = raw.get("operator")
    if operator not in ALL_OPERATORS:
        raise SchemaError(
            "FAULT_SCHEMA_ERROR",
            f"'operator' must be one of {list(ALL_OPERATORS)}, got {operator!r}",
        )
    target = raw.get("target")
    if not isinstance(target, Mapping):
        raise SchemaError("FAULT_SCHEMA_ERROR", "'target' must be an object")
    params = raw.get("params", {})
    if not isinstance(params, Mapping):
        raise SchemaError("FAULT_SCHEMA_ERROR", "'params' must be an object")
    return {
        "fault_schema_version": FAULT_SCHEMA_VERSION,
        "id": fault_id,
        "operator": operator,
        "target": dict(target),
        "params": dict(params),
    }


def _fault_int(target: Mapping[str, object], key: str) -> int:
    value = target.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError("FAULT_TARGET_NOT_FOUND", f"target.{key} must be an integer index")
    return value


def _fault_str(mapping: Mapping[str, object], key: str, error: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise SchemaError(error, f"{key} must be a non-empty string")
    return value


def _apply_fsm(model: Mapping[str, object], fault: Mapping[str, object]) -> dict[str, object]:
    faulty = copy.deepcopy(dict(model))
    transitions_raw = faulty.get("transitions")
    if not isinstance(transitions_raw, list):
        raise SchemaError("FAULT_APPLICATION_ERROR", "FSM model has no transitions array")
    transitions = cast("list[dict[str, object]]", transitions_raw)
    states = faulty.get("states")
    outputs = faulty.get("outputs")
    operator = str(fault["operator"])
    target = cast("dict[str, object]", fault["target"])
    params = cast("dict[str, object]", fault["params"])

    if operator in ("transition_redirect", "transition_remove", "output_flip"):
        index = _fault_int(target, "transition_index")
        if not 0 <= index < len(transitions):
            raise SchemaError(
                "FAULT_TARGET_NOT_FOUND",
                f"transition_index {index} out of range ({len(transitions)} transitions)",
            )
        transition = transitions[index]

        if operator == "transition_redirect":
            new_to = params.get("to")
            if new_to is not None:
                if not isinstance(states, list) or new_to not in states:
                    raise SchemaError(
                        "FAULT_APPLICATION_ERROR",
                        f"redirect target {new_to!r} is not a declared state",
                    )
                transition["to"] = new_to
            set_outputs = params.get("set_outputs")
            if set_outputs is not None:
                if not isinstance(set_outputs, Mapping):
                    raise SchemaError("FAULT_APPLICATION_ERROR", "set_outputs must be an object")
                outputs_map = cast("dict[str, object]", transition.setdefault("outputs", {}))
                for name, value in set_outputs.items():
                    if not isinstance(outputs, list) or name not in outputs:
                        raise SchemaError(
                            "FAULT_APPLICATION_ERROR",
                            f"set_outputs names unknown output {name!r}",
                        )
                    if value not in ("0", "1"):
                        raise SchemaError(
                            "FAULT_APPLICATION_ERROR",
                            f"set_outputs values must be '0' or '1', got {name}={value!r}",
                        )
                    outputs_map[name] = value
            if new_to is None and set_outputs is None:
                raise SchemaError(
                    "FAULT_APPLICATION_ERROR",
                    "transition_redirect requires 'to' and/or 'set_outputs' params",
                )
            return faulty

        if operator == "transition_remove":
            transitions.pop(index)
            return faulty

        # output_flip
        output_name = params.get("output")
        if not isinstance(output_name, str):
            raise SchemaError("FAULT_APPLICATION_ERROR", "output_flip requires params.output")
        if not isinstance(outputs, list) or output_name not in outputs:
            raise SchemaError(
                "FAULT_APPLICATION_ERROR",
                f"output {output_name!r} is not a declared output",
            )
        outputs_map = cast("dict[str, object]", transition.setdefault("outputs", {}))
        current = outputs_map.get(output_name)
        if current not in ("0", "1"):
            raise SchemaError(
                "FAULT_APPLICATION_ERROR",
                f"output {output_name!r} on transition {index} is "
                f"{current!r}; only binary values can be flipped",
            )
        outputs_map[output_name] = "1" if current == "0" else "0"
        return faulty

    raise SchemaError("FAULT_APPLICATION_ERROR", f"operator {operator!r} not valid for FSM")


def _apply_comb(model: Mapping[str, object], fault: Mapping[str, object]) -> dict[str, object]:
    faulty = copy.deepcopy(dict(model))
    components_raw = faulty.get("components")
    nets_raw = faulty.get("nets")
    if not isinstance(components_raw, list) or not isinstance(nets_raw, list):
        raise SchemaError("FAULT_APPLICATION_ERROR", "circuit model is malformed")
    components = cast("list[dict[str, object]]", components_raw)
    nets = cast("list[dict[str, object]]", nets_raw)
    operator = str(fault["operator"])
    target = cast("dict[str, object]", fault["target"])
    params = cast("dict[str, object]", fault["params"])

    if operator == "gate_swap":
        component_id = _fault_str(target, "component_id", "FAULT_TARGET_NOT_FOUND")
        new_type = _fault_str(params, "to", "FAULT_APPLICATION_ERROR")
        if new_type not in V1_TYPES:
            raise SchemaError(
                "FAULT_APPLICATION_ERROR",
                f"swap target type {new_type!r} is not a supported component type",
            )
        for component in components:
            if isinstance(component, Mapping) and component.get("id") == component_id:
                component["type"] = new_type
                component.pop("params", None)  # width/name params rarely survive a swap
                if new_type in ("INPUT", "OUTPUT"):
                    raise SchemaError(
                        "FAULT_APPLICATION_ERROR",
                        "gate_swap cannot produce primary I/O components",
                    )
                return faulty
        raise SchemaError("FAULT_TARGET_NOT_FOUND", f"component {component_id!r} does not exist")

    # stuck_at: rewire the target input pin to a fresh constant.
    component_id = _fault_str(target, "component_id", "FAULT_TARGET_NOT_FOUND")
    pin = _fault_str(target, "pin", "FAULT_TARGET_NOT_FOUND")
    value = params.get("value")
    if value not in ("0", "1"):
        raise SchemaError("FAULT_APPLICATION_ERROR", "stuck_at requires params.value '0' or '1'")
    target_component = None
    for component in components:
        if isinstance(component, Mapping) and component.get("id") == component_id:
            target_component = component
            break
    if target_component is None:
        raise SchemaError("FAULT_TARGET_NOT_FOUND", f"component {component_id!r} does not exist")
    ctype = target_component.get("type")
    params_map = target_component.get("params", {}) or {}
    if not isinstance(params_map, Mapping):
        params_map = {}
    input_pins = input_pins_for(str(ctype), dict(params_map))
    if pin not in input_pins:
        raise SchemaError(
            "FAULT_APPLICATION_ERROR",
            f"pin {component_id}.{pin} is not an input pin (stuck_at applies to input pins only)",
        )

    # detach any existing feed of this pin
    for net in nets:
        if isinstance(net, Mapping):
            sinks = net.get("sinks")
            if isinstance(sinks, list):
                net["sinks"] = [
                    s
                    for s in sinks
                    if not (
                        isinstance(s, Mapping)
                        and s.get("component") == component_id
                        and s.get("pin") == pin
                    )
                ]

    const_type = "CONST0" if value == "0" else "CONST1"
    base = f"STUCK_{component_id}_{pin}"
    const_id = base
    suffix = 0
    existing_ids = {c.get("id") for c in components if isinstance(c, Mapping)}
    while const_id in existing_ids:
        suffix += 1
        const_id = f"{base}_{suffix}"
    components.append({"id": const_id, "type": const_type})
    net_id_base = f"n_stuck_{component_id}_{pin}"
    net_id = net_id_base
    suffix = 0
    existing_nets = {n.get("id") for n in nets if isinstance(n, Mapping)}
    while net_id in existing_nets:
        suffix += 1
        net_id = f"{net_id_base}_{suffix}"
    nets.append(
        {
            "id": net_id,
            "driver": {"component": const_id, "pin": "out"},
            "sinks": [{"component": component_id, "pin": pin}],
        }
    )
    return faulty


def apply_fault(
    model_kind: str, model: Mapping[str, object], fault: Mapping[str, object]
) -> dict[str, object]:
    """Apply a fault document to a model document, returning the faulty model.

    The nominal model is deep-copied, never mutated. ``model_kind`` is
    ``"fsm"`` or ``"combinational"`` and must be consistent with the fault's
    operator family.
    """
    validated_fault = parse_fault(fault)
    operator = str(validated_fault["operator"])
    if model_kind == "fsm":
        if operator not in FSM_OPERATORS:
            raise SchemaError(
                "FAULT_APPLICATION_ERROR",
                f"operator {operator!r} does not apply to FSM models",
            )
        return _apply_fsm(model, validated_fault)
    if model_kind == "combinational":
        if operator not in COMB_OPERATORS:
            raise SchemaError(
                "FAULT_APPLICATION_ERROR",
                f"operator {operator!r} does not apply to combinational models",
            )
        return _apply_comb(model, validated_fault)
    raise SchemaError(
        "FAULT_SCHEMA_ERROR",
        f"model_kind must be one of {list(FAULT_MODEL_KINDS)}, got {model_kind!r}",
    )
