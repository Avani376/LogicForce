"""8086 published timing model (normative: cpu8086.md).

Clock cycle counts from the Intel 8086 Family User's Manual. These are the
published timings, NOT cycle-exact hardware simulation. EA = effective address
calculation penalty (5-12 cycles depending on addressing mode).
"""

from __future__ import annotations

from dataclasses import dataclass

# Base cycle counts (no EA calculation)
TIMING: dict[str, int] = {
    "MOV": 2,
    "XCHG": 4,
    "PUSH": 15,
    "POP": 12,
    "ADD": 3,
    "ADC": 3,
    "SUB": 3,
    "SBB": 3,
    "CMP": 3,
    "INC": 2,
    "DEC": 2,
    "NEG": 3,
    "AND": 3,
    "OR": 3,
    "XOR": 3,
    "NOT": 3,
    "TEST": 2,
    "MUL": 70,
    "IMUL": 80,
    "DIV": 144,
    "IDIV": 165,
    "JMP": 15,
    "JZ": 4,
    "JC": 4,
    "LOOP": 17,
    "CALL": 19,
    "RET": 16,
    "INT": 51,
    "IRET": 32,
    "HLT": 2,
    "NOP": 3,
    "STI": 2,
    "CLI": 2,
    "SHL": 2,
    "SHR": 2,
    "SAR": 2,
    "ROL": 2,
    "ROR": 2,
    "STD": 2,
    "CLD": 2,
    "MOVSB": 18,
    "MOVSW": 26,
    "STOSB": 13,
    "STOSW": 17,
    "LODSB": 15,
    "LODSW": 19,
    "SCASB": 19,
    "SCASW": 23,
    "CMPSB": 30,
    "CMPSW": 38,
}

#: EA calculation penalty cycles by addressing mode
EA_CYCLES: dict[str, int] = {
    "direct": 6,
    "reg_indirect": 5,
    "based": 9,
    "indexed": 9,
    "based_indexed": 11,
    "based_indexed_disp": 12,
}


@dataclass(frozen=True)
class TimingResult:
    mnemonic: str
    base_cycles: int
    ea_cycles: int
    total_cycles: int


def get_timing(mnemonic: str, has_memory_operand: bool = False, ea_mode: str = "direct") -> TimingResult:
    """Look up the published cycle count for an instruction.

    Label: published 8086 timing model, not cycle-exact hardware.
    """
    base = TIMING.get(mnemonic.upper(), 0)
    ea = EA_CYCLES.get(ea_mode, 0) if has_memory_operand else 0
    return TimingResult(
        mnemonic=mnemonic.upper(),
        base_cycles=base,
        ea_cycles=ea,
        total_cycles=base + ea,
    )
