"""Behavior-preserving transformation classes (normative: optimization.md).

Each function scans a circuit document for one transformation pattern and applies
the FIRST match in deterministic component-id order, returning a new document plus
a description — or the original document unchanged. Pure: inputs never mutated.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import cast

from logic_engine.components import (
    TYPE_BUFFER,
    TYPE_CONST0,
    TYPE_CONST1,
    TYPE_INPUT,
    TYPE_NOT,
    TYPE_OUTPUT,
    input_pins_for,
)


def _as_sinks(net: dict[str, object]) -> list[dict[str, object]]:
    sinks = net.get("sinks", [])
    return cast("list[dict[str, object]]", sinks if isinstance(sinks, list) else [])


def _as_params(comp: dict[str, object]) -> dict[str, object]:
    raw = comp.get("params", {}) or {}
    return cast("dict[str, object]", raw if isinstance(raw, dict) else {})


def _as_driver(net: dict[str, object]) -> dict[str, object] | None:
    driver = net.get("driver")
    return cast("dict[str, object] | None", driver if isinstance(driver, dict) else None)


def _unique_id(existing: set[str], base: str) -> str:
    candidate = base
    suffix = 0
    while candidate in existing:
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate


_GATE_TYPES = ("AND", "OR", "NAND", "NOR", "XOR", "XNOR", "BUFFER")


class _View:
    """Indexed access over a circuit document (single source for the helpers)."""

    def __init__(self, doc: Mapping[str, object]) -> None:
        self.doc = copy.deepcopy(dict(doc))
        raw_components = self.doc.get("components", [])
        raw_nets = self.doc.get("nets", [])
        component_list = raw_components if isinstance(raw_components, list) else []
        net_list = raw_nets if isinstance(raw_nets, list) else []
        self.components: list[dict[str, object]] = [
            cast("dict[str, object]", c) for c in component_list if isinstance(c, dict)
        ]
        self.nets: list[dict[str, object]] = [cast("dict[str, object]", n) for n in net_list if isinstance(n, dict)]
        self.comp_by_id: dict[str, dict[str, object]] = {str(c["id"]): c for c in self.components}
        self.net_by_id: dict[str, dict[str, object]] = {str(n["id"]): n for n in self.nets}
        # (component, input pin) -> feeding net
        self.feed: dict[tuple[str, str], dict[str, object]] = {}
        for net in self.nets:
            for sink in _as_sinks(net):
                self.feed[(str(sink["component"]), str(sink["pin"]))] = net

    def export(self) -> dict[str, object]:
        self.doc["components"] = self.components
        self.doc["nets"] = self.nets
        return self.doc

    def is_const(self, component_id: str) -> str | None:
        comp = self.comp_by_id.get(component_id)
        if comp is None:
            return None
        if comp.get("type") == TYPE_CONST0:
            return "0"
        if comp.get("type") == TYPE_CONST1:
            return "1"
        return None

    def gate_input_nets(self, component_id: str) -> list[dict[str, object]]:
        comp = self.comp_by_id[component_id]
        comp_type = cast("str", comp.get("type"))
        pins = input_pins_for(comp_type, _as_params(comp))
        nets: list[dict[str, object]] = []
        for pin in pins:
            net = self.feed.get((component_id, pin))
            if net is None:
                return []
            nets.append(net)
        return nets

    def out_net(self, component_id: str) -> dict[str, object] | None:
        for net in self.nets:
            driver = _as_driver(net)
            if driver is not None and str(driver.get("component")) == component_id:
                return net
        return None

    def driver_component_of(self, net: dict[str, object]) -> str | None:
        driver = _as_driver(net)
        return str(driver.get("component")) if driver is not None else None

    def remove_component_and_its_out_nets(self, component_id: str) -> None:
        """Remove a component, its output nets, and every sink referencing it.

        Sink cleanup matters for correctness: a removed gate's input-pin
        references would otherwise dangle as UNKNOWN_PIN_REFERENCE. Input nets
        left with zero sinks degrade to UNREAD_NET warnings (harmless)."""
        self.components = [c for c in self.components if str(c.get("id")) != component_id]
        cleaned_nets: list[dict[str, object]] = []
        for net in self.nets:
            driver = _as_driver(net)
            if driver is not None and str(driver.get("component")) == component_id:
                continue  # the component's own output net dies with it
            net["sinks"] = [s for s in _as_sinks(net) if str(s.get("component")) != component_id]
            cleaned_nets.append(net)
        self.nets = cleaned_nets
        self.comp_by_id.pop(component_id, None)
        # rebuild the feed index: removed sinks must vanish from it too
        self.feed = {}
        for net in self.nets:
            for sink in _as_sinks(net):
                self.feed[(str(sink["component"]), str(sink["pin"]))] = net

    def rewire_sinks(self, from_net: dict[str, object], to_net: dict[str, object]) -> None:
        _as_sinks(to_net).extend(_as_sinks(from_net))

    def drop_net(self, net: dict[str, object]) -> None:
        self.nets = [n for n in self.nets if n is not net]

    def replace_driver_with_constant(self, net_id: str, value: str) -> str:
        """Replace a net's driver with a fresh constant; returns a description."""
        const_type = "CONST0" if value == "0" else "CONST1"
        const_id = _unique_id(set(self.comp_by_id), f"OPT_CONST_{net_id}")
        self.components.append({"id": const_id, "type": const_type})
        self.net_by_id[net_id]["driver"] = {"component": const_id, "pin": "out"}
        return f"output of net {net_id} re-driven by {const_id}"

    def replace_gate_with_not(self, gate_id: str, source_net_id: str) -> str:
        """Replace a gate with a NOT over ``source_net_id``, REUSING the gate's out
        net (re-point its driver before removal so the net survives)."""
        out_net = self.out_net(gate_id)
        if out_net is None:
            return ""
        not_id = _unique_id(set(self.comp_by_id), f"OPT_NOT_{gate_id}")
        self.components.append({"id": not_id, "type": TYPE_NOT})
        out_net["driver"] = {"component": not_id, "pin": "out"}
        self.remove_component_and_its_out_nets(gate_id)
        source_net = self.net_by_id[source_net_id]
        _as_sinks(source_net).extend([{"component": not_id, "pin": "a"}])
        return f"{gate_id} replaced by NOT ({not_id})"

    def passthrough(self, gate_id: str, source_net: dict[str, object]) -> str:
        """Re-wire the consumers of a gate's output to ``source_net`` and drop it."""
        out_net = self.out_net(gate_id)
        if out_net is None:
            return ""
        self.rewire_sinks(out_net, source_net)
        self.remove_component_and_its_out_nets(gate_id)
        self.drop_net(out_net)
        return f"{gate_id} removed (pass-through)"


