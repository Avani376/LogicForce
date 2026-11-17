"""Phase C9 tests: string instructions, DF flag, REP/REPE/REPNE prefixes."""

from __future__ import annotations

import pytest
from cpu8086.errors import AsmError
from cpu8086.machine import assemble_and_load
from cpu8086.timing import get_timing


def run(src: str):
    machine = assemble_and_load(src)
    machine.run()
    return machine


class TestDirectionFlag:
    def test_cld_increments_std_decrements(self) -> None:
        machine = run("MOV SI, 0x210\nMOV DI, 0x220\nMOV CX, 1\nSTD\nMOVSB\nCLD\nMOVSB\nHLT")
        # STD MOVSB: pointers decrement (write at 0x220/0x220); CLD MOVSB: back up.
        assert machine.registers.get("SI") == 0x210  # 0x210 → 0x20F → 0x210
        assert machine.registers.get("DI") == 0x220  # 0x220 → 0x21F → 0x220
        assert machine.memory.read_byte(0, 0x21F) == 0  # nothing landed between

    def test_df_initial_zero(self) -> None:
        machine = run("HLT")
        assert machine.registers.flags["DF"] == 0

    def test_std_cld_no_other_flags(self) -> None:
        machine = run("MOV AL, 1\nADD AL, 1\nSTD\nCLD\nHLT")
        assert machine.registers.flags["ZF"] == 0  # from ADD (AL=2), untouched by STD/CLD
        assert machine.registers.flags["DF"] == 0

    def test_df_restored_by_iret(self) -> None:
        machine = run("STI\nSTD\nMOV CX, 0\nwait:\nINC CX\nCMP CX, 20\nJNZ wait\nHLT\nisr:\nCLD\nIRET")
        # DF=1 pushed by the interrupt; handler CLD=0; IRET restores DF=1.
        assert machine.registers.flags["DF"] == 1


class TestMovs:
    def test_movsb_copies_bytes_forward(self) -> None:
        machine = run(
            "MOV AX, 0x1122\nMOV WORD [0x200], AX\nMOV BYTE [0x202], 0x33\n"
            "MOV SI, 0x200\nMOV DI, 0x300\nMOV CX, 5\nCLD\nREP MOVSB\nHLT"
        )
        assert machine.registers.get("CX") == 0
        assert machine.memory.read_word(0, 0x300) == 0x1122
        assert machine.memory.read_byte(0, 0x302) == 0x33
        assert machine.registers.get("SI") == 0x205
        assert machine.registers.get("DI") == 0x305

    def test_movsw_copies_words(self) -> None:
        machine = run("MOV WORD [0x200], 0xBEEF\nMOV SI, 0x200\nMOV DI, 0x400\nMOV CX, 1\nREP MOVSW\nHLT")
        assert machine.memory.read_word(0, 0x400) == 0xBEEF
        assert machine.registers.get("SI") == 0x202
        assert machine.registers.get("DI") == 0x402

    def test_movsb_without_rep_single_step(self) -> None:
        machine = run("MOV BYTE [0x210], 0x42\nMOV SI, 0x210\nMOV DI, 0x300\nMOVSB\nHLT")
        assert machine.memory.read_byte(0, 0x300) == 0x42
        assert machine.registers.get("CX") == 0  # CX untouched without REP

    def test_backward_copy_with_std(self) -> None:
        machine = run("MOV WORD [0x210], 0x1234\nMOV SI, 0x211\nMOV DI, 0x411\nMOV CX, 2\nSTD\nREP MOVSB\nHLT")
        assert machine.memory.read_word(0, 0x410) == 0x1234
        assert machine.registers.get("SI") == 0x20F
        assert machine.registers.get("DI") == 0x40F


class TestStosLods:
    def test_stosb_fills(self) -> None:
        machine = run("MOV AL, 0xAB\nMOV DI, 0x400\nMOV CX, 4\nREP STOSB\nHLT")
        assert machine.memory.read_word(0, 0x400) == 0xABAB
        assert machine.memory.read_byte(0, 0x402) == 0xAB
        assert machine.registers.get("DI") == 0x404

    def test_stosw_fills_words(self) -> None:
        machine = run("MOV AX, 0x5A5A\nMOV DI, 0x400\nMOV CX, 2\nREP STOSW\nHLT")
        assert machine.memory.read_word(0, 0x400) == 0x5A5A
        assert machine.memory.read_word(0, 0x402) == 0x5A5A
        assert machine.registers.get("DI") == 0x404

    def test_lodsb_loads(self) -> None:
        machine = run("MOV BYTE [0x210], 0x5A\nMOV SI, 0x210\nLODSB\nHLT")
        assert machine.registers.get("AL") == 0x5A
        assert machine.registers.get("SI") == 0x211


