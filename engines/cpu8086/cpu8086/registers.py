"""Register model and exact flag computations (normative: cpu8086.md).

Flag functions are pure and tested against documented Intel behavior, including
known vectors (e.g. ADD 0x7F+0x01 sets OF/AF/SF and clears CF/ZF).
"""

from __future__ import annotations

from dataclasses import dataclass, field

WORD_REGS = ("AX", "BX", "CX", "DX", "SI", "DI", "BP", "SP", "IP")
SEG_REGS = ("CS", "DS", "SS", "ES")
BYTE_HALVES = {
    "AL": ("AX", "L"),
    "AH": ("AX", "H"),
    "BL": ("BX", "L"),
    "BH": ("BX", "H"),
    "CL": ("CX", "L"),
    "CH": ("CX", "H"),
    "DL": ("DX", "L"),
    "DH": ("DX", "H"),
}
FLAG_NAMES = ("CF", "PF", "AF", "ZF", "SF", "OF", "IF")


def parity_of_low_byte(value: int) -> int:
    """PF: 1 when the low 8 bits have even parity (Intel semantics)."""
    return 1 if bin(value & 0xFF).count("1") % 2 == 0 else 0


def _sign_bit(width: int) -> int:
    return 0x8000 if width == 16 else 0x80


def _mask(width: int) -> int:
    return 0xFFFF if width == 16 else 0xFF


def add_flags(a: int, b: int, carry_in: int, width: int) -> dict[str, int]:
    """Flag deltas for ADD/ADC: CF, OF, ZF, SF, PF, AF."""
    mask = _mask(width)
    total = a + b + carry_in
    result = total & mask
    sign = _sign_bit(width)
    return {
        "CF": 1 if total > mask else 0,
        "OF": 1 if ((a ^ result) & (b ^ result) & sign) != 0 else 0,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & sign else 0,
        "PF": parity_of_low_byte(result),
        "AF": 1 if ((a ^ b ^ result) & 0x10) != 0 else 0,
    }


def sub_flags(a: int, b: int, borrow_in: int, width: int) -> dict[str, int]:
    """Flag deltas for SUB/SBB/CMP: CF is the borrow, OF signed overflow."""
    mask = _mask(width)
    result = (a - b - borrow_in) & mask
    sign = _sign_bit(width)
    return {
        "CF": 1 if (b + borrow_in) > a else 0,
        "OF": 1 if ((a ^ b) & (a ^ result) & sign) != 0 else 0,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & sign else 0,
        "PF": parity_of_low_byte(result),
        "AF": 1 if ((a ^ b ^ result) & 0x10) != 0 else 0,
    }


def inc_dec_flags(old: int, result: int, width: int, increment: bool) -> dict[str, int]:
    """INC/DEC flag deltas — CF is intentionally ABSENT (unchanged on the real part).

    OF semantics are INC/DEC-specific per the Intel manuals: INC sets OF only when
    incrementing from the most-positive value (0x7F/0x7FFF), DEC only when
    decrementing from the most-negative value (0x80/0x8000)."""
    sign = _sign_bit(width)
    overflow = (1 if old == sign - 1 else 0) if increment else (1 if old == sign else 0)
    return {
        "OF": overflow,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & sign else 0,
        "PF": parity_of_low_byte(result),
        "AF": 1 if ((old ^ 1 ^ result) & 0x10) != 0 else 0,
    }


def neg_flags(a: int, width: int) -> dict[str, int]:
    """NEG: CF=1 iff operand != 0; OF=1 iff operand is the most-negative value."""
    mask = _mask(width)
    result = (-a) & mask
    sign = _sign_bit(width)
    return {
        "CF": 1 if a != 0 else 0,
        "OF": 1 if a == sign else 0,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & sign else 0,
        "PF": parity_of_low_byte(result),
        "AF": 1 if ((0 ^ a ^ result) & 0x10) != 0 else 0,
    }


def logic_flags(result: int, width: int) -> dict[str, int]:
    """Logical ops: CF=OF=0; AF cleared (documented deviation from 'undefined')."""
    sign = _sign_bit(width)
    return {
        "CF": 0,
        "OF": 0,
        "ZF": 1 if result == 0 else 0,
        "SF": 1 if result & sign else 0,
        "PF": parity_of_low_byte(result),
        "AF": 0,
    }


def mul_flags(low: int, overflow: bool, width: int) -> dict[str, int]:
    """MUL/IMUL: CF=OF per the overflow rule; ZF/SF/PF from the low half, AF
    cleared — Intel marks these undefined, we define them (cpu8086.md)."""
    flags = logic_flags(low, width)
    carry = 1 if overflow else 0
    flags["CF"] = carry
    flags["OF"] = carry
    return flags


@dataclass
class Registers:
    """All programmer-visible state except memory."""

    words: dict[str, int] = field(
        default_factory=lambda: {
            "AX": 0,
            "BX": 0,
            "CX": 0,
            "DX": 0,
            "SI": 0,
            "DI": 0,
            "BP": 0,
            "SP": 0,
            "IP": 0,
            "CS": 0,
            "DS": 0,
            "SS": 0,
            "ES": 0,
        }
    )
    flags: dict[str, int] = field(default_factory=lambda: {name: 0 for name in FLAG_NAMES})

    def get(self, name: str) -> int:
        name = name.upper()
        if name in BYTE_HALVES:
            parent, half = BYTE_HALVES[name]
            value = self.words[parent]
            return (value >> 8) & 0xFF if half == "H" else value & 0xFF
        if name in self.words:
            return self.words[name]
        raise KeyError(f"unknown register {name!r}")

    def set(self, name: str, value: int) -> None:
        name = name.upper()
        value &= 0xFFFF
        if name in BYTE_HALVES:
            parent, half = BYTE_HALVES[name]
            current = self.words[parent]
            if half == "H":
                self.words[parent] = (current & 0x00FF) | ((value & 0xFF) << 8)
            else:
                self.words[parent] = (current & 0xFF00) | (value & 0xFF)
            return
        if name in self.words:
            self.words[name] = value & 0xFFFF
            return
        raise KeyError(f"unknown register {name!r}")

    def set_flags(self, deltas: dict[str, int]) -> None:
        for name, value in deltas.items():
            if name in self.flags:
                self.flags[name] = value

    def snapshot(self) -> dict[str, int]:
        return {**{name: value for name, value in self.words.items()}, **self.flags}