def _net_id(view: _View, net: dict[str, object]) -> str:
    return str(net["id"])


def _driver_signature(view: _View, net: dict[str, object]) -> tuple[str, str] | None:
    """What a net CARRIES: its driver pin. Two nets driven by the same source pin
    carry the same value — that is what duplicate merging must compare (not net
    ids, which differ even when electrically identical)."""
    driver = _as_driver(net)
    if driver is None:
        return ("<none>", "<none>")
    return (str(driver.get("component")), str(driver.get("pin")))


def _out_net_id(view: _View, gate_id: str) -> str:
    out_net = view.out_net(gate_id)
    return _net_id(view, out_net) if out_net is not None else ""


def _fold_constant_gate(view: _View, gate_id: str, gate_type: str, input_nets: list[dict[str, object]]) -> str | None:
    """Dominance folding for gates with constant inputs (per optimization.md)."""
    values = [view.is_const(view.driver_component_of(net) or "") for net in input_nets]
    out_net_id = _out_net_id(view, gate_id)
    if gate_type in ("AND", "OR", "NAND", "NOR"):
        dominant = {"AND": "0", "OR": "1", "NAND": "0", "NOR": "1"}[gate_type]
        neutral = {"AND": "1", "OR": "0", "NAND": "1", "NOR": "0"}[gate_type]
        dominant_result = {"AND": "0", "OR": "1", "NAND": "1", "NOR": "0"}[gate_type]
        if any(value == dominant for value in values):
            description = view.replace_driver_with_constant(out_net_id, dominant_result)
            view.remove_component_and_its_out_nets(gate_id)
            return f"constant_fold: {gate_type} {gate_id} had a {dominant} input — {description}"
        non_constant = [i for i, value in enumerate(values) if value is None]
        all_constant = all(value is not None for value in values)
        all_neutral = all(value == neutral for value in values if value is not None)
        if all_constant and all_neutral:
            folded = "1" if gate_type in ("AND", "NOR") else "0"
            description = view.replace_driver_with_constant(out_net_id, folded)
            view.remove_component_and_its_out_nets(gate_id)
            return f"constant_fold: {gate_type} {gate_id} had all-{neutral} inputs — {description}"
        if (
            len(non_constant) == 1
            and len(values) >= 2
            and all(value == neutral for i, value in enumerate(values) if i != non_constant[0])
        ):
            signal_net = input_nets[non_constant[0]]
            if gate_type in ("AND", "OR"):
                description = f"constant_fold: {gate_type} {gate_id} neutral input removed — " + view.passthrough(
                    gate_id, signal_net
                )
                return description
            description = f"constant_fold: {gate_type} {gate_id} became an inverter — " + view.replace_gate_with_not(
                gate_id, _net_id(view, signal_net)
            )
            return description
        return None
    if gate_type in ("XOR", "XNOR") and len(values) == 2:
        invert = gate_type == "XNOR"
        if values[0] is None and values[1] is None:
            return None
        if values[0] == values[1]:
            return None  # both constant: a constant-only XOR is not a v1 rewrite
        constant_position = 0 if values[0] is not None else 1
        constant_value = values[constant_position]
        signal_net = input_nets[1 - constant_position]
        identity = (constant_value == "0") != invert  # XOR:0 / XNOR:1 pass through
        if identity:
            description = (
                f"constant_fold: {gate_type} {gate_id} with CONST{constant_value} input — "
                + view.passthrough(gate_id, signal_net)
            )
            return description
        description = (
            f"constant_fold: {gate_type} {gate_id} with CONST{constant_value} input inverted — "
            + view.replace_gate_with_not(gate_id, _net_id(view, signal_net))
        )
        return description
    return None


