"""Assembler tests: parsing, labels, diagnostics, size rules."""

from __future__ import annotations

import pytest
from cpu8086 import AsmError, assemble
from cpu8086.assembler import assemble as assemble_direct


def test_simple_mov_assembles() -> None:
    program = assemble("MOV AX, 0x1234\nHLT")
    assert len(program.instructions) == 2
    assert program.instructions[0].mnemonic == "MOV"
    assert program.instructions[0].dest is not None
    assert program.instructions[0].dest.kind == "reg"
    assert program.instructions[0].src is not None
    assert program.instructions[0].src.kind == "imm"
    assert program.instructions[0].src.value == 0x1234


def test_labels_resolve_to_instruction_indices() -> None:
    program = assemble("start:\nMOV CX, 3\nloop_top:\nLOOP loop_top\nHLT\n")
    assert program.labels["START"] == 0
    assert program.labels["LOOP_TOP"] == 1
    # LOOP instruction resolved its label operand to the target index
    assert program.instructions[1].dest is not None
    assert program.instructions[1].dest.value == 1


def test_jump_forward_label() -> None:
    program = assemble("JMP end\nMOV AX, 1\nend:\nHLT")
    assert program.instructions[0].dest is not None
    assert program.instructions[0].dest.value == 2  # index of HLT


def test_comments_and_blank_lines_ignored() -> None:
    program = assemble("; header comment\n\nMOV AX, 1 ; trailing comment\nHLT\n")
    assert len(program.instructions) == 2


def test_case_insensitive_mnemonics_and_registers() -> None:
    program = assemble("mov ax, bx\nhlt")
    assert program.instructions[0].mnemonic == "MOV"
    assert program.instructions[0].src is not None
    assert program.instructions[0].src.name == "BX"


def test_hex_number_forms() -> None:
    program = assemble("MOV AX, 0x1A\nMOV BX, 2Bh\nMOV CX, 43")
    assert program.instructions[0].src is not None and program.instructions[0].src.value == 0x1A
    assert program.instructions[1].src is not None and program.instructions[1].src.value == 0x2B
    assert program.instructions[2].src is not None and program.instructions[2].src.value == 43


def test_memory_operands_parse_terms_and_defaults() -> None:
    program = assemble("MOV WORD [BX+SI+4], AX\nMOV BYTE [BP+2], 7\nMOV AX, WORD [1234]")
    mem = program.instructions[0].dest
    assert mem is not None and mem.kind == "mem"
    assert mem.mem_terms == ("BX", "SI")
    assert mem.mem_disp == 4
    assert mem.default_segment == "DS"
    bp_mem = program.instructions[1].dest
    assert bp_mem is not None and bp_mem.default_segment == "SS"
    direct = program.instructions[2].src
    assert direct is not None and direct.kind == "mem" and direct.mem_disp == 1234


@pytest.mark.parametrize(
    ("source", "category", "match"),
    [
        ("FLY AX, 1", "UNKNOWN_MNEMONIC", "unknown mnemonic"),
        ("MOV AX, 1\nBACK:\nJMP BACK\nBACK:", "DUPLICATE_LABEL", "already defined"),
        ("JMP nowhere", "UNKNOWN_LABEL", "not defined"),
        ("MOV AX", "BAD_OPERAND_COUNT", "exactly 2"),
        ("INC", "BAD_OPERAND_COUNT", "exactly 1"),
        ("ADD AL, BX", "SIZE_MISMATCH", "size mismatch"),
        ("MOV AX, BX, CX", "BAD_OPERAND_COUNT", "exactly 2"),
        ("MOV AX, [BX+BP]", "SYNTAX", "invalid base/index"),
        ("MOV AX, [CX]", "SYNTAX", "not a valid base/index register"),
        ("RET 1", "BAD_OPERAND_COUNT", "takes no operands"),
        ("NEG 5", "SYNTAX", "immediate"),
        ("POP 5", "SYNTAX", "immediate"),
        ("MOV BYTE AX, 1", "SYNTAX", "size prefix"),
        ("MOV [BX], AX", "SIZE_MISMATCH", "BYTE or WORD"),
        ("INC WORD [BX", "SYNTAX", "unbalanced"),
    ],
)
def test_asm_diagnostics(source: str, category: str, match: str) -> None:
    with pytest.raises(AsmError) as excinfo:
        assemble_direct(source)
    assert excinfo.value.category == category
    assert match.lower() in str(excinfo.value).lower()


def test_error_carries_line_number() -> None:
    with pytest.raises(AsmError) as excinfo:
        assemble("MOV AX, 1\nFLY CX, 2")
    assert excinfo.value.line == 2
    assert excinfo.value.category == "UNKNOWN_MNEMONIC"


def test_assemble_direct_alias_matches() -> None:
    assert assemble_direct("NOP").instructions[0].mnemonic == "NOP"


def test_label_only_line_points_at_next_instruction() -> None:
    program = assemble("top:\nNOP")
    assert program.labels["TOP"] == 0
