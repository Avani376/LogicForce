"""Phase C7 unit tests: Pic8259 controller — init sequence, priority, EOI, masking."""

from __future__ import annotations

import pytest

from pic8259 import Pic8259, PicError


def _programmed(base: int = 8) -> Pic8259:
    pic = Pic8259()
    pic.write_icw1(0x13)  # IC4=1, SNGL=1, edge-triggered
    pic.write_icw2(base)
    pic.write_icw4(0x01)  # 8086 mode, no AEOI
    return pic


class TestInitSequence:
    def test_full_sequence_initializes(self) -> None:
        pic = _programmed(base=0x20)
        assert pic.int_vector() is None
        pic.request(3)
        assert pic.int_vector() == 0x23

    def test_ocw_before_init_rejected(self) -> None:
        pic = Pic8259()
        with pytest.raises(PicError) as exc:
            pic.write_ocw1(0xFF)
        assert exc.value.category == "NOT_INITIALIZED"

    def test_icw2_before_icw1_rejected(self) -> None:
        pic = Pic8259()
        with pytest.raises(PicError) as exc:
            pic.write_icw2(8)
        assert exc.value.category == "INIT_SEQUENCE"

    def test_icw4_when_not_expected_rejected(self) -> None:
        pic = Pic8259()
        pic.write_icw1(0x12)  # IC4=0, SNGL=1 — sequence completes after ICW2
        pic.write_icw2(8)
        assert pic.read_imr() == 0  # initialized and usable
        with pytest.raises(PicError) as exc:
            pic.write_icw4(0x01)
        assert exc.value.category == "INIT_SEQUENCE"

    def test_icw3_required_when_sngl_zero(self) -> None:
        pic = Pic8259()
        pic.write_icw1(0x11)  # IC4=0, SNGL=0
        pic.write_icw2(8)
        with pytest.raises(PicError) as exc:
            pic.write_ocw1(0)
        assert exc.value.category == "NOT_INITIALIZED"  # ICW3 still missing
        pic.write_icw3(0x00)
        assert pic.read_imr() == 0

    def test_vector_base_must_be_multiple_of_8(self) -> None:
        pic = Pic8259()
        pic.write_icw1(0x13)
        with pytest.raises(PicError) as exc:
            pic.write_icw2(12)
        assert exc.value.category == "BAD_VECTOR_BASE"

    def test_reinit_clears_state(self) -> None:
        pic = _programmed()
        pic.request(5)
        pic.write_icw1(0x13)  # re-init
        assert pic.read_irr() == 0
        with pytest.raises(PicError) as exc:
            pic.write_ocw1(0)
        assert exc.value.category == "NOT_INITIALIZED"  # sequence must restart


class TestPriorityAndAck:
    def test_ir0_highest_by_default(self) -> None:
        pic = _programmed()
        pic.request(7)
        pic.request(0)
        pic.request(4)
        assert pic.int_vector() == 8 + 0

    def test_ack_moves_irr_to_isr(self) -> None:
        pic = _programmed()
        pic.request(2)
        vector = pic.acknowledge()
        assert vector == 10
        assert pic.read_irr() == 0
        assert pic.read_isr() == 0x04

    def test_fully_nested_blocks_lower_priority(self) -> None:
        pic = _programmed()
        pic.request(2)
        pic.acknowledge()
        pic.request(5)  # lower priority than in-service IR2
        assert pic.int_vector() is None

    def test_higher_priority_interrupts_nested(self) -> None:
        pic = _programmed()
        pic.request(5)
        pic.acknowledge()
        pic.request(1)  # higher priority than in-service IR5
        assert pic.int_vector() == 9

    def test_ack_with_nothing_serviceable_raises(self) -> None:
        pic = _programmed()
        with pytest.raises(PicError) as exc:
            pic.acknowledge()
        assert exc.value.category == "BAD_OCW"

    def test_masked_request_records_in_irr_but_not_serviced(self) -> None:
        pic = _programmed()
        pic.write_ocw1(1 << 6)
        pic.request(6)
        assert pic.read_irr() == (1 << 6)
        assert pic.int_vector() is None
        pic.write_ocw1(0)
        assert pic.int_vector() == 8 + 6

    def test_bad_line_rejected(self) -> None:
        pic = _programmed()
        with pytest.raises(PicError) as exc:
            pic.request(8)
        assert exc.value.category == "BAD_LINE"