class TestScasCmps:
    def test_repne_scasb_finds_byte(self) -> None:
        machine = run("MOV BYTE [0x402], 0x33\nMOV AL, 0x33\nMOV DI, 0x400\nMOV CX, 8\nREPNE SCASB\nHLT")
        # Found at offset 2: DI points past it (0x403), CX = 8 - 3 = 5, ZF = 1.
        assert machine.registers.get("DI") == 0x403
        assert machine.registers.get("CX") == 5
        assert machine.registers.flags["ZF"] == 1

    def test_repne_scasb_not_found_exhausts_cx(self) -> None:
        machine = run("MOV AL, 0x33\nMOV DI, 0x400\nMOV CX, 8\nREPNE SCASB\nHLT")
        assert machine.registers.get("CX") == 0
        assert machine.registers.get("DI") == 0x408
        assert machine.registers.flags["ZF"] == 0  # last comparison failed

    def test_repe_cmpsb_equal_runs_to_completion(self) -> None:
        machine = run(
            "MOV BYTE [0x210], 0x42\nMOV BYTE [0x220], 0x42\nMOV SI, 0x210\nMOV DI, 0x220\nMOV CX, 1\nREPE CMPSB\nHLT"
        )
        assert machine.registers.get("CX") == 0
        assert machine.registers.flags["ZF"] == 1
        assert machine.registers.get("SI") == 0x211

    def test_repe_cmpsb_stops_on_mismatch(self) -> None:
        machine = run(
            "MOV BYTE [0x210], 0x42\nMOV BYTE [0x220], 0x42\nMOV BYTE [0x221], 0x99\n"
            "MOV SI, 0x210\nMOV DI, 0x220\nMOV CX, 5\nREPE CMPSB\nHLT"
        )
        # Byte 0 matches; byte 1 (0x42 vs 0x99) mismatches → stop with CX = 3.
        assert machine.registers.get("CX") == 3
        assert machine.registers.flags["ZF"] == 0
        assert machine.registers.get("SI") == 0x212

    def test_cmpsw_compares_words(self) -> None:
        machine = run(
            "MOV WORD [0x210], 0x4142\nMOV WORD [0x220], 0x4143\n"
            "MOV SI, 0x210\nMOV DI, 0x220\nMOV CX, 1\nREPE CMPSW\nHLT"
        )
        assert machine.registers.get("CX") == 0
        assert machine.registers.flags["ZF"] == 0


class TestRepSemantics:
    def test_cx_zero_is_a_noop(self) -> None:
        machine = run("MOV AL, 0x77\nMOV DI, 0x400\nMOV CX, 0\nREP STOSB\nHLT")
        assert machine.registers.get("DI") == 0x400  # untouched
        assert machine.memory.read_byte(0, 0x400) == 0
        assert machine.registers.flags["ZF"] == 0  # no comparison ran, flags untouched

    def test_rep_is_one_step_in_trace(self) -> None:
        machine = assemble_and_load("MOV AL, 1\nMOV DI, 0x400\nMOV CX, 100\nREP STOSB\nHLT")
        trace, reason = machine.run(max_steps=50)
        assert reason == "hlt"
        rep_records = [r for r in trace if r.instruction == "REP STOSB"]
        assert len(rep_records) == 1  # whole repeat is one step
        assert rep_records[0].memory_changes is not None
        assert len(rep_records[0].register_changes) >= 2  # DI and CX changed

    def test_trace_shows_full_source_text_with_prefix(self) -> None:
        machine = assemble_and_load("MOV DI, 0x400\nMOV CX, 2\nREP STOSB\nHLT")
        trace, _ = machine.run(max_steps=10)
        assert any(r.instruction == "REP STOSB" for r in trace)


class TestAssemblyDiagnostics:
    def test_rep_without_string_op_rejected(self) -> None:
        with pytest.raises(AsmError) as exc:
            assemble_and_load("REP NOP")
        assert exc.value.category == "UNSUPPORTED_INSTRUCTION"

    def test_repe_with_non_conditional_op_rejected(self) -> None:
        with pytest.raises(AsmError) as exc:
            assemble_and_load("REPE MOVSB")
        assert exc.value.category == "SYNTAX"

    def test_string_op_with_operands_rejected(self) -> None:
        with pytest.raises(AsmError) as exc:
            assemble_and_load("MOVSB AL, BL")
        assert exc.value.category == "BAD_OPERAND_COUNT"

    def test_bare_rep_rejected(self) -> None:
        with pytest.raises(AsmError) as exc:
            assemble_and_load("REP")
        assert exc.value.category == "SYNTAX"


class TestTiming:
    def test_published_string_timings(self) -> None:
        assert get_timing("MOVSB").base_cycles == 18
        assert get_timing("MOVSW").base_cycles == 26
        assert get_timing("REPNE").base_cycles == 0  # prefix, not an instruction
        assert get_timing("STD").base_cycles == 2
