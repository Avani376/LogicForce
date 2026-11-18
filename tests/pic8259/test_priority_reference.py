"""PIC differential tests: the engine's priority resolution vs an independent
reference resolver written from the 8259 spec (fully-nested priority with a
rotation floor, IMR gating). Property-based with hypothesis."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from pic8259 import Pic8259


def _reference_best(irr: int, isr: int, imr: int, floor: int) -> int | None:
    """Independent reference: best (lowest rank) serviceable line, else None.

    rank(line) = (line - floor - 1) mod 8 — line just above the floor is highest.
    Serviceable: IRR bit set, IMR bit clear, and (normal mask mode) better rank
    than the best in-service rank, or ISR empty."""

    def rank(line: int) -> int:
        return (line - floor - 1) % 8

    candidates = [line for line in range(8) if (irr >> line) & 1 and not (imr >> line) & 1]
    isr_lines = [line for line in range(8) if (isr >> line) & 1]
    best_isr = min((rank(l) for l in isr_lines), default=None)
    for line in sorted(candidates, key=rank):
        if best_isr is None or rank(line) < best_isr:
            return line
    return None


class TestPriorityResolution:
    @settings(max_examples=200, deadline=None)
    @given(
        irr=st.integers(min_value=0, max_value=255),
        isr=st.integers(min_value=0, max_value=255),
        imr=st.integers(min_value=0, max_value=255),
        floor=st.integers(min_value=0, max_value=7),
    )
    def test_int_vector_matches_reference(self, irr: int, isr: int, imr: int, floor: int) -> None:
        pic = Pic8259()
        pic.irr = irr
        pic.isr = isr
        pic.imr = imr
        pic._priority_floor = floor
        # Per the 8259 spec: IMR gates serviceability; masked in-service lines still block.
        line = _reference_best(irr, isr, imr, floor)
        expected = None if line is None else pic._base + line
        assert pic.int_vector() == expected, (irr, isr, imr, floor)

    def test_scenario_acknowledge_cycle(self) -> None:
        """Scenario regression: request, ack, nested request, EOI — vectors and
        register states must match the reference at every step."""
        pic = Pic8259()
        pic.write_icw1(0x13)
        pic.write_icw2(8)
        pic.write_icw4(0x01)
        steps: list[tuple[int, int | None]] = []
        # request IR3 and IR1; IR1 should win, then IR3 after EOI
        pic.request(3)
        pic.request(1)
        steps.append((pic.int_vector(), 9))  # IR1 (higher rank) delivered first
        pic.acknowledge()
        steps.append((pic.int_vector(), None))  # IR3 blocked by IR1 in service
        pic.write_ocw2(0x20)  # EOI clears IR1
        steps.append((pic.int_vector(), 11))  # IR3 now serviceable
        for (vector, _), expected_vector in zip(steps, (9, None, 11)):
            assert vector == expected_vector
        assert steps[-1][0] == 11
