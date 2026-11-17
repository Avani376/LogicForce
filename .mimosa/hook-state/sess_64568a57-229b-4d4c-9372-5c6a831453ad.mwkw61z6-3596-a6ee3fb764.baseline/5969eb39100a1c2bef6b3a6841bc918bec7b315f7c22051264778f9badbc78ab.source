"""Optimization pipeline: transformations with per-step equivalence + suite gates.

Every applied transformation must (1) preserve the full truth table EXHAUSTIVELY
and (2) keep every provided property PASSing — otherwise the run stops honestly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from logic_engine import SchemaError
from logic_engine.graph import CircuitGraph
from logic_engine.graph import parse_circuit as parse_circuit_v1
from logic_engine.hashing import canonical_json
from logic_engine.truth_table import truth_table
from logic_engine.validation import require_valid as v1_require_valid
from verify_engine import verify_combinational_invariant

from optimize_engine.metrics import compute_metrics, metrics_to_dict
from optimize_engine.transforms import apply_one_transformation
from optimize_engine.version import (
    DEFAULT_MAX_TRANSFORMATIONS,
    MAX_TRANSFORMATIONS,
    OPTIMIZATION_SCHEMA_VERSION,
    OPTIMIZE_ENGINE_VERSION,
)

VERDICT_OPTIMIZED = "OPTIMIZED"
VERDICT_NO_CHANGE = "NO_CHANGE_APPLICABLE"
VERDICT_INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class AppliedTransformation:
    description: str
    metrics: dict[str, int]
    equivalence: dict[str, object]
    suite_verdicts: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class OptimizationReport:
    engine_version: str
    input_hash: str
    metrics_before: dict[str, int]
    metrics_after: dict[str, int]
    transformations: tuple[AppliedTransformation, ...]
    final_model: dict[str, object] | None
    verdict: str
    scope: str
    assumptions: tuple[str, ...]
    reason: str | None


def _input_hash(
    circuit: Mapping[str, object],
    properties: Sequence[Mapping[str, object]],
    max_transformations: int,
) -> str:
    payload = (
        f"opt1|{canonical_json(dict(circuit))}|{canonical_json([dict(p) for p in properties])}|{max_transformations}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _truth_table_signature(
    graph: CircuitGraph,
) -> list[tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]]:
    result = truth_table(graph)
    return [(tuple(sorted(row.inputs.items())), tuple(sorted(row.outputs.items()))) for row in result.rows]


def optimize(
    circuit: Mapping[str, object],
    properties: Sequence[Mapping[str, object]],
    max_transformations: int = DEFAULT_MAX_TRANSFORMATIONS,
) -> OptimizationReport:
    """Run behavior-preserving optimization passes on a combinational circuit.

    Each applied transformation is individually gated: full truth-table
    equivalence (EXHAUSTIVE, n ≤ 12) plus every property still PASSing. Bounds
    refusals produce INCOMPLETE with a reason — never unverifiable claims.
    """
    if not isinstance(max_transformations, int) or isinstance(max_transformations, bool):
        raise SchemaError(
            "OPTIMIZATION_SCHEMA_ERROR",
            "max_transformations must be an integer",
        )
    if not 1 <= max_transformations <= MAX_TRANSFORMATIONS:
        raise SchemaError(
            "OPTIMIZATION_SCHEMA_ERROR",
            f"max_transformations must be in [1, {MAX_TRANSFORMATIONS}], got {max_transformations}",
        )
    properties_list = list(properties)
    for property_raw in properties_list:
        if property_raw.get("kind") != "combinational_invariant":
            raise SchemaError(
                "PROPERTY_SCHEMA_ERROR",
                f"optimization properties must be combinational_invariant (got {property_raw.get('kind')!r})",
            )

    graph = parse_circuit_v1(dict(circuit))
    v1_require_valid(graph)
    input_count = sum(1 for c in graph.components if c.type == "INPUT" and isinstance(c.params.get("name"), str))
    assumptions = (
        "logic_depth is an abstract gate-level metric, not hardware delay",
        "equivalence checked exhaustively over all input vectors per transformation",
    )
    hash_hex = _input_hash(circuit, properties_list, max_transformations)
    scope = f"EXHAUSTIVE({1 << input_count} input vectors) equivalence per transformation"

    if input_count > 12:
        return OptimizationReport(
            engine_version=OPTIMIZE_ENGINE_VERSION,
            input_hash=hash_hex,
            metrics_before=metrics_to_dict(compute_metrics(graph)),
            metrics_after=metrics_to_dict(compute_metrics(graph)),
            transformations=(),
            final_model=None,
            verdict=VERDICT_INCOMPLETE,
            scope="INCOMPLETE",
            assumptions=assumptions,
            reason=(
                f"MODEL_TOO_LARGE: {input_count} primary inputs exceed the 12-input "
                "exhaustive-equivalence bound — unverifiable optimizations are not performed"
            ),
        )

    nominal_signature = _truth_table_signature(graph)
    metrics_before = metrics_to_dict(compute_metrics(graph))
    current_doc: dict[str, object] = dict(circuit)
    transformations: list[AppliedTransformation] = []

    for _ in range(max_transformations):
        candidate = apply_one_transformation(current_doc)
        if candidate is None:
            break
        candidate_doc, description = candidate
        candidate_graph = parse_circuit_v1(candidate_doc)
        v1_require_valid(candidate_graph)
        candidate_signature = _truth_table_signature(candidate_graph)
        if candidate_signature != nominal_signature:
            # provably-safe classes should never trip this; if they do, stop honestly
            break
        suite_verdicts: list[dict[str, str]] = []
        rejected = False
        for property_raw in properties_list:
            report = verify_combinational_invariant(candidate_doc, property_raw)
            suite_verdicts.append({"id": str(property_raw.get("id", "unnamed")), "verdict": report.verdict})
            if report.verdict != "PASS":
                rejected = True
        if rejected:
            break
        current_doc = candidate_doc
        candidate_metrics = compute_metrics(candidate_graph)
        transformations.append(
            AppliedTransformation(
                description=description,
                metrics=metrics_to_dict(candidate_metrics),
                equivalence={
                    "equal": True,
                    "scope": f"EXHAUSTIVE({1 << input_count} input vectors)",
                },
                suite_verdicts=tuple(suite_verdicts),
            )
        )

    final_graph = parse_circuit_v1(current_doc)
    metrics_after = metrics_to_dict(compute_metrics(final_graph))
    verdict = VERDICT_OPTIMIZED if transformations else VERDICT_NO_CHANGE
    return OptimizationReport(
        engine_version=OPTIMIZE_ENGINE_VERSION,
        input_hash=hash_hex,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        transformations=tuple(transformations),
        final_model=current_doc if transformations else None,
        verdict=verdict,
        scope=scope,
        assumptions=assumptions,
        reason=None,
    )


def optimization_report_to_dict(report: OptimizationReport) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "schema_version": OPTIMIZATION_SCHEMA_VERSION,
        "engine_version": report.engine_version,
        "input_hash": report.input_hash,
        "metrics_before": report.metrics_before,
        "metrics_after": report.metrics_after,
        "transformations": [
            {
                "description": t.description,
                "metrics": t.metrics,
                "equivalence": t.equivalence,
                "suite_verdicts": [dict(v) for v in t.suite_verdicts],
            }
            for t in report.transformations
        ],
        "final_model": report.final_model,
        "verdict": report.verdict,
        "scope": report.scope,
        "assumptions": list(report.assumptions),
        "reason": report.reason,
    }


__all__ = [
    "OptimizationReport",
    "AppliedTransformation",
    "optimize",
    "optimization_report_to_dict",
]
