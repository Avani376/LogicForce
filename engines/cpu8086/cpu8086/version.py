"""8086 educational core identity (reproducibility metadata)."""

CPU8086_ENGINE_VERSION = "0.6.0"
CPU_IR_SCHEMA_VERSION = 1
#: Bounded-run cap: a `run` may execute at most this many instructions.
MAX_RUN_STEPS = 100_000
#: Default documented power-on stack pointer.
POWER_ON_SP = 0xFFFE
