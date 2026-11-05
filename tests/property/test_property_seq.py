"""Property tests: sequential tick loop vs an independent naive evaluator.

The naive evaluator walks the raw document recursively per cycle (no settle-network
derivation, no v1 simulator reuse) and applies the same characteristic tables. The
property under test is the *orchestration* — settle/async/capture/commit ordering —
not the tables themselves (those are exhaustively unit-tested against the doc).
"""

from __future__ import annotations

import string
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from logic_engine import LogicValue
from logic_engine.hashing import canonical_json
from logic_engine.simulator import simulation_result_to_dict  # noqa: F401 - used implicitly
from logic_engine.values import BINARY_FUNCS, buffer_, not_
from sequential_engine import simulate_sequential

_0, _1 = LogicValue.ZERO, LogicValue.ONE
BIT = st.sampled_from(["0", "1"])


def _pin_value(
    doc: dict[str, Any],
    comp_by_id: dict[str, Any],
    ref: dict[str, str],
    state: dict[str, str],
    vector: dict[str, str],
) -> LogicValue:
    """Evaluate a driver pin recursively (independent of the settle-network trick)."""
    comp = comp_by_id[ref["component"]]
    ctype = comp["type"]
    if ctype == "INPUT":
        return LogicValue(vector.get(comp["params"]["name"], "X"))
    if ctype == "CONST0":
        return _0
    if ctype == "CONST1":
        return _1
    if ctype in ("DFF", "TFF", "JKFF", "SRFF"):
        q = LogicValue(state[f"{ref['component']}.q"])
        return not_(q) if ref["pin"] == "qn" else q
    if ctype == "OUTPUT":
        raise ValueError("OUTPUT has no driver role here")

    net_of_pin = doc["_net_of_pin"]
    if ctype == "NOT":
        return not_(
            _pin_value(
                doc, comp_by_id, net_of_pin[(ref["component"], "a")]["driver"], state, vector
            )
        )
    if ctype == "BUFFER":
        return buffer_(
            _pin_value(
                doc, comp_by_id, net_of_pin[(ref["component"], "a")]["driver"], state, vector
            )
        )
    params = comp.get("params", {}) or {}
    width = params.get("width", 2)
    if not isinstance(width, int) or isinstance(width, bool):
        width = 2
    pins = list(string.ascii_lowercase[:width])
    values = [
        _pin_value(doc, comp_by_id, net_of_pin[(comp["id"], pin)]["driver"], state, vector)
        for pin in pins
    ]
    func = BINARY_FUNCS[ctype]
    acc = values[0]
    for v in values[1:]:
        acc = func(acc, v)
    return acc


def _ff_next(ctype: str, capture: dict[str, LogicValue], q: LogicValue) -> LogicValue:
    from sequential_engine.flipflops import dff_next, jkff_next, srff_next, tff_next

    if ctype == "DFF":
        return dff_next(capture["d"])
    if ctype == "TFF":
        return tff_next(capture["t"], q)
    if ctype == "JKFF":
        return jkff_next(capture["j"], capture["k"], q)
    return srff_next(capture["s"], capture["r"], q)