def _apply_one(doc: Mapping[str, object]) -> tuple[dict[str, object], str] | None:
    """Find and apply the first applicable transformation (class order:
    double_negation, buffer_elimination, constant_fold, duplicate_merge; each
    scanned in component-id order)."""
    view = _View(doc)

    # double_negation: NOT driven by NOT
    for gate_id in sorted(view.comp_by_id):
        comp = view.comp_by_id[gate_id]
        if comp.get("type") != TYPE_NOT:
            continue
        input_net = view.gate_input_nets(gate_id)
        if len(input_net) != 1:
            continue
        inner_id = view.driver_component_of(input_net[0])
        if inner_id is None or view.comp_by_id.get(inner_id, {}).get("type") != TYPE_NOT:
            continue
        inner_input_net = view.gate_input_nets(inner_id)
        if len(inner_input_net) != 1:
            continue
        out_net = view.out_net(gate_id)
        if out_net is None:
            continue
        view.rewire_sinks(out_net, inner_input_net[0])
        view.remove_component_and_its_out_nets(gate_id)
        view.drop_net(out_net)
        return view.export(), f"double_negation: NOT(NOT) chain through {gate_id} removed"

    # buffer_elimination
    for gate_id in sorted(view.comp_by_id):
        comp = view.comp_by_id[gate_id]
        if comp.get("type") != TYPE_BUFFER:
            continue
        input_net = view.gate_input_nets(gate_id)
        if len(input_net) != 1:
            continue
        description = f"buffer_elimination: buffer {gate_id} removed — " + view.passthrough(gate_id, input_net[0])
        return view.export(), description

    # constant_fold
    for gate_id in sorted(view.comp_by_id):
        comp = view.comp_by_id[gate_id]
        gate_type = str(comp.get("type"))
        if gate_type in ("AND", "OR", "NAND", "NOR", "XOR", "XNOR"):
            input_nets = view.gate_input_nets(gate_id)
            expected = len(input_pins_for(gate_type, _as_params(comp)))
            if len(input_nets) != expected:
                continue
            fold_result = _fold_constant_gate(view, gate_id, gate_type, input_nets)
            if fold_result is not None:
                return view.export(), fold_result

    # dead_gate_elimination: gates/constants whose output net has no sinks
    for gate_id in sorted(view.comp_by_id):
        comp = view.comp_by_id[gate_id]
        ctype = str(comp.get("type"))
        if ctype in (TYPE_INPUT, TYPE_OUTPUT):
            continue
        out_net = view.out_net(gate_id)
        if out_net is not None and len(_as_sinks(out_net)) == 0:
            view.remove_component_and_its_out_nets(gate_id)
            return (
                view.export(),
                f"dead_gate_elimination: unread {ctype} {gate_id} removed",
            )

    # duplicate_merge: same type + identical input-net ids (scan-local signatures)
    seen: dict[tuple[str, tuple[tuple[str, str] | None, ...]], str] = {}
    for gate_id in sorted(view.comp_by_id):
        comp = view.comp_by_id[gate_id]
        gate_type = str(comp.get("type"))
        if gate_type not in _GATE_TYPES:
            continue
        input_nets = view.gate_input_nets(gate_id)
        expected = len(input_pins_for(gate_type, _as_params(comp)))
        if len(input_nets) != expected:
            continue
        signature_key = (
            gate_type,
            tuple(_driver_signature(view, n) for n in input_nets),
        )
        keeper_id = seen.get(signature_key)
        if keeper_id is None:
            seen[signature_key] = gate_id
            continue
        keeper_out = view.out_net(keeper_id)
        if keeper_out is None:
            continue
        description = f"duplicate_merge: {gate_type} {gate_id} merged into {keeper_id} — " + view.passthrough(
            gate_id, keeper_out
        )
        return view.export(), description
    return None


def apply_one_transformation(
    doc: Mapping[str, object],
) -> tuple[dict[str, object], str] | None:
    """Apply the first applicable v1 transformation; returns (new doc, description).

    Deterministic: component-id order within a fixed class order. Returns None
    when no v1 transformation applies. The input document is never mutated.
    """
    return _apply_one(doc)
