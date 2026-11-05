"""LogicForge deterministic sequential engine (v0.2.0).

Clocked state simulation over the shared four-valued domain. Pure, deterministic,
no I/O. Normative contracts: ``docs/semantics/clock-edge-rules.md``,
``docs/semantics/circuit-graph-schema-v2.md``, ``docs/semantics/fsm-model.md``.
"""

from sequential_engine.flipflops import (
    async_apply,
    counter_next,
    dff_next,
    jkff_next,
    srff_next,
    tff_next,
)
from sequential_engine.graph import (
    MULTI_BIT_TYPES,
    SUPPORTED_SEQUENTIAL_TYPES,
    parse_circuit_v2,
    resolve_state_spec,
)
from sequential_engine.simulator import (
    CycleRecord,
    SeqEvent,
    SequentialResult,
    sequential_result_to_dict,
    simulate_sequential,
)
from sequential_engine.validation import validate_sequential
from sequential_engine.version import (
    MAX_CYCLES,
    MAX_STATE_WIDTH,
    SCHEMA_VERSION_V2,
    SEQUENTIAL_ENGINE_VERSION,
)

__all__ = [
    "SEQUENTIAL_ENGINE_VERSION",
    "SCHEMA_VERSION_V2",
    "MAX_CYCLES",
    "MAX_STATE_WIDTH",
    "SUPPORTED_SEQUENTIAL_TYPES",
    "MULTI_BIT_TYPES",
    "dff_next",
    "tff_next",
    "jkff_next",
    "srff_next",
    "async_apply",
    "counter_next",
    "parse_circuit_v2",
    "resolve_state_spec",
    "validate_sequential",
    "simulate_sequential",
    "sequential_result_to_dict",
    "SequentialResult",
    "CycleRecord",
    "SeqEvent",
]
