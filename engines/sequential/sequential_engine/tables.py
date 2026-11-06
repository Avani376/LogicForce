"""Excitation and characteristic tables for flip-flops (Phase C5).

Auto-generated from the same characteristic functions used by the executor,
so the tables and the simulation can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass

from logic_engine import SchemaError
from sequential_engine.flipflops import dff_next, jkff_next, srff_next, tff_next
from logic_engine.values import LogicValue

_0 = LogicValue.ZERO
_1 = LogicValue.ONE


@dataclass(frozen=True)
class TableEntry:
    inputs: dict[str, int]
    current_q: int
    next_q: int


@dataclass(frozen=True)
class FlipFlopTables:
    ff_type: str
    characteristic: list[TableEntry]  # Q(t+1) = f(inputs, Q)
    excitation: list[TableEntry]  # inputs needed for each Q→Q' transition


def _int_to_lv(value: int) -> LogicValue:
    return LogicValue.ONE if value else LogicValue.ZERO


def characteristic_table(ff_type: str, width: int = 1) -> FlipFlopTables:
    """Generate the full characteristic table for a flip-flop type."""
    if ff_type == "DFF":
        input_names = ["D"]
    elif ff_type == "TFF":
        input_names = ["T"]
    elif ff_type == "JKFF":
        input_names = ["J", "K"]
    elif ff_type == "SRFF":
        input_names = ["S", "R"]
    else:
        raise SchemaError("UNKNOWN_FF_TYPE", f"unknown flip-flop type {ff_type!r}")

    entries: list[TableEntry] = []
    num_inputs = len(input_names)
    for q in (0, 1):
        for combo in range(1 << num_inputs):
            inputs = {name: (combo >> (num_inputs - 1 - pos)) & 1 for pos, name in enumerate(input_names)}
            if ff_type == "DFF":
                nq = dff_next(_int_to_lv(inputs["D"]))
            elif ff_type == "TFF":
                nq = tff_next(_int_to_lv(inputs["T"]), _int_to_lv(q))
            elif ff_type == "JKFF":
                nq = jkff_next(_int_to_lv(inputs["J"]), _int_to_lv(inputs["K"]), _int_to_lv(q))
            else:
                nq = srff_next(_int_to_lv(inputs["S"]), _int_to_lv(inputs["R"]), _int_to_lv(q))
            next_q = 1 if nq == LogicValue.ONE else (0 if nq == LogicValue.ZERO else -1)
            entries.append(TableEntry(inputs=inputs, current_q=q, next_q=next_q))
    return FlipFlopTables(ff_type=ff_type, characteristic=entries, excitation=[])


def excitation_table(ff_type: str) -> FlipFlopTables:
    """Generate the excitation table: what inputs are needed for each Q→Q' transition."""
    if ff_type == "DFF":
        # D = Q' for all transitions (D always equals the desired next state)
        entries = [TableEntry(inputs={"D": nq}, current_q=q, next_q=nq) for q in (0, 1) for nq in (0, 1)]
        return FlipFlopTables(ff_type=ff_type, characteristic=[], excitation=entries)

    if ff_type == "TFF":
        # T = Q ^ Q' (toggle iff the state changes)
        entries = []
        for q in (0, 1):
            for nq in (0, 1):
                t = q ^ nq
                entries.append(TableEntry(inputs={"T": t}, current_q=q, next_q=nq))
        return FlipFlopTables(ff_type=ff_type, characteristic=[], excitation=entries)

    if ff_type == "JKFF":
        entries = []
        for q in (0, 1):
            for nq in (0, 1):
                if q == 0 and nq == 0:
                    j, k = 0, 0  # hold
                elif q == 0 and nq == 1:
                    j, k = 1, 0  # set
                elif q == 1 and nq == 0:
                    j, k = 0, 1  # reset
                else:
                    j, k = 1, 1  # toggle
                entries.append(TableEntry(inputs={"J": j, "K": k}, current_q=q, next_q=nq))
        return FlipFlopTables(ff_type=ff_type, characteristic=[], excitation=entries)

    if ff_type == "SRFF":
        entries = []
        for q in (0, 1):
            for nq in (0, 1):
                if q == 0 and nq == 0:
                    s, r = 0, 0  # hold
                elif q == 0 and nq == 1:
                    s, r = 1, 0  # set
                elif q == 1 and nq == 0:
                    s, r = 0, 1  # reset
                else:
                    s, r = 0, 0  # Q=1→Q=1: hold (SR=11 is forbidden)
                entries.append(TableEntry(inputs={"S": s, "R": r}, current_q=q, next_q=nq))
        return FlipFlopTables(ff_type=ff_type, characteristic=[], excitation=entries)

    raise SchemaError("UNKNOWN_FF_TYPE", f"unknown flip-flop type {ff_type!r}")
