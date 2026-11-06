"""LogicForge number systems engine (v0.9.0)."""

from numsys.conversions import (
    NumSysResult,
    Step,
    ascii_lookup,
    bcd_decode,
    bcd_encode,
    complement_add,
    convert_with_steps,
    excess3_decode,
    excess3_encode,
    gray_decode,
    gray_encode,
    ones_complement,
    twos_complement,
)
from numsys.version import NUMSYS_ENGINE_VERSION

__all__ = [
    "NUMSYS_ENGINE_VERSION",
    "NumSysResult",
    "Step",
    "convert_with_steps",
    "ones_complement",
    "twos_complement",
    "complement_add",
    "bcd_encode",
    "bcd_decode",
    "excess3_encode",
    "excess3_decode",
    "gray_encode",
    "gray_decode",
    "ascii_lookup",
]
