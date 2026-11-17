"""Interrupt controller: IVT, pending queues, deterministic firing (interrupts.md)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from cpu8086.errors import AsmError

MAX_NESTING = 8


@dataclass(frozen=True)
class ScheduledInterrupt:
    source: str  # "nmi" | "intr"
    at_step: int
    number: int

    def __post_init__(self) -> None:
        if self.source not in ("nmi", "intr"):
            raise AsmError(0, "SYNTAX", f"interrupt source must be 'nmi' or 'intr', got {self.source!r}")
        if isinstance(self.at_step, bool) or not isinstance(self.at_step, int) or self.at_step < 0:
            raise AsmError(0, "SYNTAX", f"at_step must be a non-negative integer, got {self.at_step!r}")
        if isinstance(self.number, bool) or not isinstance(self.number, int) or not 0 <= self.number <= 255:
            raise AsmError(0, "SYNTAX", f"interrupt number must be in [0, 255], got {self.number!r}")


@dataclass
class InterruptController:
    """Deterministic interrupt state: IVT, schedules, pending maskable queue."""

    ivt: dict[int, int] = field(default_factory=dict)
    scheduled: tuple[ScheduledInterrupt, ...] = field(default_factory=tuple)
    depth: int = 0
    pending_intr: deque[int] = field(default_factory=deque)
    _schedule_index: int = 0

    def __post_init__(self) -> None:
        for scheduled in self.scheduled:
            if scheduled.number not in self.ivt:
                raise AsmError(
                    0,
                    "UNKNOWN_LABEL",
                    f"scheduled {scheduled.source} interrupt {scheduled.number} has no IVT entry",
                )

    def due_now(self, steps_taken: int) -> ScheduledInterrupt | None:
        """The next scheduled interrupt whose boundary is `steps_taken` (None = none due)."""
        while self._schedule_index < len(self.scheduled):
            scheduled = self.scheduled[self._schedule_index]
            if scheduled.at_step < steps_taken:
                self._schedule_index += 1  # past boundary — skip (defensive)
                continue
            if scheduled.at_step == steps_taken:
                self._schedule_index += 1
                return scheduled
            return None  # future boundary
        return None

    def fire_software(self, number: int) -> int:
        """INT n dispatch; returns the handler index."""
        return self._fire(number)

    def raise_external(self, scheduled: ScheduledInterrupt) -> bool:
        """Offer an external interrupt. NMI always fires; INTR waits for IF=1.

        Returns True if it fired now (the caller performs the firing sequence);
        False if a maskable INTR is parked pending (caller checks `take_pending`).
        """
        if scheduled.source == "nmi":
            self._fire(scheduled.number)
            return True
        return False  # INTR parked: caller consults take_pending at each boundary

    def park_pending(self, number: int) -> None:
        self.pending_intr.append(number)

    def take_pending(self) -> int | None:
        """The next pending maskable interrupt (caller gates on IF=1)."""
        if self.pending_intr:
            return self.pending_intr.popleft()
        return None

    def _fire(self, number: int) -> int:
        if self.depth >= MAX_NESTING:
            raise AsmError(0, "SYNTAX", f"interrupt nesting exceeds the cap of {MAX_NESTING}")
        if number not in self.ivt:
            raise AsmError(0, "UNKNOWN_LABEL", f"IVT has no handler for interrupt {number}")
        self.depth += 1
        return self.ivt[number]

    def retire(self) -> None:
        """IRET: one handler frame returns."""
        if self.depth > 0:
            self.depth -= 1
