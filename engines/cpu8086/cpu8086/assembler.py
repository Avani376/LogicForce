"""Assembler: source text → typed instruction IR (normative: cpu8086.md).

Diagnostics are typed ``AsmError`` objects carrying the 1-based line, a category,
and an actionable message. The IR is the executable image; ``IP`` indexes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cpu8086.errors import AsmError
from cpu8086.registers import BYTE_HALVES, SEG_REGS, WORD_REGS

WORD_REG_NAMES = set(WORD_REGS)
SEG_REG_NAMES = set(SEG_REGS)
BYTE_REG_NAMES = set(BYTE_HALVES)
ALL_REG_NAMES = WORD_REG_NAMES | SEG_REG_NAMES | BYTE_REG_NAMES

MNEMONICS_WITH_DEST_SRC = {
    "MOV",
    "ADD",
    "ADC",
    "SUB",
    "SBB",
    "CMP",
    "AND",
    "OR",
    "XOR",
    "TEST",
}
MNEMONICS_UNARY = {"INC", "DEC", "NEG", "NOT", "PUSH", "POP"}
MNEMONICS_INTERRUPT = {"INT", "IRET", "STI", "CLI"}
MNEMONICS_IO = {"IN", "OUT"}
MNEMONICS_JUMP = {
    "JMP",
    "JZ",
    "JE",
    "JNZ",
    "JNE",
    "JC",
    "JB",
    "JNC",
    "JAE",
    "JS",
    "JNS",
    "JO",
    "JNO",
    "JCXZ",
    "LOOP",
    "CALL",
}
MNEMONICS_NONE = {"RET", "NOP", "HLT"}
ALL_MNEMONICS = (
    MNEMONICS_WITH_DEST_SRC
    | MNEMONICS_UNARY
    | MNEMONICS_JUMP
    | MNEMONICS_NONE
    | MNEMONICS_INTERRUPT
    | MNEMONICS_IO
)

_BASE_COMBOS = {
    frozenset({"BX"}): "DS",
    frozenset({"BP"}): "SS",
    frozenset({"SI"}): "DS",
    frozenset({"DI"}): "DS",
    frozenset({"BX", "SI"}): "DS",
    frozenset({"BX", "DI"}): "DS",
    frozenset({"BP", "SI"}): "SS",
    frozenset({"BP", "DI"}): "SS",
}


@dataclass(frozen=True)
class Operand:
    kind: str  # "reg" | "seg" | "imm" | "mem"
    name: str = ""  # register/segment name (reg/seg kinds)
    value: int = 0  # immediate value (imm kind)
    label: str = ""  # symbolic jump target (jump-family operands only)
    width: int = 0  # 8 or 16; 0 = not yet pinned (mem without prefix — rejected later)
    mem_terms: tuple[str, ...] = ()  # base/index register terms (mem kind)
    mem_disp: int = 0  # displacement (mem kind)
    default_segment: str = "DS"  # segment for mem kind

    @property
    def is_memory(self) -> bool:
        return self.kind == "mem"


@dataclass(frozen=True)
class Instruction:
    index: int
    mnemonic: str
    dest: Operand | None
    src: Operand | None
    line: int
    text: str


@dataclass(frozen=True)
class AssembledProgram:
    instructions: tuple[Instruction, ...]
    labels: dict[str, int]
    source_lines: int


def _split_operands(text: str, line: int) -> list[str]:
    """Split on commas that are not inside brackets."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char == "[":
            depth += 1
            current.append(char)
        elif char == "]":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    if depth != 0:
        raise AsmError(line, "SYNTAX", "unbalanced brackets in operand")
    return [part for part in parts if part]


def _parse_number(text: str, line: int) -> int:
    text = text.strip()
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    value: int
    if text.lower().startswith("0x"):
        value = int(text, 16)
    elif text.lower().endswith("h") and len(text) > 1 and re.fullmatch(r"[0-9a-f]+h", text.lower()):
        value = int(text[:-1], 16)
    elif text.lower().endswith("b") and re.fullmatch(r"[01]+b", text.lower()):
        value = int(text[:-1], 2)
    elif text.isdigit():
        value = int(text, 10)
    else:
        raise AsmError(line, "SYNTAX", f"cannot parse number {text!r}")
    return -value if negative else value


def _parse_memory_operand(text: str, line: int, width: int) -> Operand:
    """Parse ``[terms]`` with optional BYTE/WORD prefix already stripped."""
    inner = text.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        raise AsmError(line, "SYNTAX", f"expected memory operand in brackets, got {text!r}")
    body = inner[1:-1].strip()
    if not body:
        raise AsmError(line, "SYNTAX", "empty memory operand")
    terms: list[str] = []
    displacement = 0
    for raw_term in re.split(r"\+", body):
        term = raw_term.strip().upper()
        if not term:
            raise AsmError(line, "SYNTAX", "empty term in memory operand")
        if term in ("BX", "BP", "SI", "DI"):
            terms.append(term)
        elif term in ALL_REG_NAMES:
            raise AsmError(line, "SYNTAX", f"{term!r} is not a valid base/index register")
        else:
            displacement += _parse_number(term.lower(), line)
    if len(terms) > 2:
        raise AsmError(line, "SYNTAX", f"too many base/index terms in {inner!r}")
    combo = frozenset(terms)
    if len(terms) == 2 and combo not in _BASE_COMBOS:
        raise AsmError(
            line,
            "SYNTAX",
            f"invalid base/index combination {body!r} — valid pairs: BX+SI, BX+DI, BP+SI, BP+DI",
        )
    if len(terms) == 1 and combo not in _BASE_COMBOS:
        raise AsmError(line, "SYNTAX", f"invalid base register {body!r}")
    default_segment = "SS" if "BP" in combo else "DS"
    if width == 0:
        raise AsmError(
            line,
            "SIZE_MISMATCH",
            "memory operand needs an explicit BYTE or WORD size prefix (e.g. 'MOV BYTE [BX], 7')",
        )
    return Operand(
        kind="mem",
        width=width,
        mem_terms=tuple(sorted(terms)),
        mem_disp=displacement,
        default_segment=default_segment,
    )


def _parse_operand(text: str, line: int) -> Operand:
    upper = text.upper()
    if upper in ALL_REG_NAMES:
        if upper in SEG_REG_NAMES:
            return Operand(kind="seg", name=upper, width=16)
        width = 8 if upper in BYTE_REG_NAMES else 16
        return Operand(kind="reg", name=upper, width=width)
    size = 0
    body = text
    parts = upper.split(maxsplit=1)
    if len(parts) == 2 and parts[0] in ("BYTE", "WORD"):
        size = 8 if parts[0] == "BYTE" else 16
        body = text.split(maxsplit=1)[1]
        upper_body = body.upper()
        if upper_body in ALL_REG_NAMES:
            raise AsmError(line, "SYNTAX", "size prefix is not valid on a register operand")
    if "[" in body:
        return _parse_memory_operand(body, line, size)
    if any(ch in body for ch in "+-") and "[" not in body:
        raise AsmError(line, "SYNTAX", f"arithmetic outside brackets is not supported: {text!r}")
    try:
        return Operand(kind="imm", value=_parse_number(body, line), width=size or 16)
    except AsmError:
        raise AsmError(line, "UNKNOWN_LABEL", f"unknown symbol or bad number {text!r}") from None


def _operand_width(operand: Operand) -> int:
    if operand.kind == "reg":
        return 8 if operand.name in BYTE_REG_NAMES else 16
    return operand.width


def _check_operand_compat(
    mnemonic: str, line: int, dest: Operand | None, src: Operand | None
) -> None:
    if dest is not None and dest.kind == "mem" and src is not None and src.kind == "mem":
        raise AsmError(line, "SYNTAX", "memory-to-memory operations are not supported")
    if dest is not None and dest.kind == "mem" and dest.width == 0:
        raise AsmError(
            line,
            "SIZE_MISMATCH",
            "memory operand needs an explicit BYTE or WORD size prefix",
        )
    if src is not None and src.kind == "mem" and src.width == 0:
        raise AsmError(
            line,
            "SIZE_MISMATCH",
            "memory operand needs an explicit BYTE or WORD size prefix",
        )
    if (
        src is not None
        and src.kind == "imm"
        and dest is not None
        and dest.kind in ("reg", "mem")
        and _operand_width(dest) == 8
        and not (-128 <= src.value <= 255)
    ):
        raise AsmError(line, "SIZE_MISMATCH", f"immediate {src.value} does not fit a byte operand")
    if (
        dest is not None
        and src is not None
        and dest.kind in ("reg", "mem")
        and src.kind in ("reg", "mem")
    ):
        dest_width = _operand_width(dest)
        src_width = _operand_width(src)
        if dest_width != src_width:
            raise AsmError(
                line,
                "SIZE_MISMATCH",
                f"operand size mismatch: {dest_width}-bit destination vs {src_width}-bit source",
            )


def _validate_signature(
    mnemonic: str, line: int, operands: list[Operand]
) -> tuple[Operand | None, Operand | None]:
    if mnemonic in MNEMONICS_WITH_DEST_SRC:
        if len(operands) != 2:
            raise AsmError(line, "BAD_OPERAND_COUNT", f"{mnemonic} requires exactly 2 operands")
        dest, src = operands[0], operands[1]
        _check_operand_compat(mnemonic, line, dest, src)
        return dest, src
    if mnemonic in MNEMONICS_UNARY:
        if len(operands) != 1:
            raise AsmError(line, "BAD_OPERAND_COUNT", f"{mnemonic} requires exactly 1 operand")
        operand = operands[0]
        if operand.kind == "mem" and operand.width == 0:
            raise AsmError(
                line,
                "SIZE_MISMATCH",
                f"{mnemonic} on memory needs an explicit BYTE or WORD size prefix",
            )
        if mnemonic in ("INC", "DEC", "NEG", "NOT") and operand.kind == "imm":
            raise AsmError(line, "SYNTAX", f"{mnemonic} cannot take an immediate operand")
        if mnemonic == "POP" and operand.kind == "imm":
            raise AsmError(line, "SYNTAX", "POP cannot take an immediate operand")
        if operand.kind == "seg" and mnemonic in ("INC", "DEC", "NEG", "NOT", "TEST"):
            raise AsmError(line, "SYNTAX", f"{mnemonic} cannot take a segment register")
        return operand, None
    if mnemonic in MNEMONICS_JUMP:
        if len(operands) != 1 or operands[0].kind != "imm":
            raise AsmError(line, "SYNTAX", f"{mnemonic} requires a label operand")
        return operands[0], None
    if mnemonic in MNEMONICS_IO:
        # IN AL, p(imm|DX) / OUT p(imm|DX), AL — accumulator port forms only
        if len(operands) != 2:
            raise AsmError(line, "BAD_OPERAND_COUNT", f"{mnemonic} requires exactly 2 operands")
        if mnemonic == "IN":
            dest, src = operands[0], operands[1]
            accumulator = dest
            port_operand = src
        else:
            dest, src = operands[0], operands[1]
            accumulator = src
            port_operand = dest
        if accumulator.kind != "reg" or accumulator.name != "AL":
            raise AsmError(
                line,
                "SYNTAX",
                f"{mnemonic} byte form requires AL as accumulator (IN AL, p / OUT p, AL)",
            )
        if port_operand.kind == "reg" and port_operand.name == "DX":
            resolved_port = Operand(kind="reg", name="DX", width=16)
        elif port_operand.kind == "imm" and 0 <= port_operand.value <= 0xFFFF:
            resolved_port = Operand(kind="imm", value=port_operand.value, width=16)
        else:
            raise AsmError(line, "SYNTAX", f"{mnemonic} port must be an immediate 0-0xFFFF or DX")
        if mnemonic == "IN":
            return dest, resolved_port
        return resolved_port, accumulator
        raise AsmError(line, "SYNTAX", f"{mnemonic} port must be an immediate 0-0xFFFF or DX")
    if mnemonic in MNEMONICS_INTERRUPT:
        if mnemonic == "INT":
            if len(operands) != 1 or operands[0].kind != "imm":
                raise AsmError(line, "SYNTAX", "INT requires a numeric operand (0-255)")
            value = int(operands[0].value)
            if not 0 <= value <= 255:
                raise AsmError(line, "SYNTAX", f"INT number must be in [0, 255], got {value}")
            return operands[0], None
        if operands:
            raise AsmError(line, "BAD_OPERAND_COUNT", f"{mnemonic} takes no operands")
        return None, None
    if mnemonic in MNEMONICS_NONE:
        if operands:
            raise AsmError(line, "BAD_OPERAND_COUNT", f"{mnemonic} takes no operands")
        return None, None
    raise AsmError(line, "UNKNOWN_MNEMONIC", f"unknown mnemonic {mnemonic!r}")


def assemble(source: str) -> AssembledProgram:
    """Assemble source text into the executable IR (fail-fast per error; the first
    error is raised with its line — batch mode is a Phase 7 nicety)."""
    instructions: list[Instruction] = []
    labels: dict[str, int] = {}
    pending_labels: list[tuple[str, int]] = []
    lines = source.splitlines()

    for line_number, raw_line in enumerate(lines, start=1):
        text = raw_line.split(";", 1)[0].strip()
        if not text:
            continue

        # labels: `name:` possibly followed by an instruction
        while True:
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", text)
            if match is None:
                break
            label = match.group(1).upper()
            if label in labels or any(name == label for name, _ in pending_labels):
                raise AsmError(line_number, "DUPLICATE_LABEL", f"label {label!r} already defined")
            pending_labels.append((label, line_number))
            text = match.group(2).strip()
            if not text:
                break
        if not text:
            continue

        parts = text.split(maxsplit=1)
        mnemonic = parts[0].upper()
        if mnemonic not in ALL_MNEMONICS:
            raise AsmError(
                line_number,
                "UNKNOWN_MNEMONIC",
                f"unknown mnemonic {mnemonic!r} — see the declared subset",
            )
        operand_text = parts[1] if len(parts) == 2 else ""
        raw_operands = _split_operands(operand_text, line_number)
        if mnemonic in MNEMONICS_JUMP:
            # jump-family operands are LABELS (identifiers), resolved in pass 2;
            # numeric operands are absolute instruction indices (documented)
            if len(raw_operands) != 1:
                raise AsmError(
                    line_number, "BAD_OPERAND_COUNT", f"{mnemonic} requires exactly 1 label operand"
                )
            target_text = raw_operands[0]
            try:
                numeric = _parse_number(target_text, line_number)
            except AsmError:
                numeric = None
            if numeric is not None and not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", target_text.strip()
            ):
                operands = [Operand(kind="imm", value=numeric, width=16)]
            else:
                label_name = target_text.strip().upper()
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label_name):
                    raise AsmError(line_number, "SYNTAX", f"bad jump target {target_text!r}")
                operands = [Operand(kind="imm", label=label_name, width=16)]
            dest, src = _validate_signature(mnemonic, line_number, operands)
        else:
            operands = [_parse_operand(o, line_number) for o in raw_operands]
            dest, src = _validate_signature(mnemonic, line_number, operands)

        index = len(instructions)
        for label, _ in pending_labels:
            labels[label] = index
        pending_labels = []

        instructions.append(
            Instruction(
                index=index,
                mnemonic=mnemonic,
                dest=dest,
                src=src,
                line=line_number,
                text=text,
            )
        )

    if pending_labels:
        label, line_number = pending_labels[-1]
        raise AsmError(
            line_number, "UNKNOWN_LABEL", f"label {label!r} points past the last instruction"
        )

    # second pass: resolve symbolic label targets to instruction indices
    resolved: list[Instruction] = []
    for instruction in instructions:
        if (
            instruction.mnemonic in MNEMONICS_JUMP
            and instruction.dest is not None
            and instruction.dest.label
        ):
            label = instruction.dest.label
            if label not in labels:
                raise AsmError(instruction.line, "UNKNOWN_LABEL", f"label {label!r} is not defined")
            instruction = Instruction(
                index=instruction.index,
                mnemonic=instruction.mnemonic,
                dest=Operand(kind="imm", value=labels[label], width=16),
                src=None,
                line=instruction.line,
                text=instruction.text,
            )
        resolved.append(instruction)

    return AssembledProgram(instructions=tuple(resolved), labels=labels, source_lines=len(lines))
