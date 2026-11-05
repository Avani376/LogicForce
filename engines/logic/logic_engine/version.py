"""Engine identity for reproducibility (recorded in every result and report)."""

ENGINE_VERSION = "0.1.0"
SCHEMA_VERSION = 1

#: Hard bound for exhaustive truth-table enumeration (2^12 = 4096 rows).
TRUTH_TABLE_MAX_INPUTS = 12

#: Hard bound for gate input width.
MAX_GATE_WIDTH = 16
