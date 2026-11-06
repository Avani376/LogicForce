"""Phase C7 unit tests: resolve_pic_flow — scheduled events, delivery trace."""

from __future__ import annotations

import pytest

from pic8259 import EVENT_OPS, PicConfig, PicEvent, PicError, resolve_pic_flow


def _vectors(result: object) -> list[tuple[int, int, int]]:
    return [(d.at_step, d.line, d.vector) for d in result.deliveries]  # type: ignore[attr-defined]


class TestConfigValidation:
    def test_base_vector_must_be_multiple_of_8(self) -> None:
        with pytest.raises(PicError) as exc:
            PicConfig(base_vector=12)
        assert exc.value.category == "BAD_VECTOR_BASE"

    def test_base_vector_range(self) -> None:
        with pytest.raises(PicError):
            PicConfig(base_vector=256)

    def test_event_op_whitelist(self) -> None:
        with pytest.raises(PicError) as exc:
            PicEvent(0, "poll")
        assert exc.value.category == "BAD_EVENT"
        assert set(EVENT_OPS) == {"request", "eoi", "seoi", "rotate_eoi", "set_priority", "mask"}

    def test_event_step_bounds(self) -> None:
        with pytest.raises(PicError):
            PicEvent(-1, "request", line=0)
        with pytest.raises(PicError):
            PicEvent(1_000_001, "request", line=0)

    def test_event_line_bounds(self) -> None:
        with pytest.raises(PicError):
            PicEvent(0, "request", line=9)


class TestDelivery:
    def test_empty_events_no_deliveries(self) -> None:
        result = resolve_pic_flow(PicConfig(base_vector=8), [])
        assert result.deliveries == ()
        assert result.scope == "EXHAUSTIVE(0)"

    def test_single_request_delivers_immediately(self) -> None:
        result = resolve_pic_flow(PicConfig(base_vector=32), [PicEvent(4, "request", line=2)])
        assert _vectors(result) == [(4, 2, 34)]
        assert result.final_isr == 1 << 2

    def test_same_boundary_two_requests_one_inta_then_next_boundary(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8),
            [PicEvent(2, "request", line=5), PicEvent(2, "request", line=1)],
        )
        # IR5 delivers at the request boundary (ISR empty); IR1 (higher priority)
        # becomes serviceable mid-boundary but the INTA is taken — next boundary.
        assert _vectors(result) == [(2, 5, 13), (3, 1, 9)]

    def test_nonspecific_eoi_clears_best_isr_rank(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8),
            [
                PicEvent(2, "request", line=5),
                PicEvent(2, "request", line=1),
                PicEvent(10, "eoi"),
            ],
        )
        # IR5 delivers at 2 (ISR empty), IR1 nests at 3 (higher priority, next
        # INTA). EOI at 10 clears IR1 (best rank); IR5 remains in service.
        assert _vectors(result) == [(2, 5, 13), (3, 1, 9)]
        assert result.final_isr == 1 << 5

    def test_masked_request_waits_for_unmask(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=16),
            [
                PicEvent(1, "mask", line=3, masked=True),
                PicEvent(2, "request", line=3),
                PicEvent(5, "mask", line=3, masked=False),
            ],
        )
        assert _vectors(result) == [(5, 3, 19)]

    def test_seoi_clears_only_named_level(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8),
            [
                PicEvent(1, "request", line=2),
                PicEvent(2, "request", line=6),  # lower priority: waits
                PicEvent(4, "seoi", line=2),
            ],
        )
        # IR2 delivers at 1; IR6 blocked; specific EOI of IR2 at 4 releases IR6.
        assert _vectors(result) == [(1, 2, 10), (4, 6, 14)]

    def test_rotation_reorders_priority(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8),
            [
                PicEvent(1, "request", line=2),
                PicEvent(3, "rotate_eoi"),  # clear IR2, floor ← IR2 → IR3 highest
                PicEvent(4, "request", line=2),
                PicEvent(5, "request", line=3),
            ],
        )
        # At 4: IR2 delivers (ISR empty). At 5: IR3 now outranks IR2 in service.
        assert _vectors(result) == [(1, 2, 10), (4, 2, 10), (5, 3, 11)]

    def test_aeoi_flow_leaves_isr_clear(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8, aeoi=True),
            [PicEvent(1, "request", line=2), PicEvent(2, "request", line=4)],
        )
        assert _vectors(result) == [(1, 2, 10), (2, 4, 12)]
        assert result.final_isr == 0

    def test_set_priority_demotes_pending_request(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8),
            [
                PicEvent(1, "request", line=0),
                PicEvent(2, "request", line=1),  # blocked by IR0 in service
                PicEvent(3, "set_priority", line=4),  # floor ← IR4 → IR0 rank (0-4-1)%8=3, IR1 rank (1-4-1)%8=4
            ],
        )
        # IR1 stays blocked (IR0 in service still outranks it under the new floor).
        assert _vectors(result) == [(1, 0, 8)]

    def test_trace_records_all_kinds(self) -> None:
        result = resolve_pic_flow(
            PicConfig(base_vector=8),
            [PicEvent(1, "request", line=2), PicEvent(3, "eoi")],
        )
        kinds = [e.kind for e in result.trace]
        assert "init" in kinds
        assert "request" in kinds
        assert "ack" in kinds
        assert "eoi" in kinds

    def test_determinism_byte_identical(self) -> None:
        events = [PicEvent(1, "request", line=2), PicEvent(2, "request", line=1), PicEvent(5, "eoi")]
        a = resolve_pic_flow(PicConfig(base_vector=8), list(events)).to_json()
        b = resolve_pic_flow(PicConfig(base_vector=8), list(events)).to_json()
        assert a == b

    def test_scope_label_exhaustive(self) -> None:
        events = [PicEvent(1, "request", line=2), PicEvent(2, "eoi")]
        result = resolve_pic_flow(PicConfig(base_vector=8), events)
        assert result.scope == "EXHAUSTIVE(2)"
        assert result.engine_version
