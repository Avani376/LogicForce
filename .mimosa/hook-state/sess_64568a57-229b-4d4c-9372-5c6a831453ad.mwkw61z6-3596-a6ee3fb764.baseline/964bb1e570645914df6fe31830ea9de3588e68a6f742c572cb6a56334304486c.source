"""LogicForge optimization engine (v0.5.0).

Behavior-preserving combinational circuit optimization. Every transformation is
gated by exhaustive truth-table equivalence plus the property suite. Metrics are
abstract gate-level counts — no delay claims.
"""

from optimize_engine.metrics import compute_metrics, metrics_to_dict
from optimize_engine.optimizer import (
    AppliedTransformation,
    OptimizationReport,
    optimization_report_to_dict,
    optimize,
)
from optimize_engine.transforms import apply_one_transformation
from optimize_engine.version import (
    DEFAULT_MAX_TRANSFORMATIONS,
    MAX_TRANSFORMATIONS,
    OPTIMIZATION_SCHEMA_VERSION,
    OPTIMIZE_ENGINE_VERSION,
)

__all__ = [
    "OPTIMIZE_ENGINE_VERSION",
    "OPTIMIZATION_SCHEMA_VERSION",
    "MAX_TRANSFORMATIONS",
    "DEFAULT_MAX_TRANSFORMATIONS",
    "compute_metrics",
    "metrics_to_dict",
    "apply_one_transformation",
    "optimize",
    "optimization_report_to_dict",
    "OptimizationReport",
    "AppliedTransformation",
]
