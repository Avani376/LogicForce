"""Sequential engine identity (reproducibility metadata)."""

SEQUENTIAL_ENGINE_VERSION = "0.2.0"
SCHEMA_VERSION_V2 = 2

#: Hard bounds (refusal, never truncation).
MAX_CYCLES = 256
MAX_STATE_WIDTH = 16

#: Reserved namespaces for synthetic settle-network components (schema v2 doc).
SQ_PREFIX = "SQ:"
SP_PREFIX = "SP:"
