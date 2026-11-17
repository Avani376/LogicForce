"""Deterministic 8259 PIC model: registers, ICW/OCW machine, priority, EOI (pic8259.md)."""

from __future__ import annotations

from dataclasses import dataclass

from pic8259.errors import PicError


@dataclass(frozen=True)
class PicTraceEvent:
    """One state transition. `at_step` is caller-supplied (instruction boundary)."""

    at_step: int
    kind: str  # init | request | deliver | ack | eoi | mask | rotate | smm
    line: int | None = None
    vector: int | None = None
    detail: str = ""

    def to_json(self) -> dict[str, int | str | None]:
        return {
            "at_step": self.at_step,
            "kind": self.kind,
            "line": self.line,
            "vector": self.vector,
            "detail": self.detail,
        }


class Pic8259:
    """Single-chip 8259 model. All state transitions are explicit method calls."""

    def __init__(self) -> None:
        self.irr = 0
        self.isr = 0
        self.imr = 0
        self._base = 0
        self._aeoi = False
        self._ltim = False
        self._sfnm = False
        self._single = True
        self._icw3 = 0
        self._priority_floor = 7  # rank(line) = (line - floor - 1) mod 8; floor 7 ⇒ IR0 highest
        self._special_mask = False
        self._status_select_isr = False  # OCW3 RR/RIS
        self._in_init = False
        self._expect_icw3 = False
        self._expect_icw4 = False
        self._initialized = False
        self.trace: list[PicTraceEvent] = []

    # ------------------------------------------------------------------ init

    def write_icw1(self, value: int, at_step: int = 0) -> None:
        """ICW1 — always the first word; re-initializes the controller."""
        value = self._byte(value, "ICW1")
        ic4 = value & 0x01
        sngl = (value >> 1) & 0x01
        ltim = (value >> 3) & 0x01
        # Re-initialization: documented real-chip behavior (all state clears).
        self.irr = 0
        self.isr = 0
        self.imr = 0
        self._priority_floor = 7
        self._special_mask = False
        self._status_select_isr = False
        self._aeoi = False
        self._ltim = ltim == 1
        self._sfnm = False
        self._single = sngl == 1
        self._icw3 = 0
        self._base = 0
        self._in_init = True
        self._expect_icw3 = sngl == 0
        self._expect_icw4 = ic4 == 1
        self._initialized = False
        self.trace.append(PicTraceEvent(at_step, "init", detail=f"ICW1=0x{value:02X} (re-init)"))

    def write_icw2(self, value: int, at_step: int = 0) -> None:
        """ICW2 — vector base for IR0; must be a multiple of 8 (8086 mode)."""
        if not self._in_init:
            raise PicError("INIT_SEQUENCE", "ICW2 before ICW1 — the init sequence starts with ICW1")
        value = self._byte(value, "ICW2")
        if value % 8 != 0:
            raise PicError(
                "BAD_VECTOR_BASE",
                f"ICW2 vector base must be a multiple of 8 in 8086 mode, got {value} (IR0..IR7 map to base..base+7)",
            )
        self._base = value
        if self._expect_icw3:
            return  # ICW3 comes next (SNGL=0)
        if self._expect_icw4:
            return  # ICW4 comes next (IC4=1)
        self._finish_init()

    def write_icw3(self, value: int, at_step: int = 0) -> None:
        """ICW3 — required when SNGL=0; recorded, cascade routing not simulated."""
        if not self._in_init:
            raise PicError("INIT_SEQUENCE", "ICW3 outside the init sequence")
        if not self._expect_icw3:
            raise PicError(
                "INIT_SEQUENCE",
                "ICW3 not expected — SNGL=1 (single chip); expected ICW4 or nothing",
            )
        value = self._byte(value, "ICW3")
        self._icw3 = value
        self._expect_icw3 = False
        if not self._expect_icw4:
            self._finish_init()

    def write_icw4(self, value: int, at_step: int = 0) -> None:
        """ICW4 — required when IC4=1; AEOI (bit 1) and SFNM (bit 4) recorded."""
        if not self._in_init:
            raise PicError("INIT_SEQUENCE", "ICW4 outside the init sequence")
        if not self._expect_icw4:
            raise PicError(
                "INIT_SEQUENCE",
                "ICW4 not expected — IC4=0 in ICW1; the init sequence is already complete",
            )
        value = self._byte(value, "ICW4")
        self._aeoi = (value & 0x02) != 0
        self._sfnm = (value & 0x10) != 0
        self._expect_icw4 = False
        self._finish_init()

    def _finish_init(self) -> None:
        self._in_init = False
        self._initialized = True

    # ------------------------------------------------------------------ ocws

    def write_ocw1(self, value: int, at_step: int = 0) -> None:
        """OCW1 — set the interrupt mask register directly (bit=1 masks the line)."""
        self._require_initialized("OCW1")
        value = self._byte(value, "OCW1")
        self.imr = value
        self.trace.append(PicTraceEvent(at_step, "mask", detail=f"IMR=0x{value:02X}"))

    def write_ocw2(self, value: int, at_step: int = 0) -> None:
        """OCW2 — EOI family and rotation (R/SL/EOI bits + LEVEL)."""
        self._require_initialized("OCW2")
        value = self._byte(value, "OCW2")
        rotate = (value >> 7) & 0x01
        specific = (value >> 6) & 0x01
        eoi = (value >> 5) & 0x01
        level = value & 0x07
        if (rotate, specific, eoi) == (0, 0, 0):
            raise PicError("BAD_OCW", f"OCW2 0x{value:02X}: R=0, SL=0, EOI=0 is a undefined command")
        if not eoi and (specific or not rotate):
            raise PicError("BAD_OCW", f"OCW2 0x{value:02X}: only 'rotate/set priority' (R=1,SL=0,EOI=0) omits EOI")

        if rotate and not specific and not eoi:
            # Set priority command: floor ← LEVEL, ISR unchanged.
            self._priority_floor = level
            self.trace.append(PicTraceEvent(at_step, "rotate", line=level, detail=f"priority floor ← IR{level}"))
            return

        if specific:
            if (self.isr >> level) & 0x01 == 0:
                raise PicError(
                    "BAD_OCW", f"specific EOI for IR{level} but IR{level} is not in service (ISR=0x{self.isr:02X})"
                )
            self._clear_isr(level)
            self.trace.append(PicTraceEvent(at_step, "eoi", line=level, detail=f"specific EOI IR{level}"))
        else:
            best = self._best_isr_line()
            if best is None:
                raise PicError("BAD_OCW", f"non-specific EOI with empty ISR (ISR=0x{self.isr:02X})")
            self._clear_isr(best)
            self.trace.append(PicTraceEvent(at_step, "eoi", line=best, detail=f"non-specific EOI IR{best}"))
            level = best

        if rotate:
            self._priority_floor = level
            self.trace.append(PicTraceEvent(at_step, "rotate", line=level, detail=f"priority floor ← IR{level}"))

    def write_ocw3(self, value: int, at_step: int = 0) -> None:
        """OCW3 — special mask mode (ESMM/SMM) and IRR/ISR status-read select."""
        self._require_initialized("OCW3")
        value = self._byte(value, "OCW3")
        esmm = (value >> 6) & 0x01
        smm = (value >> 5) & 0x01
        poll = (value >> 2) & 0x01
        if poll:
            raise PicError("BAD_OCW", "poll mode (P=1) is out of the educational subset — see pic8259.md")
        if esmm:
            self._special_mask = smm == 1
            self.trace.append(PicTraceEvent(at_step, "smm", detail=f"special mask mode {'ON' if smm else 'OFF'}"))
        rr = (value >> 1) & 0x01
        ris = value & 0x01
        if rr:
            self._status_select_isr = ris == 1

    # ------------------------------------------------------------- operation

    def request(self, line: int, at_step: int = 0) -> None:
        """Raise a request pulse on IR line `line` (0–7). Masked lines still record in IRR."""
        line = self._line(line)
        self.irr |= 1 << line
        self.trace.append(PicTraceEvent(at_step, "request", line=line, detail=f"IR{line} raised"))

    def int_vector(self) -> int | None:
        """Vector number on the INT line for the best serviceable request, or None."""
        line = self._serviceable_line()
        if line is None:
            return None
        return self._base + line

    def acknowledge(self, at_step: int = 0) -> int:
        """INTA: move the best serviceable IRR bit to ISR; return its vector."""
        line = self._serviceable_line()
        if line is None:
            raise PicError(
                "BAD_OCW",
                "acknowledge with no serviceable request "
                f"(IRR=0x{self.irr:02X}, IMR=0x{self.imr:02X}, ISR=0x{self.isr:02X})",
            )
        bit = 1 << line
        self.irr &= ~bit & 0xFF
        vector = self._base + line
        if self._aeoi:
            self.trace.append(
                PicTraceEvent(at_step, "ack", line=line, vector=vector, detail=f"IR{line} ack (AEOI — no ISR bit)")
            )
            self.trace.append(PicTraceEvent(at_step, "eoi", line=line, detail="automatic EOI"))
        else:
            self.isr |= bit
            self.trace.append(PicTraceEvent(at_step, "ack", line=line, vector=vector, detail=f"IR{line} in service"))
        return vector

    def read_irr(self) -> int:
        return self.irr

    def read_isr(self) -> int:
        return self.isr

    def read_imr(self) -> int:
        return self.imr

    def read_status(self) -> tuple[str, int]:
        """(register_name, value) per the OCW3 RR/RIS selection."""
        return ("ISR" if self._status_select_isr else "IRR", self.isr if self._status_select_isr else self.irr)

    # ------------------------------------------------------------- internals

    def _rank(self, line: int) -> int:
        return (line - self._priority_floor - 1) % 8

    def _serviceable_line(self) -> int | None:
        best: int | None = None
        for line in range(8):
            bit = 1 << line
            if (self.irr & bit) == 0 or (self.imr & bit) != 0:
                continue
            if not self._special_mask:
                blocking = self._best_isr_line()
                if blocking is not None and self._rank(line) >= self._rank(blocking):
                    continue
            if best is None or self._rank(line) < self._rank(best):
                best = line
        return best

    def _best_isr_line(self) -> int | None:
        best: int | None = None
        for line in range(8):
            if (self.isr >> line) & 0x01 and (best is None or self._rank(line) < self._rank(best)):
                best = line
        return best

    def _clear_isr(self, line: int) -> None:
        self.isr &= ~(1 << line) & 0xFF

    def _require_initialized(self, word: str) -> None:
        if not self._initialized:
            raise PicError("NOT_INITIALIZED", f"{word} before init completes — write the full ICW sequence first")

    def _line(self, line: int) -> int:
        if isinstance(line, bool) or not isinstance(line, int) or not 0 <= line <= 7:
            raise PicError("BAD_LINE", f"IR line must be an integer in [0, 7], got {line!r}")
        return line

    def _byte(self, value: int, word: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
            raise PicError("BAD_OCW", f"{word} must be an integer in [0, 255], got {value!r}")
        return value
