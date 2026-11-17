"""LogicForge repair engine (v0.4.0).

Delta-guided repair search toward a passing nominal reference, with full
property-suite re-verification per candidate. "Repaired" is claimed only after
the suite passes on the repaired model.
"""

from repair_engine.repair import (
    REPAIR_OPS,
    RepairCandidate,
    RepairReport,
    apply_patch,
    compute_deltas,
    repair_report_to_dict,
    search_repairs,
)
from repair_engine.version import REPAIR_ENGINE_VERSION, REPAIR_SCHEMA_VERSION

__all__ = [
    "REPAIR_ENGINE_VERSION",
    "REPAIR_SCHEMA_VERSION",
    "REPAIR_OPS",
    "RepairCandidate",
    "RepairReport",
    "compute_deltas",
    "apply_patch",
    "search_repairs",
    "repair_report_to_dict",
]
