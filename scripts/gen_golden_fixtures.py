"""Generate golden fixture circuits and expected truth tables.

Provenance rule: expected tables are computed here from **closed-form reference
definitions** (the independent specification of each circuit's function), NOT by
running the simulation engine. Golden tests then compare engine output against these
committed fixtures, so an engine bug cannot silently rewrite its own oracle.

Run from the repository root:
    .venv/Scripts/python scripts/gen_golden_fixtures.py
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "fixtures"

Bit = int
Bits = dict[str, Bit]


def _input(name: str) -> dict[str, object]:
    return {"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}}


def _output(name: str) -> dict[str, object]:
    return {"id": f"OUT_{name}", "type": "OUTPUT", "params": {"name": name}}


class Builder:
    """Assembles a schema-v1 circuit document with deterministic net ids."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.components: list[dict[str, object]] = []
        self.nets: list[dict[str, object]] = []
        self._counter = 0

    def add(self, comp_id: str, comp_type: str, **params: object) -> str:
        entry: dict[str, object] = {"id": comp_id, "type": comp_type}
        if params:
            entry["params"] = dict(params)
        self.components.append(entry)
        return comp_id

    def input(self, name: str) -> str:
        self.components.append(_input(name))
        return f"IN_{name}"

    def output(self, name: str) -> str:
        self.components.append(_output(name))
        return f"OUT_{name}"

    def wire(self, driver: str, sinks: list[tuple[str, str]]) -> str:
        """Wire ``driver.out`` to sink pins; an output pin may feed several nets."""
        self._counter += 1
        net_id = f"n{self._counter:02d}_from_{driver}"
        self.nets.append(
            {
                "id": net_id,
                "driver": {"component": driver, "pin": "out"},
                "sinks": [
                    {"component": comp, "pin": pin} for comp, pin in sinks
                ],
            }
        )
        return net_id

    def doc(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "name": self.name,
            "components": self.components,
            "nets": self.nets,
        }


def half_adder() -> tuple[dict[str, object], list[str], list[str], Callable[[Bits], Bits]]:
    b = Builder("half_adder")
    a, bb = b.input("a"), b.input("b")
    gx = b.add("G_xor", "XOR")
    ga = b.add("G_and", "AND")
    out_sum, out_cout = b.output("sum"), b.output("carry_out")
    b.wire(a, [(gx, "a"), (ga, "a")])
    b.wire(bb, [(gx, "b"), (ga, "b")])
    b.wire(gx, [(out_sum, "in")])
    b.wire(ga, [(out_cout, "in")])

    def definition(bits: Bits) -> Bits:
        return {"sum": bits["a"] ^ bits["b"], "carry_out": bits["a"] & bits["b"]}

    return b.doc(), ["a", "b"], ["sum", "carry_out"], definition


def full_adder() -> tuple[dict[str, object], list[str], list[str], Callable[[Bits], Bits]]:
    b = Builder("full_adder")
    a, bb, cin = b.input("a"), b.input("b"), b.input("cin")
    gx = b.add("G_xor1", "XOR")
    gx2 = b.add("G_xor2", "XOR")
    ga = b.add("G_and1", "AND")
    ga2 = b.add("G_and2", "AND")
    go = b.add("G_or", "OR")
    out_sum, out_cout = b.output("sum"), b.output("carry_out")
    b.wire(a, [(gx, "a"), (ga, "a")])
    b.wire(bb, [(gx, "b"), (ga, "b")])
    b.wire(cin, [(gx2, "b"), (ga2, "b")])
    b.wire(gx, [(gx2, "a"), (ga2, "a")])
    b.wire(ga, [(go, "a")])
    b.wire(ga2, [(go, "b")])
    b.wire(gx2, [(out_sum, "in")])
    b.wire(go, [(out_cout, "in")])

    def definition(bits: Bits) -> Bits:
        a_, b_, c_ = bits["a"], bits["b"], bits["cin"]
        return {
            "sum": a_ ^ b_ ^ c_,
            "carry_out": (a_ & b_) | (a_ & c_) | (b_ & c_),
        }

    return b.doc(), ["a", "b", "cin"], ["sum", "carry_out"], definition


def mux2() -> tuple[dict[str, object], list[str], list[str], Callable[[Bits], Bits]]:
    b = Builder("mux2to1")
    in0, in1, sel = b.input("in0"), b.input("in1"), b.input("sel")
    nsel = b.add("G_notsel", "NOT")
    w0 = b.add("G_and0", "AND")
    w1 = b.add("G_and1", "AND")
    o = b.add("G_or", "OR")
    out = b.output("out")
    b.wire(sel, [(nsel, "a"), (w1, "b")])
    b.wire(nsel, [(w0, "b")])
    b.wire(in0, [(w0, "a")])
    b.wire(in1, [(w1, "a")])
    b.wire(w0, [(o, "a")])
    b.wire(w1, [(o, "b")])
    b.wire(o, [(out, "in")])

    def definition(bits: Bits) -> Bits:
        return {"out": bits["in1"] if bits["sel"] else bits["in0"]}

    return b.doc(), ["in0", "in1", "sel"], ["out"], definition


