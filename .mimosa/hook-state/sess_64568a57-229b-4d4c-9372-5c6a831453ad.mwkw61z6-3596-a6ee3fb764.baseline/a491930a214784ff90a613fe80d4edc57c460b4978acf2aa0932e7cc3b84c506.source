"""1 MiB byte-addressable memory with mod-0x100000 wraparound (cpu8086.md)."""

from __future__ import annotations

from dataclasses import dataclass, field

ADDRESS_SPACE = 0x100000


def physical(segment: int, offset: int) -> int:
    """(segment × 16 + offset) mod 0x100000 — the documented wraparound rule."""
    return ((segment << 4) + offset) % ADDRESS_SPACE


@dataclass
class Memory:
    data: bytearray = field(default_factory=lambda: bytearray(ADDRESS_SPACE))

    def read_byte(self, segment: int, offset: int) -> int:
        return self.data[physical(segment, offset)]

    def write_byte(self, segment: int, offset: int, value: int) -> None:
        self.data[physical(segment, offset)] = value & 0xFF

    def read_word(self, segment: int, offset: int) -> int:
        """Little-endian word; a word at offset 0xFFFF spans into 0x10000 (mod rule)."""
        low = self.read_byte(segment, offset)
        high = self.read_byte(segment, offset + 1)
        return low | (high << 8)

    def write_word(self, segment: int, offset: int, value: int) -> None:
        self.write_byte(segment, offset, value & 0xFF)
        self.write_byte(segment, offset + 1, (value >> 8) & 0xFF)

    def load_bytes(self, segment: int, offset: int, blob: bytes) -> None:
        for index, byte in enumerate(blob):
            self.write_byte(segment, offset + index, byte)
