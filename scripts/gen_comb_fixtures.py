"""Generate golden fixtures for combinational library circuits (Phase C4).

Provenance: expected truth tables from closed-form definitions, never from the engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "fixtures_comb"


def _input(name):
    return {"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}}


def _output(name):
    return {"id": f"OUT_{name}", "type": "OUTPUT", "params": {"name": name}}


_CONST0 = {"id": "C0", "type": "CONST0"}


def _NET(nid, drv, sinks):
    return {
        "id": nid,
        "driver": {"component": drv, "pin": "out"},
        "sinks": [{"component": c, "pin": p} for c, p in sinks],
    }


def full_adder() -> tuple[dict, list[str], list[str], Any]:
    b = {
        "schema_version": 1,
        "name": "full_adder",
        "components": [
            _input("a"),
            _input("b"),
            _input("cin"),
            {"id": "X1", "type": "XOR"},
            {"id": "X2", "type": "XOR"},
            {"id": "A1", "type": "AND"},
            {"id": "A2", "type": "AND"},
            {"id": "O1", "type": "OR"},
            _output("sum"),
            _output("carry"),
        ],
        "nets": [
            _NET("n_a1", "IN_a", [("X1", "a"), ("A1", "a")]),
            _NET("n_b1", "IN_b", [("X1", "b"), ("A1", "b")]),
            _NET("n_x1", "X1", [("X2", "a"), ("A2", "a")]),
            _NET("n_cin", "IN_cin", [("X2", "b"), ("A2", "b")]),
            _NET("n_a2", "A1", [("O1", "a")]),
            _NET("n_a3", "A2", [("O1", "b")]),
            _NET("n_sum", "X2", [("OUT_sum", "in")]),
            _NET("n_cout", "O1", [("OUT_carry", "in")]),
        ],
    }

    def fn(bits: dict[str, int]) -> dict[str, int]:
        a, bb, c = bits["a"], bits["b"], bits["cin"]
        return {"sum": a ^ bb ^ c, "carry": (a & bb) | (a & c) | (bb & c)}

    inputs, outputs = ["a", "b", "cin"], ["sum", "carry"]
    return b, inputs, outputs, fn


def binary_to_gray() -> tuple[dict, list[str], list[str], Any]:
    w = 4
    comps: list[dict] = [_input(f"b{i}") for i in range(w)]
    nets: list[dict] = []
    for i in range(w):
        comps.append(_output(f"g{i}"))
    # g0 = b0, gi = b[i-1] XOR b[i]
    comps.append({"id": "X0", "type": "XOR"})
    nets.append(_NET("n_b0_g", "IN_b0", [("X0", "a"), ("OUT_g0", "in")]))
    nets.append(_NET("n_b1_g", "IN_b1", [("X0", "b")]))
    for i in range(1, w):
        if i > 1:
            comps.append({"id": f"W{i}", "type": "BUFFER"})
            nets.append(_NET(f"n_buf{i}", f"IN_b{i}", [(f"W{i}", "a")]))
            nets.append(_NET(f"n_w{i}", f"W{i}", [(f"OUT_g{i}", "in")]))
        else:
            nets.append(_NET(f"n_direct{i}", f"IN_b{i}", [(f"OUT_g{i}", "in")]))
    # g0 = b0 ^ b1, g1 = b1 ^ b2, g2 = b2 ^ b3, g3 = b3
    # fix: redo properly
    comps = [_input(f"b{i}") for i in range(w)]
    nets = []
    for i in range(w):
        comps.append(_output(f"g{i}"))
    comps.insert(w, {"id": "X01", "type": "XOR"})
    comps.insert(w + 1, {"id": "X12", "type": "XOR"})
    comps.insert(w + 2, {"id": "X23", "type": "XOR"})
    nets = [
        _NET("n_b0", "IN_b0", [("X01", "a"), ("OUT_g3", "in")]),
        _NET("n_b1", "IN_b1", [("X01", "b"), ("X12", "a"), ("OUT_g2", "in")]),
        _NET("n_b2", "IN_b2", [("X12", "b"), ("X23", "a"), ("OUT_g1", "in")]),
        _NET("n_b3", "IN_b3", [("X23", "b"), ("OUT_g0", "in")]),
        _NET("n_x01", "X01", []),
        _NET("n_x12", "X12", []),
        _NET("n_x23", "X23", []),
    ]

    def fn(bits: dict[str, int]) -> dict[str, int]:
        b = [bits[f"b{i}"] for i in range(w)]
        g = [b[i] ^ b[i + 1] for i in range(w - 1)] + [b[w - 1]]
        return {f"g{i}": g[i] for i in range(w)}

    # fix outputs to g0..g3
    comps = [_input(f"b{i}") for i in range(w)]
    for i in range(w):
        comps.append(_output(f"g{i}"))
    comps += [{"id": "X01", "type": "XOR"}, {"id": "X12", "type": "XOR"}, {"id": "X23", "type": "XOR"}]
    nets = [
        _NET("n_b0", "IN_b0", [("X01", "a"), ("OUT_g3", "in")]),
        _NET("n_b1", "IN_b1", [("X01", "b"), ("X12", "a"), ("OUT_g2", "in")]),
        _NET("n_b2", "IN_b2", [("X12", "b"), ("X23", "a"), ("OUT_g1", "in")]),
        _NET("n_b3", "IN_b3", [("X23", "b"), ("OUT_g0", "in")]),
        _NET("n_x01", "X01", []),
        _NET("n_x12", "X12", []),
        _NET("n_x23", "X23", []),
    ]
    inputs = [f"b{i}" for i in range(w)]
    outputs = [f"g{i}" for i in range(w)]

    def fn(bits: dict[str, int]) -> dict[str, int]:
        b = [bits[f"b{i}"] for i in range(w)]
        g = [b[i] ^ b[i + 1] for i in range(w - 1)] + [b[w - 1]]
        return {f"g{i}": g[i] for i in range(w)}

    return _doc("binary_to_gray", comps, nets), inputs, outputs, fn


def parity_generator(w: int = 4) -> tuple[dict, list[str], list[str], Any]:
    comps: list[dict] = [_input(f"d{i}") for i in range(w)]
    nets: list[dict] = []
    comps.append({"id": "X0", "type": "XOR"})
    nets.append(_NET("n_d0", "IN_d0", [("X0", "a")]))
    nets.append(_NET("n_d1", "IN_d1", [("X0", "b")]))
    for i in range(2, w):
        comps.append({"id": f"X{i - 1}", "type": "XOR"})
        nets.append(_NET(f"n_x{i - 1}", f"X{i - 2}", [(f"X{i - 1}", "a")]))
        nets.append(_NET(f"n_d{i}", f"IN_d{i}", [(f"X{i - 1}", "b")]))
    comps.append(_output("parity"))
    nets.append(_NET("n_par", f"X{w - 2}", [("OUT_parity", "in")]))

    def fn(bits: dict[str, int]) -> dict[str, int]:
        total = 0
        for i in range(w):
            total ^= bits[f"d{i}"]
        return {"parity": total}

    inputs = [f"d{i}" for i in range(w)]
    return _doc("parity_gen", comps, nets), inputs, ["parity"], fn


def mux_4to1() -> tuple[dict, list[str], list[str], Any]:
    comps: list[dict[str, object]] = [
        _input("d0"),
        _input("d1"),
        _input("d2"),
        _input("d3"),
        _input("s0"),
        _input("s1"),
        {"id": "N_s0", "type": "NOT"},
        {"id": "N_s1", "type": "NOT"},
        {"id": "A0", "type": "AND"},
        {"id": "A1", "type": "AND"},
        {"id": "A2", "type": "AND"},
        {"id": "A3", "type": "AND"},
        {"id": "O", "type": "OR", "params": {"width": 4}},
        _output("y"),
    ]
    nets: list[dict[str, object]] = [
        _NET("n_s0", "IN_s0", [("N_s0", "a"), ("A1", "a"), ("A3", "a")]),
        _NET("n_ns0", "N_s0", [("A0", "a"), ("A2", "a")]),
        _NET("n_s1", "IN_s1", [("N_s1", "a"), ("A2", "b"), ("A3", "b")]),
        _NET("n_ns1", "N_s1", [("A0", "b"), ("A1", "b")]),
        _NET("n_d0", "IN_d0", [("A0", "c")]),
        _NET("n_d1", "IN_d1", [("A1", "c")]),
        _NET("n_d2", "IN_d2", [("A2", "c")]),
        _NET("n_d3", "IN_d3", [("A3", "c")]),
        _NET("n_a0", "A0", [("O", "a")]),
        _NET("n_a1", "A1", [("O", "b")]),
        _NET("n_a2", "A2", [("O", "c")]),
        _NET("n_a3", "A3", [("O", "d")]),
        _NET("n_y", "O", [("OUT_y", "in")]),
    ]

    def fn(bits: dict[str, int]) -> dict[str, int]:
        sel = bits["s1"] * 2 + bits["s0"]
        return {"y": bits[f"d{sel}"]}

    inputs = ["d0", "d1", "d2", "d3", "s0", "s1"]
    return _doc("mux_4to1", comps, nets), inputs, ["y"], fn


def _doc(name: str, comps: list, nets: list) -> dict:
    return {"schema_version": 1, "name": name, "components": comps, "nets": nets}


def _expected_rows(inputs: list[str], outputs: list[str], fn: Any) -> list[dict[str, str]]:
    rows = []
    for i in range(1 << len(inputs)):
        bits = {name: (i >> (len(inputs) - 1 - pos)) & 1 for pos, name in enumerate(inputs)}
        out_bits = fn(bits)
        rows.append(
            {"inputs": {n: str(bits[n]) for n in inputs}, "outputs": {n: str(out_bits[n]) for n in sorted(outputs)}}
        )
    return rows


FIXTURES: dict[str, Any] = {
    "comb_full_adder": full_adder,
    "comb_binary_to_gray": binary_to_gray,
    "comb_parity_gen": parity_generator,
    "comb_mux_4to1": mux_4to1,
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, factory in FIXTURES.items():
        doc, inputs, outputs, fn = factory()
        rows = _expected_rows(inputs, outputs, fn)
        fixture = {"circuit": doc, "expected": {"rows": rows}}
        (FIXTURES_DIR / f"{name}.json").write_text(json.dumps(fixture, indent=2) + "\n")
        print(f"wrote {name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