def mux4() -> tuple[dict[str, object], list[str], list[str], Callable[[Bits], Bits]]:
    """4:1 mux as a tree of three 2:1 muxes; ``in`` selection index = 2*s1 + s0."""
    b = Builder("mux4to1")
    in0, in1, in2, in3 = (b.input(f"in{i}") for i in range(4))
    s0, s1 = b.input("s0"), b.input("s1")
    ns0 = b.add("G_nots0", "NOT")
    ns1 = b.add("G_nots1", "NOT")
    b.wire(s0, [(ns0, "a")])
    b.wire(s1, [(ns1, "a")])
    # Low mux: selects between in0 (s0=0) and in1 (s0=1).
    a1 = b.add("G_and_i0", "AND")
    a2 = b.add("G_and_i1", "AND")
    o1 = b.add("G_or_lo", "OR")
    b.wire(in0, [(a1, "a")])
    b.wire(ns0, [(a1, "b")])
    b.wire(in1, [(a2, "a")])
    b.wire(s0, [(a2, "b")])
    b.wire(a1, [(o1, "a")])
    b.wire(a2, [(o1, "b")])
    # High mux: selects between in2 (s0=0) and in3 (s0=1).
    a3 = b.add("G_and_i2", "AND")
    a4 = b.add("G_and_i3", "AND")
    o2 = b.add("G_or_hi", "OR")
    b.wire(in2, [(a3, "a")])
    b.wire(ns0, [(a3, "b")])
    b.wire(in3, [(a4, "a")])
    b.wire(s0, [(a4, "b")])
    b.wire(a3, [(o2, "a")])
    b.wire(a4, [(o2, "b")])
    # Select between the two halves on s1.
    a5 = b.add("G_and_lo", "AND")
    a6 = b.add("G_and_hi", "AND")
    out_or = b.add("G_or_out", "OR")
    b.wire(o1, [(a5, "a")])
    b.wire(ns1, [(a5, "b")])
    b.wire(o2, [(a6, "a")])
    b.wire(s1, [(a6, "b")])
    b.wire(a5, [(out_or, "a")])
    b.wire(a6, [(out_or, "b")])
    out = b.output("out")
    b.wire(out_or, [(out, "in")])

    def definition(bits: Bits) -> Bits:
        channels = [bits["in0"], bits["in1"], bits["in2"], bits["in3"]]
        return {"out": channels[(bits["s1"] << 1) | bits["s0"]]}

    return b.doc(), ["in0", "in1", "in2", "in3", "s0", "s1"], ["out"], definition


def decoder2to4() -> tuple[dict[str, object], list[str], list[str], Callable[[Bits], Bits]]:
    """Active-high-enable 2:4 decoder with 3-input AND gates (exercises width > 2)."""
    b = Builder("decoder2to4")
    en, s0, s1 = b.input("E"), b.input("s0"), b.input("s1")
    ns0 = b.add("G_nots0", "NOT")
    ns1 = b.add("G_nots1", "NOT")
    b.wire(s0, [(ns0, "a")])
    b.wire(s1, [(ns1, "a")])
    y_ids: list[str] = []
    for i in range(4):
        gate = b.add(f"G_and_y{i}", "AND", width=3)
        b.wire(en, [(gate, "a")])
        b.wire(ns1 if not ((i >> 1) & 1) else s1, [(gate, "b")])
        b.wire(ns0 if not (i & 1) else s0, [(gate, "c")])
        y_ids.append(gate)
    outs = [b.output(f"y{i}") for i in range(4)]
    for gate_id, out_id in zip(y_ids, outs, strict=True):
        b.wire(gate_id, [(out_id, "in")])

    def definition(bits: Bits) -> Bits:
        active = 2 * bits["s1"] + bits["s0"]
        return {f"y{i}": 1 if (bits["E"] and i == active) else 0 for i in range(4)}

    return b.doc(), ["E", "s0", "s1"], [f"y{i}" for i in range(4)], definition


def expected_rows(
    input_names: list[str],
    output_names: list[str],
    definition: Callable[[Bits], Bits],
) -> list[dict[str, object]]:
    """Enumerate rows exactly like the contract: sorted names, first name = MSB."""
    inputs_sorted = sorted(input_names)
    rows: list[dict[str, object]] = []
    for index in range(1 << len(inputs_sorted)):
        bits: Bits = {
            name: (index >> (len(inputs_sorted) - 1 - position)) & 1
            for position, name in enumerate(inputs_sorted)
        }
        out_bits = definition(bits)
        rows.append(
            {
                "inputs": {name: str(bits[name]) for name in inputs_sorted},
                "outputs": {name: str(out_bits[name]) for name in sorted(output_names)},
            }
        )
    return rows


_Factory = Callable[
    [], tuple[dict[str, object], list[str], list[str], Callable[[Bits], Bits]]
]

FIXTURES: dict[str, _Factory] = {
    "half_adder": half_adder,
    "full_adder": full_adder,
    "mux2to1": mux2,
    "mux4to1": mux4,
    "decoder2to4": decoder2to4,
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, factory in FIXTURES.items():
        doc, inputs, outputs, definition = factory()
        fixture = {
            "circuit": doc,
            "expected": {
                "input_names": sorted(inputs),
                "output_names": sorted(outputs),
                "rows": expected_rows(inputs, outputs, definition),
            },
        }
        path = FIXTURES_DIR / f"{name}.json"
        path.write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {path.name}: {len(fixture['expected']['rows'])} expected rows")


if __name__ == "__main__":
    main()
