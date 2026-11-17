"""LogicForge deterministic logic engine (v0.1.0).

Pure, deterministic combinational logic simulation. No I/O, no clocks, no randomness.
Normative contracts: ``docs/semantics/``. All failures are typed errors.
"""

from logic_engine.components import SUPPORTED_TYPES, Component
from logic_engine.errors import (
    CircuitNotValidError,
    InvalidInputValueError,
    LogicEngineError,
    SchemaError,
    TruthTableLimitExceededError,
)
from logic_engine.graph import CircuitGraph, Net, PinRef, circuit_to_dict, parse_circuit
from logic_engine.hashing import canonical_inputs, canonical_json, input_hash
from logic_engine.simulator import (
    SimulationResult,
    TraceCause,
    TraceEvent,
    simulate,
    simulation_result_to_dict,
)
from logic_engine.truth_table import (
    TruthTableResult,
    TruthTableRow,
    truth_table,
    truth_table_to_dict,
)
from logic_engine.validation import (
    ValidationIssue,
    ValidationReport,
    validate,
)
from logic_engine.values import LogicValue
from logic_engine.version import ENGINE_VERSION, SCHEMA_VERSION

__all__ = [
    "ENGINE_VERSION",
    "SCHEMA_VERSION",
    "CircuitGraph",
    "Component",
    "LogicValue",
    "LogicEngineError",
    "SchemaError",
    "CircuitNotValidError",
    "InvalidInputValueError",
    "TruthTableLimitExceededError",
    "Net",
    "PinRef",
    "SUPPORTED_TYPES",
    "ValidationIssue",
    "ValidationReport",
    "SimulationResult",
    "TraceEvent",
    "TraceCause",
    "TruthTableResult",
    "TruthTableRow",
    "parse_circuit",
    "circuit_to_dict",
    "validate",
    "simulate",
    "simulation_result_to_dict",
    "truth_table",
    "truth_table_to_dict",
    "canonical_json",
    "canonical_inputs",
    "input_hash",
]
