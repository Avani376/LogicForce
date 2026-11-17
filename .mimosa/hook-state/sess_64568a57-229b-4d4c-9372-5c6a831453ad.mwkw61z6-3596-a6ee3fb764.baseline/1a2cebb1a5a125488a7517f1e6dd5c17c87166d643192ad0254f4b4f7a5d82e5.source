"""Interrupt-aware machine: wires the controller into step/run (interrupts.md).

External interrupts are scheduled at instruction boundaries (deterministic);
software INT n / IRET / STI / CLI execute as instructions. Trace records gain a
`kind` field; ordinary instruction records default to kind "instruction".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from cpu8086.assembler import AssembledProgram, Instruction, Operand, assemble
from cpu8086.errors import AsmError, CpuRuntimeError, UnsupportedInstructionError
from cpu8086.interrupts import (
    InterruptController,
    ScheduledInterrupt,
)
from cpu8086.memory import Memory, physical
from cpu8086.registers import (
    BYTE_HALVES,
    Registers,
    add_flags,
    inc_dec_flags,
    logic_flags,
    mul_flags,
    neg_flags,
    sub_flags,
)
from cpu8086.version import MAX_RUN_STEPS, POWER_ON_SP

_ARITHMETIC = {
    "ADD",
    "ADC",
    "SUB",
    "SBB",
    "CMP",
    "AND",
    "OR",
    "XOR",
    "TEST",
    "INC",
    "DEC",
    "NEG",
}

_MULTIPLY_DIVIDE = {"MUL", "IMUL", "DIV", "IDIV"}
_STRING_OPS = {"MOVSB", "MOVSW", "STOSB", "STOSW", "LODSB", "LODSW", "SCASB", "SCASW", "CMPSB", "CMPSW"}
_JUMP_MNEMONICS = {
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
}


@dataclass(frozen=True)
class TraceRecord:
    kind: str  # "instruction" | "interrupt" | "iret" | "pending_intr"
    step: int
    ip: int
    instruction: str = ""
    register_changes: dict[str, int] = field(default_factory=dict)
    flag_changes: dict[str, int] = field(default_factory=dict)
    memory_changes: tuple[tuple[int, int], ...] = field(default_factory=tuple)
    halted: bool = False
    number: int | None = None  # interrupt/iret only
    source: str | None = None  # interrupt only
    handler: int | None = None  # interrupt only
    resumed_at: int | None = None  # iret only


@dataclass
class Cpu:
    """Deterministic IR-level 8086 machine with interrupt support."""

    program: AssembledProgram
    interrupts: InterruptController = field(default_factory=InterruptController)
    registers: Registers = field(default_factory=Registers)
    memory: Memory = field(default_factory=Memory)
    halted: bool = False
    port_reader: object | None = None  # Callable[[int], int] | None — unconnected ports read 0xFF
    port_writer: object | None = None  # Callable[[int, int], None] | None — writes to unconnected ports are ignored
    _steps_taken: int = 0
    _last_run: tuple[TraceRecord, ...] = ()

    def __post_init__(self) -> None:
        self.registers.set("SP", POWER_ON_SP)

    def _read_port(self, port: int) -> int:
        import typing

        if typing.cast("typing.Callable[[int], int] | None", self.port_reader) is not None:
            return typing.cast("typing.Callable[[int], int]", self.port_reader)(port) & 0xFF
        return 0xFF  # documented: unconnected port reads as all-ones

    def _write_port(self, port: int, value: int) -> None:
        import typing

        writer = typing.cast("typing.Callable[[int, int], None] | None", self.port_writer)
        if writer is not None:
            writer(port, value & 0xFF)
        # writes to unconnected ports are recorded in the trace and ignored

    def reset(self) -> None:
        self.registers = Registers()
        self.registers.set("SP", POWER_ON_SP)
        self.halted = False
        self._steps_taken = 0
        self.interrupts.depth = 0
        self.interrupts.pending_intr.clear()

    # ------------------------------------------------------------------ helpers

    def _resolve_read(self, operand: Operand) -> int:
        if operand.kind == "reg":
            return self.registers.get(operand.name)
        if operand.kind == "seg":
            return self.registers.get(operand.name)
        if operand.kind == "imm":
            return operand.value & 0xFFFF
        if operand.kind == "mem":
            segment, offset = self._effective_address(operand)
            if operand.width == 8:
                return self.memory.read_byte(segment, offset)
            return self.memory.read_word(segment, offset)
        raise CpuRuntimeError(self._steps_taken, f"unresolvable operand kind {operand.kind!r}")

    def _resolve_write(self, operand: Operand, value: int) -> tuple[tuple[int, int], ...] | None:
        if operand.kind == "reg":
            self.registers.set(operand.name, value)
            return None
        if operand.kind == "seg":
            self.registers.set(operand.name, value)
            return None
        if operand.kind == "mem":
            segment, offset = self._effective_address(operand)
            if operand.width == 8:
                self.memory.write_byte(segment, offset, value)
                return ((physical(segment, offset), value & 0xFF),)
            self.memory.write_word(segment, offset, value)
            return (
                (physical(segment, offset), value & 0xFF),
                (physical(segment, offset + 1), (value >> 8) & 0xFF),
            )
        raise CpuRuntimeError(self._steps_taken, f"unwritable operand kind {operand.kind!r}")

    def _effective_address(self, operand: Operand) -> tuple[int, int]:
        segment_name = operand.default_segment
        base = self.registers.get(segment_name)
        offset = operand.mem_disp
        for term in operand.mem_terms:
            offset += self.registers.get(term)
        return base & 0xFFFF, offset & 0xFFFF

    def _read_dest(self, operand: Operand, width: int) -> int:
        value = self._resolve_read(operand)
        return value & ((1 << width) - 1)

    def _stack_push_word(self, value: int) -> tuple[tuple[int, int], tuple[int, int]]:
        sp = (self.registers.get("SP") - 2) & 0xFFFF
        self.registers.set("SP", sp)
        self.memory.write_word(self.registers.get("SS"), sp, value)
        seg = self.registers.get("SS")
        return (
            (physical(seg, sp), value & 0xFF),
            (physical(seg, sp + 1), (value >> 8) & 0xFF),
        )

    def _stack_pop_word(self) -> int:
        sp = self.registers.get("SP")
        value = self.memory.read_word(self.registers.get("SS"), sp)
        self.registers.set("SP", (sp + 2) & 0xFFFF)
        return value

    # ------------------------------------------------------------- interrupt fire

    def _fire_interrupt(self, number: int, source: str) -> TraceRecord:
        handler = self.interrupts.fire_software(number)
        before = self.registers.snapshot()
        before_flags = dict(self.registers.flags)
        memory_changes: list[tuple[int, int]] = []
        flags_word = sum(
            (self.registers.flags[name] << position)
            for position, name in enumerate(("CF", "PF", "AF", "ZF", "SF", "OF", "IF", "DF"))
        )
        memory_changes.extend(self._stack_push_word(flags_word))
        memory_changes.extend(self._stack_push_word(self.registers.get("IP")))
        self.registers.set_flags({"IF": 0})
        self.registers.set("IP", handler)
        after = self.registers.snapshot()
        register_changes = {k: v for k, v in after.items() if before[k] != v}
        flag_changes = {k: v for k, v in self.registers.flags.items() if before_flags[k] != v}
        return TraceRecord(
            kind="interrupt",
            step=self._steps_taken,
            ip=self.registers.get("IP"),
            register_changes=register_changes,
            flag_changes=flag_changes,
            memory_changes=tuple(memory_changes),
            number=number,
            source=source,
            handler=handler,
        )

    def _fire_iret(self) -> TraceRecord:
        if self.interrupts.depth <= 0:
            raise CpuRuntimeError(self._steps_taken, "IRET without a matching interrupt frame")
        before = self.registers.snapshot()
        before_flags = dict(self.registers.flags)
        return_ip = self._stack_pop_word()
        flags_word = self._stack_pop_word()
        for position, name in enumerate(("CF", "PF", "AF", "ZF", "SF", "OF", "IF", "DF")):
            self.registers.flags[name] = (flags_word >> position) & 1
        self.registers.set("IP", return_ip)
        self.interrupts.retire()
        after = self.registers.snapshot()
        register_changes = {k: v for k, v in after.items() if before[k] != v}
        flag_changes = {k: v for k, v in self.registers.flags.items() if before_flags[k] != v}
        resumed_at = self.registers.get("IP")
        return TraceRecord(
            kind="iret",
            step=self._steps_taken,
            ip=resumed_at,
            register_changes=register_changes,
            flag_changes=flag_changes,
            resumed_at=resumed_at,
        )

    # -------------------------------------------------------------------- step

    def step(self) -> TraceRecord:
        if self.halted:
            raise CpuRuntimeError(self._steps_taken, "CPU is halted")
        if self.program is None:
            raise CpuRuntimeError(self._steps_taken, "no program loaded")

        # Scheduled external interrupts fire at this boundary (before fetch).
        scheduled = self.interrupts.due_now(self._steps_taken)
        if scheduled is not None:
            if scheduled.source == "nmi":
                self._steps_taken += 1
                return self._fire_interrupt(scheduled.number, "nmi")
            if self.registers.flags["IF"] == 1:
                self._steps_taken += 1
                return self._fire_interrupt(scheduled.number, "intr")
            self.interrupts.park_pending(scheduled.number)
            self._steps_taken += 1
            return TraceRecord(
                kind="pending_intr",
                step=self._steps_taken,
                ip=self.registers.get("IP"),
                number=scheduled.number,
            )
        if self.registers.flags["IF"] == 1:
            pending = self.interrupts.take_pending()
            if pending is not None:
                self._steps_taken += 1
                return self._fire_interrupt(pending, "intr")

        ip = self.registers.get("IP")
        instructions = self.program.instructions
        if not 0 <= ip < len(instructions):
            raise CpuRuntimeError(self._steps_taken, f"IP {ip} outside program (0..{len(instructions) - 1})")
        instruction = instructions[ip]
        before = self.registers.snapshot()
        before_flags = dict(self.registers.flags)
        memory_changes: list[tuple[int, int]] = []
        halted = False

        self.registers.set("IP", ip + 1)
        mnemonic = instruction.mnemonic

        if mnemonic == "MOV":
            assert instruction.src is not None and instruction.dest is not None
            width = _operand_width_bits(instruction.dest)
            value = self._resolve_read(instruction.src) & ((1 << width) - 1)
            memory_changes.extend(self._resolve_write(instruction.dest, value) or [])
        elif mnemonic in _ARITHMETIC:
            memory_changes.extend(self._execute_arithmetic(instruction))
        elif mnemonic in _MULTIPLY_DIVIDE:
            memory_changes.extend(self._execute_mul_div(instruction))
        elif mnemonic in _STRING_OPS:
            memory_changes.extend(self._execute_string(instruction))
        elif mnemonic == "PUSH":
            assert instruction.dest is not None
            value = self._resolve_read(instruction.dest) & 0xFFFF
            memory_changes.extend(self._stack_push_word(value))
        elif mnemonic == "POP":
            assert instruction.dest is not None
            value = self._stack_pop_word()
            memory_changes.extend(self._resolve_write(instruction.dest, value) or [])
        elif mnemonic == "JMP":
            assert instruction.dest is not None
            self.registers.set("IP", instruction.dest.value)
        elif mnemonic == "LOOP":
            assert instruction.dest is not None
            cx = (self.registers.get("CX") - 1) & 0xFFFF
            self.registers.set("CX", cx)
            if cx != 0:
                self.registers.set("IP", instruction.dest.value)
        elif mnemonic == "CALL":
            assert instruction.dest is not None
            return_ip = self.registers.get("IP")
            memory_changes.extend(self._stack_push_word(return_ip))
            self.registers.set("IP", instruction.dest.value)
        elif mnemonic in _JUMP_MNEMONICS:
            self._execute_conditional_jump(instruction)
        elif mnemonic == "LOOP":
            assert instruction.dest is not None
            cx = (self.registers.get("CX") - 1) & 0xFFFF
            self.registers.set("CX", cx)
            if cx != 0:
                self.registers.set("IP", instruction.dest.value)
        elif mnemonic == "CALL":
            assert instruction.dest is not None
            return_ip = self.registers.get("IP")
            memory_changes.extend(self._stack_push_word(return_ip))
            self.registers.set("IP", instruction.dest.value)
        elif mnemonic == "RET":
            self.registers.set("IP", self._stack_pop_word())
        elif mnemonic == "INT":
            assert instruction.dest is not None
            self._steps_taken += 1
            return self._fire_interrupt(instruction.dest.value, "software")
        elif mnemonic == "IRET":
            self._steps_taken += 1
            iret_record = self._fire_iret()
            return iret_record
        elif mnemonic == "XCHG":
            assert instruction.dest is not None and instruction.src is not None
            tmp = self._resolve_read(instruction.dest)
            src_val = self._resolve_read(instruction.src)
            self._resolve_write(instruction.dest, src_val)
            self._resolve_write(instruction.src, tmp)
        elif mnemonic in ("SHL", "SHR", "SAR"):
            assert instruction.dest is not None
            width = _operand_width_bits(instruction.dest)
            mask = (1 << width) - 1
            old = self._read_dest(instruction.dest, width)
            count = self._resolve_read(instruction.src) & 0xFF if instruction.src else 1
            if mnemonic == "SHL":
                result = (old << count) & mask
            elif mnemonic == "SHR":
                result = old >> count
            else:
                sign_bit = 1 << (width - 1)
                sign_fill = mask & ~(mask >> count) if old & sign_bit else 0
                result = (old >> count) | sign_fill
            from cpu8086.registers import logic_flags

            deltas = logic_flags(result, width)
            self.registers.set_flags(deltas)
            memory_changes.extend(self._resolve_write(instruction.dest, result) or [])
        elif mnemonic == "IN":
            assert instruction.src is not None and instruction.dest is not None
            port = instruction.src.value if instruction.src.kind == "imm" else self.registers.get("DX")
            value = self._read_port(port & 0xFFFF)
            self._resolve_write(instruction.dest, value)
        elif mnemonic == "OUT":
            assert instruction.src is not None and instruction.dest is not None
            port = instruction.dest.value if instruction.dest.kind == "imm" else self.registers.get("DX")
            value = self._resolve_read(instruction.src) & 0xFF
            self._write_port(port & 0xFFFF, value)
        elif mnemonic == "STI":
            self.registers.set_flags({"IF": 1})
        elif mnemonic == "CLI":
            self.registers.set_flags({"IF": 0})
        elif mnemonic == "STD":
            self.registers.set_flags({"DF": 1})
        elif mnemonic == "CLD":
            self.registers.set_flags({"DF": 0})
        elif mnemonic == "NOP":
            pass
        elif mnemonic == "HLT":
            halted = True
            self.halted = True
        else:
            raise UnsupportedInstructionError(mnemonic, instruction.line)

        self._steps_taken += 1
        after = self.registers.snapshot()
        register_changes = {k: v for k, v in after.items() if before[k] != v}
        flag_changes = {k: v for k, v in self.registers.flags.items() if before_flags[k] != v}
        return TraceRecord(
            kind="instruction",
            step=self._steps_taken,
            ip=ip,
            instruction=instruction.text,
            register_changes=register_changes,
            flag_changes=flag_changes,
            memory_changes=tuple(memory_changes),
            halted=halted,
        )

    def _execute_arithmetic(self, instruction: Instruction) -> list[tuple[int, int]]:
        mnemonic = instruction.mnemonic
        assert instruction.dest is not None
        width = _operand_width_bits(instruction.dest)
        mask = (1 << width) - 1
        old = self._read_dest(instruction.dest, width)
        source_value = 1 if instruction.src is None else self._resolve_read(instruction.src) & mask
        memory_changes: list[tuple[int, int]] = []

        if mnemonic == "ADD":
            deltas = add_flags(old, source_value, 0, width)
            result = (old + source_value) & mask
        elif mnemonic == "ADC":
            deltas = add_flags(old, source_value, self.registers.flags["CF"], width)
            result = (old + source_value + self.registers.flags["CF"]) & mask
        elif mnemonic == "SUB" or mnemonic == "CMP":
            deltas = sub_flags(old, source_value, 0, width)
            result = (old - source_value) & mask
            self.registers.set_flags(deltas)
            if mnemonic == "CMP":
                return memory_changes  # flags only; dest unchanged
        elif mnemonic == "SBB":
            deltas = sub_flags(old, source_value, self.registers.flags["CF"], width)
            result = (old - source_value - self.registers.flags["CF"]) & mask
        elif mnemonic == "AND":
            result = old & source_value
            deltas = logic_flags(result, width)
        elif mnemonic == "OR":
            result = old | source_value
            deltas = logic_flags(result, width)
        elif mnemonic == "XOR":
            result = old ^ source_value
            deltas = logic_flags(result, width)
        elif mnemonic == "TEST":
            result = old & source_value
            deltas = logic_flags(result, width)
            self.registers.set_flags(deltas)
            return memory_changes  # flags only; dest unchanged
        elif mnemonic == "INC":
            result = (old + 1) & mask
            deltas = inc_dec_flags(old, result, width, increment=True)
        elif mnemonic == "DEC":
            result = (old - 1) & mask
            deltas = inc_dec_flags(old, result, width, increment=False)
        elif mnemonic == "NEG":
            result = (-old) & mask
            deltas = neg_flags(old, width)
        else:
            raise UnsupportedInstructionError(mnemonic, instruction.line)

        memory_changes.extend(self._resolve_write(instruction.dest, result) or [])
        self.registers.set_flags(deltas)
        return memory_changes

    def _execute_mul_div(self, instruction: Instruction) -> list[tuple[int, int]]:
        """MUL/IMUL/DIV/IDIV — one explicit operand, implicit accumulator (cpu8086.md)."""
        mnemonic = instruction.mnemonic
        assert instruction.dest is not None
        width = _operand_width_bits(instruction.dest)
        operand = self._resolve_read(instruction.dest) & ((1 << width) - 1)

        if mnemonic == "MUL":
            if width == 8:
                full = self.registers.get("AL") * operand
                self.registers.set("AX", full & 0xFFFF)
                self.registers.set_flags(mul_flags(full & 0xFF, (full >> 8) != 0, 8))
            else:
                full = self.registers.get("AX") * operand
                self.registers.set("AX", full & 0xFFFF)
                self.registers.set("DX", (full >> 16) & 0xFFFF)
                self.registers.set_flags(mul_flags(full & 0xFFFF, (full >> 16) != 0, 16))
            return []

        if mnemonic == "IMUL":
            if width == 8:
                full = _to_signed(self.registers.get("AL"), 8) * _to_signed(operand, 8)
                self.registers.set("AX", full & 0xFFFF)
                self.registers.set_flags(mul_flags(full & 0xFF, not -128 <= full <= 127, 8))
            else:
                full = _to_signed(self.registers.get("AX"), 16) * _to_signed(operand, 16)
                self.registers.set("AX", full & 0xFFFF)
                self.registers.set("DX", (full >> 16) & 0xFFFF)
                self.registers.set_flags(mul_flags(full & 0xFFFF, not -32768 <= full <= 32767, 16))
            return []

        # DIV / IDIV — all flags unchanged (cpu8086.md).
        if width == 8:
            dividend = self.registers.get("AX")
            if operand == 0:
                raise CpuRuntimeError(self._steps_taken, "integer divide by zero")
            if mnemonic == "DIV":
                quotient, remainder = dividend // operand, dividend % operand
                if quotient > 0xFF:
                    raise CpuRuntimeError(self._steps_taken, f"divide overflow: quotient {quotient} does not fit AL")
                self.registers.set("AL", quotient)
                self.registers.set("AH", remainder)
            else:
                divisor = _to_signed(operand, 8)
                signed_dividend = _to_signed(dividend, 16)
                quotient = _trunc_div(signed_dividend, divisor)
                remainder = signed_dividend - quotient * divisor
                if not -128 <= quotient <= 127:
                    raise CpuRuntimeError(
                        self._steps_taken, f"divide overflow: quotient {quotient} does not fit AL signed"
                    )
                self.registers.set("AL", quotient & 0xFF)
                self.registers.set("AH", remainder & 0xFF)
            return []

        dividend = (self.registers.get("DX") << 16) | self.registers.get("AX")
        if operand == 0:
            raise CpuRuntimeError(self._steps_taken, "integer divide by zero")
        if mnemonic == "DIV":
            quotient, remainder = dividend // operand, dividend % operand
            if quotient > 0xFFFF:
                raise CpuRuntimeError(self._steps_taken, f"divide overflow: quotient {quotient} does not fit AX")
            self.registers.set("AX", quotient)
            self.registers.set("DX", remainder)
        else:
            divisor = _to_signed(operand, 16)
            signed_dividend = _to_signed(dividend, 32)
            quotient = _trunc_div(signed_dividend, divisor)
            remainder = signed_dividend - quotient * divisor
            if not -32768 <= quotient <= 32767:
                raise CpuRuntimeError(self._steps_taken, f"divide overflow: quotient {quotient} does not fit AX signed")
            self.registers.set("AX", quotient & 0xFFFF)
            self.registers.set("DX", remainder & 0xFFFF)
        return []

    def _execute_string(self, instruction: Instruction) -> list[tuple[int, int]]:
        """String ops with implicit DS:SI / ES:DI operands and optional REP family (cpu8086.md).

        A REP-prefixed op is ONE step that executes the whole repeat: while CX != 0
        the operation runs and CX decrements; REPE/REPNE stop early on the ZF test
        performed after each iteration. The trace records the net SI/DI/CX changes
        and every net memory write of the repeat.
        """
        mnemonic = instruction.mnemonic
        width = 8 if mnemonic.endswith("B") else 16
        size = 1 if width == 8 else 2
        delta = -size if self.registers.flags["DF"] == 1 else size
        mask = (1 << width) - 1
        memory_changes: list[tuple[int, int]] = []

        def read_source(offset: int) -> int:
            segment = self.registers.get("DS")
            if width == 8:
                return self.memory.read_byte(segment, offset & 0xFFFF)
            return self.memory.read_word(segment, offset & 0xFFFF)

        def read_dest(offset: int) -> int:
            segment = self.registers.get("ES")
            if width == 8:
                return self.memory.read_byte(segment, offset & 0xFFFF)
            return self.memory.read_word(segment, offset & 0xFFFF)

        def write_dest(offset: int, value: int) -> None:
            segment = self.registers.get("ES")
            if width == 8:
                self.memory.write_byte(segment, offset & 0xFFFF, value)
                memory_changes.append((physical(segment, offset & 0xFFFF), value & 0xFF))
            else:
                self.memory.write_word(segment, offset & 0xFFFF, value)
                memory_changes.append((physical(segment, offset & 0xFFFF), value & 0xFF))
                memory_changes.append((physical(segment, (offset & 0xFFFF) + 1), (value >> 8) & 0xFF))

        def once() -> None:
            si = self.registers.get("SI")
            di = self.registers.get("DI")
            if mnemonic == "MOVSB" or mnemonic == "MOVSW":
                write_dest(di, read_source(si))
                self.registers.set("SI", (si + delta) & 0xFFFF)
                self.registers.set("DI", (di + delta) & 0xFFFF)
            elif mnemonic == "STOSB" or mnemonic == "STOSW":
                write_dest(di, self.registers.get("AL" if width == 8 else "AX") & mask)
                self.registers.set("DI", (di + delta) & 0xFFFF)
            elif mnemonic == "LODSB" or mnemonic == "LODSW":
                self.registers.set("AL" if width == 8 else "AX", read_source(si) & mask)
                self.registers.set("SI", (si + delta) & 0xFFFF)
            elif mnemonic == "SCASB" or mnemonic == "SCASW":
                deltas = sub_flags(
                    self.registers.get("AL" if width == 8 else "AX") & mask, read_dest(di) & mask, 0, width
                )
                self.registers.set_flags(deltas)
                self.registers.set("DI", (di + delta) & 0xFFFF)
            else:  # CMPSB / CMPSW: [DS:SI] - [ES:DI]
                deltas = sub_flags(read_source(si) & mask, read_dest(di) & mask, 0, width)
                self.registers.set_flags(deltas)
                self.registers.set("SI", (si + delta) & 0xFFFF)
                self.registers.set("DI", (di + delta) & 0xFFFF)

        if instruction.rep == "":
            once()
            return memory_changes

        count = self.registers.get("CX")
        while count > 0:
            once()
            count = (count - 1) & 0xFFFF
            if instruction.rep == "REPE" and self.registers.flags["ZF"] == 0:
                break
            if instruction.rep == "REPNE" and self.registers.flags["ZF"] == 1:
                break
        self.registers.set("CX", count)
        return memory_changes

    def _execute_conditional_jump(self, instruction: Instruction) -> None:
        flags = self.registers.flags
        mnemonic = instruction.mnemonic
        take = {
            "JZ": flags["ZF"] == 1,
            "JE": flags["ZF"] == 1,
            "JNZ": flags["ZF"] == 0,
            "JNE": flags["ZF"] == 0,
            "JC": flags["CF"] == 1,
            "JB": flags["CF"] == 1,
            "JNC": flags["CF"] == 0,
            "JAE": flags["CF"] == 0,
            "JS": flags["SF"] == 1,
            "JNS": flags["SF"] == 0,
            "JO": flags["OF"] == 1,
            "JNO": flags["OF"] == 0,
            "JCXZ": self.registers.get("CX") == 0,
        }[mnemonic]
        if take and instruction.dest is not None:
            self.registers.set("IP", instruction.dest.value)

    # -------------------------------------------------------------- run control

    def run(
        self,
        max_steps: int = 10_000,
        breakpoints: Sequence[int] = (),
    ) -> tuple[tuple[TraceRecord, ...], str]:
        if not 1 <= max_steps <= MAX_RUN_STEPS:
            raise CpuRuntimeError(self._steps_taken, f"max_steps must be in [1, {MAX_RUN_STEPS}]")
        records: list[TraceRecord] = []
        for _ in range(max_steps):
            next_ip = self.registers.get("IP")
            if next_ip in breakpoints and self._steps_taken > 0:
                self._last_run = tuple(records)
                return self._last_run, "breakpoint"
            if self.halted:
                self._last_run = tuple(records)
                return self._last_run, "hlt"
            records.append(self.step())
            if records[-1].halted:
                self._last_run = tuple(records)
                return self._last_run, "hlt"
        self._last_run = tuple(records)
        return self._last_run, "max_steps"

    def _trace_history(self) -> tuple[TraceRecord, ...]:
        """Test-only accessor for the last run's full trace."""
        return self._last_run


