"""Generate sequential golden fixtures from closed-form reference definitions.

Provenance rule (same as the combinational fixtures): expected waveforms/events are
computed here from independent reference models (Johnson shift formula, mod-2^w
counter arithmetic, toggle relation) — never by running the engine.

Run: .venv/Scripts/python scripts/gen_sequential_fixtures.py
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "fixtures_seq"


def _const0(comp_id: str) -> dict[str, object]:
    return {"id": comp_id, "type": "CONST0"}


def _input(name: str) -> dict[str, object]:
    return {"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}}


def _output(name: str) -> dict[str, object]:
    return {"id": f"OUT_{name}", "type": "OUTPUT", "params": {"name": name}}


def _net(
    net_id: str, driver: str, driver_pin: str, sinks: list[tuple[str, str]]
) -> dict[str, object]:
    return {
        "id": net_id,
        "driver": {"component": driver, "pin": driver_pin},
        "sinks": [{"component": c, "pin": p} for c, p in sinks],
    }


def _doc(
    name: str, components: list[dict[str, object]], nets: list[dict[str, object]]
) -> dict[str, object]:
    return {"schema_version": 2, "name": name, "components": components, "nets": nets}


def _str_bits(bits: list[int]) -> str:
    return "".join(str(b) for b in bits)


def divide_by_2() -> tuple[
    dict[str, object], int, list[dict[str, str]], list[dict[str, object]], dict[str, str]
]:
    """DFF with qn -> d feedback toggles every edge (divide-by-two)."""
    components = [
        _const0("C0"),
        {"id": "FF1", "type": "DFF"},
        {"id": "N1", "type": "NOT"},
        _output("q"),
    ]
    nets = [
        _net("n_pre", "C0", "out", [("FF1", "pre")]),
        _net("n_clr", "C0", "out", [("FF1", "clr")]),
        _net("n_q", "FF1", "q", [("N1", "a"), ("OUT_q", "in")]),
        _net("n_qn", "FF1", "qn", []),
        _net("n_d", "N1", "out", [("FF1", "d")]),
    ]

    cycles = 6
    observed: list[dict[str, str]] = []
    q = 0
    events: list[dict[str, object]] = []
    for cycle in range(cycles):
        observed.append({"FF1.q": str(q), "q": str(q)})
        nxt = 1 - q
        events.append(
            {
                "cycle": cycle,
                "component": "FF1",
                "pin": "q",
                "old": str(q),
                "new": str(nxt),
                "cause": "clock_edge",
            }
        )
        q = nxt
    waveforms = {
        "FF1.q": [row["FF1.q"] for row in observed],
        "out:q": [row["q"] for row in observed],
    }
    final = {"FF1.q": str(q)}
    return (
        _doc("divide_by_2", components, nets),
        cycles,
        observed,
        events,
        {"waveforms": waveforms, "final_state": final},
    )


def johnson_counter() -> tuple[
    dict[str, object], int, list[dict[str, str]], list[dict[str, object]], dict[str, str]
]:
    """4-bit Johnson (twisted-ring) counter: d0=~q3, d1=q0, d2=q1, d3=q2."""
    width = 4
    components: list[dict[str, object]] = [_const0("C0")]
    nets: list[dict[str, object]] = []
    for i in range(width):
        components.append({"id": f"FF{i}", "type": "DFF"})
        components.append(_output(f"q{i}"))
        nets.append(_net(f"n_pre{i}", "C0", "out", [(f"FF{i}", "pre")]))
        nets.append(_net(f"n_clr{i}", "C0", "out", [(f"FF{i}", "clr")]))
    components.append({"id": "N1", "type": "NOT"})
    nets.append(_net("n_d0", "N1", "out", [("FF0", "d")]))
    for i in range(1, width):
        nets.append(_net(f"n_d{i}", f"FF{i - 1}", "q", [(f"FF{i}", "d")]))
    # q taps: every FF.q feeds its primary output; FF3.q also feeds the inverter
    for i in range(width):
        sinks: list[tuple[str, str]] = [(f"OUT_q{i}", "in")]
        if i == width - 1:
            sinks.append(("N1", "a"))
        nets.append(_net(f"n_q{i}", f"FF{i}", "q", sinks))

    def bits_of(state: str) -> list[int]:
        return [int(state[i]) for i in range(width)]

    def johnson_next(state: str) -> str:
        bits = bits_of(state)
        nxt = [1 - bits[width - 1]] + bits[:-1]
        return _str_bits(nxt)

    cycles = 10
    observed: list[dict[str, str]] = []
    events: list[dict[str, object]] = []
    state = "0000"
    for cycle in range(cycles):
        row: dict[str, str] = {}
        bits = bits_of(state)
        for i in range(width):
            row[f"FF{i}.q"] = str(bits[i])
            row[f"q{i}"] = str(bits[i])
        observed.append(row)
        nxt_state = johnson_next(state)
        nxt_bits = bits_of(nxt_state)
        for i in range(width):
            if nxt_bits[i] != bits[i]:
                events.append(
                    {
                        "cycle": cycle,
                        "component": f"FF{i}",
                        "pin": "q",
                        "old": str(bits[i]),
                        "new": str(nxt_bits[i]),
                        "cause": "clock_edge",
                    }
                )
        state = nxt_state
    waveforms: dict[str, list[str]] = {}
    for i in range(width):
        waveforms[f"FF{i}.q"] = [row[f"FF{i}.q"] for row in observed]
        waveforms[f"out:q{i}"] = [row[f"q{i}"] for row in observed]
    final = {f"FF{i}.q": state[i] for i in range(width)}
    return (
        _doc("johnson_counter", components, nets),
        cycles,
        observed,
        events,
        {"waveforms": waveforms, "final_state": final},
    )


def mod8_counter() -> tuple[
    dict[str, object], int, list[dict[str, str]], list[dict[str, object]], dict[str, str]
]:
    """3-bit COUNTER with en tied high: counts 0..7 and wraps."""
    width = 3
    components: list[dict[str, object]] = [
        _const0("C0"),
        {"id": "C1", "type": "CONST1"},
        {"id": "CNT", "type": "COUNTER", "params": {"width": width}},
    ]
    nets: list[dict[str, object]] = [
        _net("n_clr", "C0", "out", [("CNT", "clr")]),
        _net("n_en", "C1", "out", [("CNT", "en")]),
    ]
    for i in range(width):
        components.append(_output(f"q{i}"))
        nets.append(_net(f"n_q{i}", "CNT", f"q{i}", [(f"OUT_q{i}", "in")]))

    cycles = 8
    observed: list[dict[str, str]] = []
    events: list[dict[str, object]] = []
    value = 0
    for cycle in range(cycles):
        bits = [(value >> i) & 1 for i in range(width)]
        row = {"CNT.q0": str(bits[0]), "CNT.q1": str(bits[1]), "CNT.q2": str(bits[2])}
        for i in range(width):
            row[f"q{i}"] = str(bits[i])
        observed.append(row)
        nxt_value = (value + 1) % (1 << width)
        nxt_bits = [(nxt_value >> i) & 1 for i in range(width)]
        for i in range(width):
            if nxt_bits[i] != bits[i]:
                events.append(
                    {
                        "cycle": cycle,
                        "component": "CNT",
                        "pin": f"q{i}",
                        "old": str(bits[i]),
                        "new": str(nxt_bits[i]),
                        "cause": "clock_edge",
                    }
                )
        value = nxt_value
    waveforms: dict[str, list[str]] = {}
    for i in range(width):
        waveforms[f"CNT.q{i}"] = [row[f"CNT.q{i}"] for row in observed]
        waveforms[f"out:q{i}"] = [row[f"q{i}"] for row in observed]
    final_bits = [(value >> i) & 1 for i in range(width)]
    final = {f"CNT.q{i}": str(final_bits[i]) for i in range(width)}
    return (
        _doc("mod8_counter", components, nets),
        cycles,
        observed,
        events,
        {"waveforms": waveforms, "final_state": final},
    )


FIXTURES: dict[
    str,
    Callable[
        [],
        tuple[
            dict[str, object], int, list[dict[str, str]], list[dict[str, object]], dict[str, str]
        ],
    ],
] = {
    "seq_divide_by_2": divide_by_2,
    "seq_johnson_counter": johnson_counter,
    "seq_mod8_counter": mod8_counter,
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, factory in FIXTURES.items():
        circuit, cycles, observed, events, extra = factory()
        fixture = {
            "circuit": circuit,
            "cycles": cycles,
            "inputs_per_cycle": [],
            "expected": {
                "cycles": observed,
                "events": events,
                "waveforms": extra["waveforms"],
                "final_state": extra["final_state"],
            },
        }
        path = FIXTURES_DIR / f"{name}.json"
        path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.name}: {cycles} cycles, {len(events)} events")


if __name__ == "__main__":
    main()
