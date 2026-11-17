"""Exhaustive truth-table enumeration with an honest scope label.

Normative source: ``docs/semantics/report-and-scope-labels.md``. Bound: 12 primary
inputs (4096 rows); beyond that the request is refused — never truncated, because a
truncated table would silently relabel an exhaustive claim as bounded.
"""

from __future__ import annotations

from dataclasses import dataclass

from logic_engine.components import TYPE_INPUT, TYPE_OUTPUT
from logic_engine.errors import TruthTableLimitExceededError
from logic_engine.graph import CircuitGraph
from logic_engine.simulator import simulate
from logic_engine.validation import require_valid
from logic_engine.values import LogicValue
from logic_engine.version import ENGINE_VERSION, TRUTH_TABLE_MAX_INPUTS


@dataclass(frozen=True)
class TruthTableRow:
    inputs: dict[str, str]
    outputs: dict[str, str]


@dataclass(frozen=True)
class TruthTableResult:
    engine_version: str
    scope: str
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]
    rows: tuple[TruthTableRow, ...]


def truth_table(graph: CircuitGraph) -> TruthTableResult:
    """Enumerate all 2^n input vectors in ascending input-name order.

    The first input name (alphabetical) is the most significant bit of the row index.
    Every row is produced by the same deterministic ``simulate`` path used by the
    single-vector API, so the two can never disagree.

    Raises ``CircuitNotValidError`` (invalid circuit) or
    ``TruthTableLimitExceededError`` (more than 12 primary inputs).
    """
    require_valid(graph)

    input_names = sorted(
        str(comp.params["name"])
        for comp in graph.components
        if comp.type == TYPE_INPUT and isinstance(comp.params.get("name"), str)
    )
    output_names = sorted(
        str(comp.params["name"])
        for comp in graph.components
        if comp.type == TYPE_OUTPUT and isinstance(comp.params.get("name"), str)
    )

    n = len(input_names)
    if n > TRUTH_TABLE_MAX_INPUTS:
        raise TruthTableLimitExceededError(n, TRUTH_TABLE_MAX_INPUTS)

    rows: list[TruthTableRow] = []
    for index in range(1 << n):
        vector: dict[str, LogicValue] = {}
        for position, name in enumerate(input_names):
            bit = (index >> (n - 1 - position)) & 1
            vector[name] = LogicValue.ONE if bit else LogicValue.ZERO
        result = simulate(graph, vector)
        rows.append(
            TruthTableRow(
                inputs={name: vector[name].value for name in input_names},
                outputs=dict(result.outputs),
            )
        )

    return TruthTableResult(
        engine_version=ENGINE_VERSION,
        scope=f"EXHAUSTIVE({1 << n})",
        input_names=tuple(input_names),
        output_names=tuple(output_names),
        rows=tuple(rows),
    )


def truth_table_to_dict(result: TruthTableResult) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "engine_version": result.engine_version,
        "scope": result.scope,
        "input_names": list(result.input_names),
        "output_names": list(result.output_names),
        "rows": [{"inputs": dict(row.inputs), "outputs": dict(row.outputs)} for row in result.rows],
    }