def _naive_sequential(
    doc: dict[str, Any], cycles: int, inputs_per_cycle: list[dict[str, str]]
) -> list[dict[str, str]]:
    comp_by_id = {c["id"]: c for c in doc["components"]}
    net_of_pin: dict[tuple[str, str], dict[str, Any]] = {}
    for net in doc["nets"]:
        for sink in net["sinks"]:
            net_of_pin[(sink["component"], sink["pin"])] = net
    doc["_net_of_pin"] = net_of_pin

    ff_ids = [c["id"] for c in doc["components"] if c["type"] in ("DFF", "TFF", "JKFF", "SRFF")]
    state: dict[str, str] = {f"{fid}.q": "0" for fid in ff_ids}
    observed: list[dict[str, str]] = []

    input_names = sorted(
        c["params"]["name"]
        for c in doc["components"]
        if c["type"] == "INPUT" and not c["id"].startswith(("SQ:", "SP:"))
    )

    for cycle in range(cycles):
        vector = dict(inputs_per_cycle[cycle]) if cycle < len(inputs_per_cycle) else {}
        full_vector = {name: vector.get(name, "X") for name in input_names}

        # async: evaluate async pins by recursive eval, override before capture
        for fid in ff_ids:
            pre = _pin_value(
                doc, comp_by_id, net_of_pin[(fid, "pre")]["driver"], state, full_vector
            )
            clr = _pin_value(
                doc, comp_by_id, net_of_pin[(fid, "clr")]["driver"], state, full_vector
            )
            from sequential_engine.flipflops import async_apply

            override = async_apply(pre, clr)
            if override is not None:
                state[f"{fid}.q"] = override.value

        # capture
        nxt: dict[str, str] = {}
        for fid in ff_ids:
            ctype = comp_by_id[fid]["type"]
            capture: dict[str, LogicValue] = {}
            for pin in {"DFF": ("d",), "TFF": ("t",), "JKFF": ("j", "k"), "SRFF": ("s", "r")}[
                ctype
            ]:
                capture[pin] = _pin_value(
                    doc, comp_by_id, net_of_pin[(fid, pin)]["driver"], state, full_vector
                )
            nxt[f"{fid}.q"] = _ff_next(ctype, capture, LogicValue(state[f"{fid}.q"])).value

        observed.append(dict(state))
        state = nxt

    return observed


@st.composite
def dff_networks(draw: st.DrawFn) -> tuple[dict[str, Any], int, list[dict[str, str]]]:
    n_ffs = draw(st.integers(min_value=1, max_value=3))
    n_inputs = draw(st.integers(min_value=1, max_value=2))
    cycles = draw(st.integers(min_value=1, max_value=6))
    use_inputs = draw(st.booleans())

    components: list[dict[str, Any]] = [{"id": "C0", "type": "CONST0"}]
    nets: list[dict[str, Any]] = []
    input_names = [f"x{i}" for i in range(n_inputs)]
    for name in input_names:
        components.append({"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}})

    ff_ids = [f"F{i}" for i in range(n_ffs)]
    taps: list[tuple[str, str]] = [(f"F{i}", "qn") for i in range(n_ffs)]
    taps += [(f"IN_{name}", "out") for name in input_names]

    for fid in ff_ids:
        components.append({"id": fid, "type": "DFF"})
        nets.append(
            {
                "id": f"n_{fid}_pre",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": fid, "pin": "pre"}],
            }
        )
        nets.append(
            {
                "id": f"n_{fid}_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": fid, "pin": "clr"}],
            }
        )
        # d = NOT(source) (keeps the DAG dense and exercises inversion feedback)
        source = draw(st.sampled_from(taps))
        components.append({"id": f"N_{fid}", "type": "NOT"})
        nets.append(
            {
                "id": f"n_src_{fid}",
                "driver": {"component": source[0], "pin": source[1]},
                "sinks": [{"component": f"N_{fid}", "pin": "a"}],
            }
        )
        nets.append(
            {
                "id": f"n_d_{fid}",
                "driver": {"component": f"N_{fid}", "pin": "out"},
                "sinks": [{"component": fid, "pin": "d"}],
            }
        )
        taps.append((f"N_{fid}", "out"))

    inputs_per_cycle = []
    if use_inputs:
        for _ in range(cycles):
            row = {name: draw(BIT) for name in input_names}
            inputs_per_cycle.append(row)

    doc = {"schema_version": 2, "name": "gen_seq", "components": components, "nets": nets}
    return doc, cycles, inputs_per_cycle


@given(data=dff_networks())
@settings(max_examples=150, deadline=None)
def test_sequential_matches_naive_evaluator(
    data: tuple[dict[str, Any], int, list[dict[str, str]]],
) -> None:
    doc, cycles, inputs_per_cycle = data
    result = simulate_sequential(doc, cycles, inputs_per_cycle)
    expected_observed = _naive_sequential(doc, cycles, inputs_per_cycle)
    actual_observed = [row.state for row in result.cycles]
    assert actual_observed == expected_observed, canonical_json(
        {"cycles": cycles, "inputs": inputs_per_cycle}
    )