def _operand_width_bits(operand: Operand) -> int:
    width = operand.width
    if width == 0 and operand.kind == "reg":
        return 8 if operand.name in BYTE_HALVES else 16
    return width if width in (8, 16) else 16


def _to_signed(value: int, width: int) -> int:
    """Interpret the low `width` bits of `value` as a two's-complement signed integer."""
    value &= (1 << width) - 1
    sign = 1 << (width - 1)
    return value - (1 << width) if value & sign else value


def _trunc_div(dividend: int, divisor: int) -> int:
    """x86 IDIV truncates toward zero (Python's // floors)."""
    quotient = abs(dividend) // abs(divisor)
    return -quotient if (dividend < 0) != (divisor < 0) else quotient


def assemble_and_load(
    source: str,
    interrupts: Mapping[int, str] | None = None,
    schedule: Sequence[ScheduledInterrupt] = (),
) -> Cpu:
    """Assemble source and return a machine with an optional IVT + schedule."""
    program = assemble(source)
    ivt: dict[int, int] = {}
    for number, label in (interrupts or {}).items():
        if not isinstance(number, int) or isinstance(number, bool) or not 0 <= number <= 255:
            raise AsmError(0, "SYNTAX", f"IVT numbers must be in [0, 255], got {number!r}")
        if not isinstance(label, str):
            raise AsmError(0, "SYNTAX", f"IVT labels must be strings, got {label!r}")
        label_key = label.upper()
        if label_key not in program.labels:
            raise AsmError(0, "UNKNOWN_LABEL", f"IVT label {label!r} is not defined")
        ivt[number] = program.labels[label_key]
    controller = InterruptController(
        ivt=ivt,
        scheduled=tuple(schedule) if schedule else (),
    )
    machine = Cpu(program=program, interrupts=controller)
    machine.registers.set("SP", POWER_ON_SP)
    return machine
