"""Scheduled-event driver: line requests + EOI commands → deterministic delivery trace.

The driver models an accepting CPU (IF=1): a delivery is the boundary at which
the INT line rises with a vector. CPU-side IF gating is layered on top by the
existing cpu8086 interrupt controller when a PIC-derived schedule runs there.
One INTA per boundary (documented in pic8259.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from pic8259.controller import Pic8259, PicTraceEvent
from pic8259.errors import PicError
from pic8259.version import PIC8259_ENGINE_VERSION

#: Operations a scheduled event can carry.
EVENT_OPS = ("request", "eoi", "seoi", "rotate_eoi", "set_priority", "mask")

#: Upper bound on a scheduled boundary (keeps the boundary walk bounded like the CPU step cap).
MAX_BOUNDARY = 1_000_000


@dataclass(frozen=True)
class PicEvent:
    """One scheduled PIC operation at an instruction boundary (`at_step` semantics
    match cpu8086 `ScheduledInterrupt`: after step k, before step k+1)."""

    at_step: int
    op: str
    line: int = 0
    masked: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.at_step, bool) or not isinstance(self.at_step, int) or not 0 <= self.at_step <= MAX_BOUNDARY:
            raise PicError(
                "BAD_EVENT",
                f"at_step must be an integer in [0, {MAX_BOUNDARY}], got {self.at_step!r}",
            )
        if self.op not in EVENT_OPS:
            raise PicError(
                "BAD_EVENT",
                f"op must be one of {', '.join(EVENT_OPS)}, got {self.op!r}",
            )
        if isinstance(self.line, bool) or not isinstance(self.line, int) or not 0 <= self.line <= 7:
            raise PicError("BAD_EVENT", f"line must be an integer in [0, 7], got {self.line!r}")
        if not isinstance(self.masked, bool):
            raise PicError("BAD_EVENT", f"masked must be a boolean, got {self.masked!r}")


@dataclass(frozen=True)
class PicConfig:
    """Init-time configuration, expressed through the ICW sequence."""

    base_vector: int = 8
    aeoi: bool = False
    single: bool = True

    def __post_init__(self) -> None:
        if (
            isinstance(self.base_vector, bool)
            or not isinstance(self.base_vector, int)
            or not 0 <= self.base_vector <= 248
        ):
            raise PicError(
                "BAD_VECTOR_BASE",
                f"base_vector must be an integer in [0, 248] and a multiple of 8, got {self.base_vector!r}",
            )
        if self.base_vector % 8 != 0:
            raise PicError("BAD_VECTOR_BASE", f"base_vector must be a multiple of 8, got {self.base_vector}")
        if not isinstance(self.aeoi, bool) or not isinstance(self.single, bool):
            raise PicError("BAD_OCW", "aeoi and single must be booleans")


@dataclass(frozen=True)
class PicDelivery:
    """The INT line rising with a vector at an instruction boundary."""

    at_step: int
    line: int
    vector: int


@dataclass
class PicFlowResult:
    """EXHAUSTIVE resolution of a scheduled PIC flow — every event, every transition."""

    deliveries: tuple[PicDelivery, ...]
    trace: tuple[PicTraceEvent, ...]
    final_irr: int
    final_isr: int
    final_imr: int
    scope: str = ""
    engine_version: str = ""

    def to_json(self) -> dict[str, object]:
        return {
            "deliveries": [{"at_step": d.at_step, "line": d.line, "vector": d.vector} for d in self.deliveries],
            "trace": [e.to_json() for e in self.trace],
            "final_registers": {"IRR": self.final_irr, "ISR": self.final_isr, "IMR": self.final_imr},
            "scope": self.scope,
            "engine_version": self.engine_version,
        }


def _program(pic: Pic8259, config: PicConfig) -> None:
    """Run the ICW sequence implied by `config` (single-chip educational subset)."""
    icw1 = 0x11  # IC4=1 (we always write ICW4), edge-triggered
    if config.single:
        icw1 |= 0x02  # SNGL=1 — single chip, no ICW3
    pic.write_icw1(icw1)
    pic.write_icw2(config.base_vector)
    if not config.single:
        pic.write_icw3(0x00)  # no slaves attached (cascade routing out of scope)
    icw4 = 0x01  # μPM=1 — 8086 mode
    if config.aeoi:
        icw4 |= 0x02
    pic.write_icw4(icw4)


def _apply(pic: Pic8259, event: PicEvent, at_step: int) -> None:
    if event.op == "request":
        pic.request(event.line, at_step=at_step)
    elif event.op == "eoi":
        pic.write_ocw2(0x20, at_step=at_step)  # non-specific EOI
    elif event.op == "seoi":
        pic.write_ocw2(0x60 | event.line, at_step=at_step)  # specific EOI
    elif event.op == "rotate_eoi":
        pic.write_ocw2(0xA0, at_step=at_step)  # rotate on non-specific EOI (R=1, SL=0, EOI=1)
    elif event.op == "set_priority":
        pic.write_ocw2(0x80 | event.line, at_step=at_step)  # set priority (R=1, SL=0, EOI=0)
    elif event.op == "mask":
        new_imr = (pic.read_imr() | (1 << event.line)) if event.masked else (pic.read_imr() & ~(1 << event.line))
        pic.write_ocw1(new_imr & 0xFF, at_step=at_step)


def resolve_pic_flow(config: PicConfig, events: list[PicEvent]) -> PicFlowResult:
    """Process `events` in boundary order (stable for equal `at_step`). After each
    event the INT line is checked; at most one INTA per boundary — a vector that
    becomes serviceable after a delivery holds until the next boundary. Every
    event is processed — the result is labeled EXHAUSTIVE(len(events))."""
    pic = Pic8259()
    _program(pic, config)
    ordered = sorted(events, key=lambda e: e.at_step)  # stable: list order kept for ties
    deliveries: list[PicDelivery] = []
    last_boundary = max((e.at_step for e in ordered), default=-1)
    cursor = 0

    for boundary in range(last_boundary + 1):
        delivered_this_boundary = False
        while cursor < len(ordered) and ordered[cursor].at_step == boundary:
            _apply(pic, ordered[cursor], boundary)
            cursor += 1
            if not delivered_this_boundary:
                vector = pic.int_vector()
                if vector is not None:
                    pic.acknowledge(at_step=boundary)
                    deliveries.append(PicDelivery(at_step=boundary, line=vector - config.base_vector, vector=vector))
                    delivered_this_boundary = True
        if not delivered_this_boundary:
            # No more events here — but a vector held since an earlier boundary
            # (nested request waiting for its INTA) delivers at this one.
            vector = pic.int_vector()
            if vector is not None:
                pic.acknowledge(at_step=boundary)
                deliveries.append(PicDelivery(at_step=boundary, line=vector - config.base_vector, vector=vector))

    # Flush held vectors past the last event boundary: a nested request held at
    # boundary k gets its INTA at k+1. Bounded — each ack clears one IRR bit and
    # no new requests arrive after the last event.
    boundary = last_boundary + 1
    while pic.int_vector() is not None:
        vector = pic.int_vector()
        assert vector is not None  # narrows for mypy; re-checked by the loop condition
        pic.acknowledge(at_step=boundary)
        deliveries.append(PicDelivery(at_step=boundary, line=vector - config.base_vector, vector=vector))
        boundary += 1

    return PicFlowResult(
        deliveries=tuple(deliveries),
        trace=tuple(pic.trace),
        final_irr=pic.read_irr(),
        final_isr=pic.read_isr(),
        final_imr=pic.read_imr(),
        scope=f"EXHAUSTIVE({len(events)})",
        engine_version=PIC8259_ENGINE_VERSION,
    )
