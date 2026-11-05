"""LogicForge 8086 educational core (v0.6.0).

IR-based educational emulator: assembler -> typed instructions -> deterministic
executor with exact documented flag semantics. Native machine-code encoding is
out of scope (see docs/semantics/cpu8086.md).
"""

from cpu8086.assembler import AssembledProgram, Instruction, assemble
from cpu8086.errors import AsmError, CpuRuntimeError, UnsupportedInstructionError
from cpu8086.memory import ADDRESS_SPACE, Memory, physical
from cpu8086.registers import (
    BYTE_HALVES,
    FLAG_NAMES,
    SEG_REGS,
    WORD_REGS,
    Registers,
    add_flags,
    inc_dec_flags,
    logic_flags,
    neg_flags,
    parity_of_low_byte,
    sub_flags,
)
from cpu8086.version import CPU8086_ENGINE_VERSION

__all__ = [
    "CPU8086_ENGINE_VERSION",
    "AsmError",
    "AssembledProgram",
    "Instruction",
    "assemble",
    "CpuRuntimeError",
    "UnsupportedInstructionError",
    "Memory",
    "physical",
    "ADDRESS_SPACE",
    "Registers",
    "WORD_REGS",
    "SEG_REGS",
    "BYTE_HALVES",
    "FLAG_NAMES",
    "add_flags",
    "sub_flags",
    "inc_dec_flags",
    "neg_flags",
    "logic_flags",
    "parity_of_low_byte",
]
