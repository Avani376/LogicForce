"""LogicForge verification engine (v0.3.0).

Invariant verification over bounded models. Pure, deterministic, typed errors,
scope labels mandatory. Verdicts are produced only by this package.
"""

from verify_engine.expressions import (
    ExprNode,
    evaluate_expression,
    expression_signals,
    parse_expression,
)
from verify_engine.verify import (
    Property,
    VerificationReport,
    parse_property,
    verification_report_to_dict,
    verify_combinational_invariant,
    verify_fsm_invariant,
)
from verify_engine.version import (
    MAX_COMBINATIONAL_INPUTS,
    MAX_FSM_INPUTS,
    MAX_FSM_STATES,
    PROPERTY_SCHEMA_VERSION,
    VERIFY_ENGINE_VERSION,
)

__all__ = [
    "VERIFY_ENGINE_VERSION",
    "PROPERTY_SCHEMA_VERSION",
    "MAX_COMBINATIONAL_INPUTS",
    "MAX_FSM_INPUTS",
    "MAX_FSM_STATES",
    "Property",
    "VerificationReport",
    "ExprNode",
    "parse_expression",
    "expression_signals",
    "evaluate_expression",
    "parse_property",
    "verify_combinational_invariant",
    "verify_fsm_invariant",
    "verification_report_to_dict",
]
