"""Deterministic instruction executor with debugger semantics (cpu8086.md).

`step()` executes one instruction and emits a trace record; `run()` steps until
HLT, a breakpoint, the step cap (bounded, reported), or a typed error. IP is the
instruction index into the assembled IR (documented scope decision).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from cpu8086.assembler import AssembledProgram, Instruction, Operand
from cpu8086.errors import CpuRuntimeError, UnsupportedInstructionError
from cpu8086.memory import Memory, physical
from cpu8086.registers import (
    BYTE_HALVES,
    Registers,
    add_flags,
    inc_dec_flags,
    logic_flags,
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


@dataclass(frozen=True)
class TraceRecord:
    step: int
    ip: int
    instruction: str
    register_changes: dict[str, int]
    flag_changes: dict[str, int]
    memory_changes: tuple[tuple[int, int], ...]
    halted: bool


@dataclass
class MachineState:
    registers: Registers = field(default_factory=Registers)
    memory: Memory = field(default_factory=Memory)
    program: AssembledProgram | None = None
    halted: bool = False


class Cpu:
    """Deterministic IR-level 8086 machine with debugger controls."""

    def __init__(self, program: AssembledProgram) -> None:
        self.program = program
        self.registers = Registers()
        self.memory = Memory()
        self.halted = False
        self._steps_taken = 0

    def reset(self) -> None:
        """Power-on state: registers zeroed, SP = 0xFFFE, IP = 0, memory as loaded."""
        self.registers = Registers()
        self.registers.set("SP", POWER_ON_SP)
        self.halted = False
        self._steps_taken = 0

    def _resolve_read(self, operand: Operand) -> int:
        if operand.kind == "reg":
            return self.registers.get(operand.name)
        if operand.kind == "seg":
            return self.registers.get(operand.name)
        if operand.kind == "imm":
            return operand.value & 0xFFFF
        if operand.kind == "mem":
            segment, offset = self._effective_address(operand)
            return (
                self.memory.read_byte(segment, offset)
                if operand.width == 8
                else self.memory.read_word(segment, offset)
            )
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

    def step(self) -> TraceRecord:
        """Execute exactly one instruction; returns the trace record."""
        if self.halted:
            raise CpuRuntimeError(self._steps_taken, "CPU is halted")
        if self.program is None:
            raise CpuRuntimeError(self._steps_taken, "no program loaded")
        ip = self.registers.get("IP")
        instructions = self.program.instructions
        if not 0 <= ip < len(instructions):
            raise CpuRuntimeError(
                self._steps_taken, f"IP {ip} outside program (0..{len(instructions) - 1})"
            )
        instruction = instructions[ip]
        before = self.registers.snapshot()
        before_flags = dict(self.registers.flags)
        memory_changes: list[tuple[int, int]] = []

        self.registers.set("IP", ip + 1)  # default advance; jumps overwrite
        halted = False

        mnemonic = instruction.mnemonic
        if mnemonic == "MOV":
            assert instruction.src is not None and instruction.dest is not None
            value = self._resolve_read(instruction.src)
            width = _operand_width_bits(instruction.dest)
            memory_changes_result = self._resolve_write(
                instruction.dest, value & ((1 << width) - 1)
            )
            if memory_changes_result:
                memory_changes.extend(memory_changes_result)
        elif mnemonic in _ARITHMETIC:
            arithmetic_changes, halted = self._execute_arithmetic(instruction)
            memory_changes.extend(arithmetic_changes)
        elif mnemonic == "PUSH":
            assert instruction.dest is not None
            value = self._resolve_read(instruction.dest) & 0xFFFF
            sp = (self.registers.get("SP") - 2) & 0xFFFF
            self.registers.set("SP", sp)
            self.memory.write_word(self.registers.get("SS"), sp, value)
            memory_changes.extend(
                [
                    (physical(self.registers.get("SS"), sp), value & 0xFF),
                    (physical(self.registers.get("SS"), sp + 1), (value >> 8) & 0xFF),
                ]
            )
        elif mnemonic == "POP":
            assert instruction.dest is not None
            sp = self.registers.get("SP")
            value = self.memory.read_word(self.registers.get("SS"), sp)
            self.registers.set("SP", (sp + 2) & 0xFFFF)
            write_result = self._resolve_write(instruction.dest, value)
            if write_result:
                memory_changes.extend(write_result)
        elif mnemonic == "JMP":
            assert instruction.dest is not None
            self.registers.set("IP", instruction.dest.value)
        elif mnemonic in (
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
        ):
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
            sp = (self.registers.get("SP") - 2) & 0xFFFF
            self.registers.set("SP", sp)
            self.memory.write_word(self.registers.get("SS"), sp, return_ip)
            memory_changes.extend(
                [
                    (physical(self.registers.get("SS"), sp), return_ip & 0xFF),
                    (
                        physical(self.registers.get("SS"), sp + 1),
                        (return_ip >> 8) & 0xFF,
                    ),
                ]
            )
            self.registers.set("IP", instruction.dest.value)
        elif mnemonic == "RET":
            sp = self.registers.get("SP")
            return_ip = self.memory.read_word(self.registers.get("SS"), sp)
            self.registers.set("SP", (sp + 2) & 0xFFFF)
            self.registers.set("IP", return_ip)
        elif mnemonic == "NOP":
            pass
        elif mnemonic == "HLT":
            halted = True
            self.halted = True
        else:
            raise UnsupportedInstructionError(mnemonic, instruction.line)

        self._steps_taken += 1
        after = self.registers.snapshot()
        register_changes = {name: value for name, value in after.items() if before[name] != value}
        flag_changes = {
            name: value
            for name, value in self.registers.flags.items()
            if before_flags[name] != value
        }
        return TraceRecord(
            step=self._steps_taken,
            ip=ip,
            instruction=instruction.text,
            register_changes=register_changes,
            flag_changes=flag_changes,
            memory_changes=tuple(memory_changes),
            halted=halted,
        )

    def _execute_arithmetic(self, instruction: Instruction) -> tuple[list[tuple[int, int]], bool]:
        mnemonic = instruction.mnemonic
        assert instruction.dest is not None
        width = _operand_width_bits(instruction.dest)
        mask = (1 << width) - 1
        old = self._read_dest(instruction.dest, width)
        # INC/DEC have an implicit +1/-1; all other ops read their source operand
        source_value = 1 if instruction.src is None else self._resolve_read(instruction.src) & mask
        memory_changes: list[tuple[int, int]] = []
        halted = False

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
                return memory_changes, halted  # flags only; dest unchanged
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
            return memory_changes, halted  # flags only; dest unchanged
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

        write_result = self._resolve_write(instruction.dest, result)
        if write_result:
            memory_changes.extend(write_result)
        self.registers.set_flags(deltas)
        return memory_changes, halted

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

    def run(
        self,
        max_steps: int = 10_000,
        breakpoints: Sequence[int] = (),
    ) -> tuple[tuple[TraceRecord, ...], str]:
        """Step until HLT, a breakpoint, the cap, or an error.

        Returns (trace records, stop reason) where reason is
        "hlt" | "breakpoint" | "max_steps". Errors propagate as typed exceptions.
        """
        if not 1 <= max_steps <= MAX_RUN_STEPS:
            raise CpuRuntimeError(self._steps_taken, f"max_steps must be in [1, {MAX_RUN_STEPS}]")
        records: list[TraceRecord] = []
        for _ in range(max_steps):
            next_ip = self.registers.get("IP")
            if next_ip in breakpoints and self._steps_taken > 0:
                return tuple(records), "breakpoint"
            if self.halted:
                return tuple(records), "hlt"
            records.append(self.step())
            if records[-1].halted:
                return tuple(records), "hlt"
        return tuple(records), "max_steps"


def _operand_width_bits(operand: Operand) -> int:
    width = operand.width
    if width == 0 and operand.kind == "reg":
        return 8 if operand.name in BYTE_HALVES else 16
    return width if width in (8, 16) else 16


def assemble_and_load(source: str) -> Cpu:
    """Assemble source text and return a loaded machine (IP=0, power-on state)."""
    from cpu8086.assembler import assemble

    program = assemble(source)
    machine = Cpu(program)
    machine.registers.set("SP", POWER_ON_SP)
    return machine
