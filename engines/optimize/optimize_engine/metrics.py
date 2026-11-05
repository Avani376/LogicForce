"""Abstract gate-level metrics (normative: optimization.md).

``logic_depth`` is the longest input→output path in gate levels — an abstract
structural metric, explicitly NOT a hardware delay claim.
"""

from __future__ import annotations

from logic_engine.components import (
    MULTI_INPUT_GATES,
    TYPE_BUFFER,
    TYPE_INPUT,
    TYPE_NOT,
    TYPE_OUTPUT,
    input_pins_for,
)
from logic_engine.graph import CircuitGraph

_GATE_TYPES = {TYPE_NOT, TYPE_BUFFER, *MULTI_INPUT_GATES}


def compute_metrics(graph: CircuitGraph) -> dict[str, int]:
    """Gate count, component count, and logic depth for a validated graph."""
    gate_count = 0
    depths: dict[str, int] = {}
    net_by_pin: dict[tuple[str, str], str] = {}
    net_driver: dict[str, object] = {}
    for net in graph.nets:
        net_driver[net.id] = net.driver
        for sink in net.sinks:
            net_by_pin.setdefault((sink.component, sink.pin), net.id)

    def driver_depth(ref: object) -> int:
        """Depth of a driving pin's component (primary inputs are depth 0)."""
        component_id = getattr(ref, "component", None)
        if component_id is None:
            return 0
        ctype = _type_of(graph, str(component_id))
        if ctype == TYPE_INPUT:
            return 0
        return component_depth(str(component_id))

    def component_depth(component_id: str) -> int:
        if component_id in depths:
            return depths[component_id]
        depths[component_id] = 0  # cycle guard (graph is validated acyclic)
        ctype = _type_of(graph, component_id)
        depth = 0
        if ctype not in (TYPE_INPUT, "CONST0", "CONST1"):
            pins = input_pins_for(ctype, _params_of(graph, component_id))
            for pin in pins:
                net_id = net_by_pin.get((component_id, pin))
                if net_id is None:
                    continue
                driver = net_driver.get(net_id)
                if driver is None:
                    continue
                candidate = driver_depth(driver) + 1
                if candidate > depth:
                    depth = candidate
        depths[component_id] = depth
        return depth

    component_count = 0
    for comp in graph.components:
        component_count += 1
        if comp.type in _GATE_TYPES:
            gate_count += 1
        component_depth(comp.id)

    output_depths = [
        depths.get(comp.id, 0) for comp in graph.components if comp.type == TYPE_OUTPUT
    ]
    logic_depth = max(output_depths, default=0)
    return {
        "gate_count": gate_count,
        "component_count": component_count,
        "logic_depth": logic_depth,
    }


def _type_of(graph: CircuitGraph, component_id: str) -> str:
    for comp in graph.components:
        if comp.id == component_id:
            return str(comp.type)
    return TYPE_INPUT


def _params_of(graph: CircuitGraph, component_id: str) -> dict[str, object]:
    for comp in graph.components:
        if comp.id == component_id:
            return dict(comp.params)
    return {}


def metrics_to_dict(metrics: dict[str, int]) -> dict[str, int]:
    return {
        "gate_count": metrics["gate_count"],
        "component_count": metrics["component_count"],
        "logic_depth": metrics["logic_depth"],
    }
