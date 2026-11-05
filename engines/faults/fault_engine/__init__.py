"""LogicForge fault injection engine (v0.4.0).

Faults are pure document transformations; nominal models are never mutated.
Normative contract: ``docs/semantics/faults-and-repair.md``.
"""

from fault_engine.faults import (
    ALL_OPERATORS,
    COMB_OPERATORS,
    FAULT_MODEL_KINDS,
    FSM_OPERATORS,
    apply_fault,
    parse_fault,
)
from fault_engine.version import (
    FAULT_ENGINE_VERSION,
    FAULT_SCHEMA_VERSION,
    MAX_CANDIDATES,
    REPAIR_SCHEMA_VERSION,
)

__all__ = [
    "FAULT_ENGINE_VERSION",
    "FAULT_SCHEMA_VERSION",
    "REPAIR_SCHEMA_VERSION",
    "MAX_CANDIDATES",
    "ALL_OPERATORS",
    "FSM_OPERATORS",
    "COMB_OPERATORS",
    "FAULT_MODEL_KINDS",
    "parse_fault",
    "apply_fault",
]