class TestEoiFamily:
    def test_nonspecific_eoi_clears_best_isr(self) -> None:
        pic = _programmed()
        pic.request(3)
        pic.acknowledge()
        pic.request(1)
        pic.acknowledge()
        assert pic.read_isr() == 0x0A  # IR1 + IR3
        pic.write_ocw2(0x20)  # non-specific EOI → clears IR1 (best rank)
        assert pic.read_isr() == 0x08
        pic.write_ocw2(0x20)
        assert pic.read_isr() == 0x00

    def test_specific_eoi(self) -> None:
        pic = _programmed()
        pic.request(4)
        pic.acknowledge()
        pic.write_ocw2(0x60 | 4)  # specific EOI IR4
        assert pic.read_isr() == 0

    def test_specific_eoi_requires_in_service(self) -> None:
        pic = _programmed()
        with pytest.raises(PicError) as exc:
            pic.write_ocw2(0x62)  # specific EOI IR2, nothing in service
        assert exc.value.category == "BAD_OCW"

    def test_nonspecific_eoi_with_empty_isr_rejected(self) -> None:
        pic = _programmed()
        with pytest.raises(PicError) as exc:
            pic.write_ocw2(0x20)
        assert exc.value.category == "BAD_OCW"

    def test_rotation_changes_priority_floor(self) -> None:
        pic = _programmed()
        pic.request(2)
        pic.acknowledge()
        pic.write_ocw2(0xA0)  # rotate on non-specific EOI: clear IR2, floor ← IR2
        assert pic.read_isr() == 0
        # With floor IR2, IR3 is now highest: IR2 and IR3 requested → IR3 first.
        pic.request(2)
        pic.request(3)
        assert pic.int_vector() == 8 + 3

    def test_set_priority_command(self) -> None:
        pic = _programmed()
        pic.write_ocw2(0x80 | 6)  # set priority: floor ← IR6 → IR7 highest
        pic.request(7)
        pic.request(0)
        assert pic.int_vector() == 8 + 7

    def test_aeoi_never_sets_isr(self) -> None:
        pic = Pic8259()
        pic.write_icw1(0x13)
        pic.write_icw2(8)
        pic.write_icw4(0x03)  # AEOI
        pic.request(1)
        vector = pic.acknowledge()
        assert vector == 9
        assert pic.read_isr() == 0


class TestOcw3:
    def test_special_mask_mode_lets_lower_priority_service(self) -> None:
        pic = _programmed()
        pic.request(1)
        pic.acknowledge()
        pic.request(5)
        assert pic.int_vector() is None  # normal mask mode blocks
        pic.write_ocw3(0x60)  # ESMM=1, SMM=1
        assert pic.int_vector() == 8 + 5  # SMM: ISR does not block
        pic.write_ocw3(0x40)  # ESMM=1, SMM=0 — back to normal
        assert pic.int_vector() is None

    def test_poll_mode_rejected(self) -> None:
        pic = _programmed()
        with pytest.raises(PicError) as exc:
            pic.write_ocw3(0x04)
        assert exc.value.category == "BAD_OCW"

    def test_status_read_selection(self) -> None:
        pic = _programmed()
        pic.request(2)
        pic.acknowledge()
        assert pic.read_status() == ("IRR", 0)
        pic.write_ocw3(0x03)  # RR=1, RIS=1 → read ISR
        assert pic.read_status() == ("ISR", 0x04)
