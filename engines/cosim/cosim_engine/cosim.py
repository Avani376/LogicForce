"""LogicForge co-simulation engine (v0.8.0).

Shared event scheduler linking a combinational circuit and an 8086 program
through I/O ports. Deterministic 4-step cycle per cosim.md: apply port writes →
settle circuit → execute one instruction → record.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from cpu8086 import CpuRuntimeError
from cpu8086.machine import assemble_and_load
from logic_engine import SchemaError
from logic_engine.graph import parse_circuit as parse_circuit_v1
from logic_engine.hashing import canonical_json
from logic_engine.simulator import simulate as v1_simulate
from logic_engine.validation import require_valid as v1_require_valid
from logic_engine.values import LogicValue, normalize_value

COSIM_ENGINE_VERSION = "0.8.0"
COSIM_SCHEMA_VERSION = 1
MAX_CYCLES = 4096


@dataclass(frozen=True)
class PortMapping:
    port: int
    signal: str
    direction: str  # "input" | "output"


@dataclass
class CoSimCycle:
    cycle: int
    kind: str  # "instruction" | "halt"
    cpu_ip: int
    instruction: str
    port_writes: tuple[dict[str, object], ...]
    port_reads: tuple[dict[str, object], ...]
    circuit_outputs: dict[str, str]


@dataclass
class CoSimReport:
    engine_version: str
    input_hash: str
    cycles: tuple[CoSimCycle, ...]
    executed: int
    port_writes_total: int
    final_registers: dict[str, int]
    final_circuit_outputs: dict[str, str]
    verdict: str
    scope: str
    assumptions: tuple[str, ...]
    reason: str | None


def parse_cosim_document(raw: object) -> dict[str, object]:
    """Validate a co-simulation document (schema 1); returns a normalized copy."""
    if not isinstance(raw, Mapping):
        raise SchemaError("COSIM_SCHEMA_ERROR", "co-sim document must be a JSON object")
    version = raw.get("cosim_schema_version")
    if version != COSIM_SCHEMA_VERSION:
        raise SchemaError(
            "COSIM_SCHEMA_ERROR",
            f"expected cosim_schema_version {COSIM_SCHEMA_VERSION}, got {version!r}",
        )
    circuit = raw.get("circuit")
    program = raw.get("program")
    ports = raw.get("ports")
    cycles = raw.get("cycles")
    if not isinstance(circuit, Mapping) or circuit.get("schema_version") != 1:
        raise SchemaError("COSIM_SCHEMA_ERROR", "'circuit' must be a schema-v1 circuit document")
    if not isinstance(program, str) or not program.strip():
        raise SchemaError("COSIM_SCHEMA_ERROR", "'program' must be a non-empty string")
    if not isinstance(ports, list):
        raise SchemaError("COSIM_SCHEMA_ERROR", "'ports' must be an array")
    seen_ports: set[int] = set()
    seen_signals: set[str] = set()
    for entry in ports:
        if not isinstance(entry, Mapping):
            raise SchemaError("COSIM_SCHEMA_ERROR", "each port mapping must be an object")
        port = entry.get("port")
        signal = entry.get("signal")
        direction = entry.get("direction")
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 0xFFFF:
            raise SchemaError("COSIM_SCHEMA_ERROR", f"port must be in [0, 0xFFFF], got {port!r}")
        if port in seen_ports:
            raise SchemaError("COSIM_SCHEMA_ERROR", f"port {port} mapped more than once")
        seen_ports.add(port)
        if not isinstance(signal, str) or not signal:
            raise SchemaError("COSIM_SCHEMA_ERROR", "'signal' must be a non-empty string")
        if signal in seen_signals:
            raise SchemaError("COSIM_SCHEMA_ERROR", f"signal {signal!r} mapped more than once")
        seen_signals.add(signal)
        if direction not in ("input", "output"):
            raise SchemaError(
                "COSIM_SCHEMA_ERROR",
                f"'direction' must be 'input' or 'output', got {direction!r}",
            )
    if isinstance(cycles, bool) or not isinstance(cycles, int) or not 1 <= cycles <= MAX_CYCLES:
        raise SchemaError(
            "COSIM_SCHEMA_ERROR",
            f"'cycles' must be an integer in [1, {MAX_CYCLES}], got {cycles!r}",
        )
    return {
        "cosim_schema_version": COSIM_SCHEMA_VERSION,
        "name": raw.get("name") if isinstance(raw.get("name"), str) else None,
        "circuit": dict(circuit),
        "program": program,
        "ports": [dict(entry) for entry in ports],
        "cycles": cycles,
    }


def _wiring(
    circuit_doc: Mapping[str, object], port_mappings: Sequence[Mapping[str, object]]
) -> tuple[dict[int, str], dict[int, str], dict[str, LogicValue]]:
    """Validate direction/signal wiring."""
    # returns (port->input signal, port->output signal, initial input vector)
    graph = parse_circuit_v1(dict(circuit_doc))
    v1_require_valid(graph)
    input_names = {
        str(c.params["name"])
        for c in graph.components
        if c.type == "INPUT" and isinstance(c.params.get("name"), str)
    }
    output_names = {
        str(c.params["name"])
        for c in graph.components
        if c.type == "OUTPUT" and isinstance(c.params.get("name"), str)
    }
    port_to_input: dict[int, str] = {}
    port_to_output: dict[int, str] = {}
    for mapping in port_mappings:
        signal = str(mapping["signal"])
        port = cast("int", mapping["port"])
        if mapping["direction"] == "input":
            if signal not in input_names:
                raise SchemaError(
                    "COSIM_SCHEMA_ERROR",
                    f"input port {port} maps signal {signal!r}: not a circuit primary input",
                )
            port_to_input[port] = signal
        else:
            if signal not in output_names:
                raise SchemaError(
                    "COSIM_SCHEMA_ERROR",
                    f"output port {port} maps signal {signal!r}: not a circuit primary output",
                )
            port_to_output[port] = signal
    initial = {name: LogicValue.UNKNOWN for name in input_names}
    return port_to_input, port_to_output, initial


def _settle(
    circuit_doc: Mapping[str, object], input_vector: Mapping[str, LogicValue]
) -> dict[str, str]:
    graph = parse_circuit_v1(dict(circuit_doc))
    return dict(v1_simulate(graph, dict(input_vector)).outputs)


def _assumptions() -> tuple[str, ...]:
    return (
        "OUT writes land at the NEXT cycle's settle (one-cycle port latency)",
        "IN reads sample the circuit as settled in the current cycle",
        "unmapped output ports read 0xFF; unwritten circuit inputs are X",
    )


def _hash(document: Mapping[str, object]) -> str:
    payload = f"cosim1|{canonical_json(dict(document))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_cosim(document: Mapping[str, object]) -> CoSimReport:
    """Execute the documented co-simulation (deterministic, bounded)."""
    normalized = parse_cosim_document(dict(document))
    circuit_doc = cast("dict[str, object]", normalized["circuit"])
    program = str(normalized["program"])
    raw_cycles = normalized["cycles"]
    cycles_budget = cast("int", raw_cycles)
    port_mappings = cast("list[dict[str, object]]", normalized["ports"])

    port_to_input, port_to_output, current_inputs = _wiring(circuit_doc, port_mappings)

    # pending writes: port -> value, applied at the next cycle's settle
    pending_writes: dict[int, int] = {}
    # last written value per INPUT SIGNAL (drives the settle vector)
    # logs captured by the port callbacks during instruction execution
    reads_log: list[dict[str, object]] = []
    writes_log: list[dict[str, object]] = []
    settled_outputs: dict[str, str] = {}

    def read_port(port: int) -> int:
        if port in port_to_output:
            signal = port_to_output[port]
            value = settled_outputs.get(signal, "X")
            reads_log.append({"port": port, "value": value, "signal": signal})
            if value in ("X", "Z"):
                return 0xFF
            return int(value)
        reads_log.append({"port": port, "value": "unmapped"})
        return 0xFF

    def write_port(port: int, value: int) -> None:
        if port in port_to_input:
            signal = port_to_input[port]
            writes_log.append({"port": port, "value": value, "signal": signal})
            pending_writes[port] = value

    machine = assemble_and_load(program)
    machine.port_reader = read_port
    machine.port_writer = write_port

    executed = 0
    trace: list[CoSimCycle] = []
    port_writes_total = 0
    verdict = "BOUNDED"
    reason: str | None = None
    last_outputs: dict[str, str] = {}

    for cycle in range(cycles_budget):
        # 1. apply pending port writes to the circuit input vector
        applied: list[dict[str, object]] = []
        for port, value in sorted(pending_writes.items()):
            signal = port_to_input[port]
            current_inputs[signal] = (
                LogicValue.ONE if (value & 1) else LogicValue.ZERO
            )
            applied.append({"port": port, "value": value, "signal": signal})
            port_writes_total += 1
        pending_writes = {}

        # 2. settle the circuit with the current input vector
        settled_outputs = _settle(circuit_doc, current_inputs)
        last_outputs = dict(settled_outputs)
        reads_log.clear()
        writes_log.clear()

        # 3. execute one CPU instruction (IN reads step-2 settle; OUT stages for k+1)
        cpu_ip = machine.registers.get("IP")
        instruction_text = ""
        halted = False
        try:
            if machine.halted:
                verdict = "HALTED"
                reason = "CPU executed HLT"
                break
            record = machine.step()
            executed += 1
            cpu_ip = record.ip
            instruction_text = record.instruction
            halted = record.halted
        except CpuRuntimeError as exc:
            trace.append(
                CoSimCycle(
                    cycle=cycle,
                    kind="error",
                    cpu_ip=cpu_ip,
                    instruction=instruction_text,
                    port_writes=tuple(applied),
                    port_reads=(),
                    circuit_outputs=dict(last_outputs),
                )
            )
            return CoSimReport(
                engine_version=COSIM_ENGINE_VERSION,
                input_hash=_hash(document),
                cycles=tuple(trace),
                executed=executed,
                port_writes_total=port_writes_total,
                final_registers=machine.registers.snapshot(),
                final_circuit_outputs=dict(last_outputs),
                verdict="INCOMPLETE",
                scope=f"BOUNDED({cycle} cycles executed)",
                assumptions=_assumptions(),
                reason=f"CPU error: {exc}",
            )

        # 4. record
        kind = "halt" if halted else "instruction"
        trace.append(
            CoSimCycle(
                cycle=cycle,
                kind=kind,
                cpu_ip=cpu_ip,
                instruction=instruction_text,
                port_writes=tuple(applied),
                port_reads=tuple(reads_log),
                circuit_outputs=dict(last_outputs),
            )
        )
        if halted:
            verdict = "HALTED"
            reason = "CPU executed HLT"
            break

    return CoSimReport(
        engine_version=COSIM_ENGINE_VERSION,
        input_hash=_hash(document),
        cycles=tuple(trace),
        executed=executed,
        port_writes_total=port_writes_total,
        final_registers=machine.registers.snapshot(),
        final_circuit_outputs=dict(last_outputs),
        verdict=verdict,
        scope=f"BOUNDED({cycles_budget} cycles)",
        assumptions=_assumptions(),
        reason=reason,
    )


def cosim_report_to_dict(report: CoSimReport) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "schema_version": COSIM_SCHEMA_VERSION,
        "engine_version": report.engine_version,
        "input_hash": report.input_hash,
        "executed": report.executed,
        "port_writes_total": report.port_writes_total,
        "trace": [
            {
                "cycle": c.cycle,
                "kind": c.kind,
                "cpu_ip": c.cpu_ip,
                "instruction": c.instruction,
                "port_writes": [dict(w) for w in c.port_writes],
                "port_reads": [dict(r) for r in c.port_reads],
                "circuit_outputs": dict(c.circuit_outputs),
            }
            for c in report.cycles
        ],
        "final_registers": report.final_registers,
        "final_circuit_outputs": report.final_circuit_outputs,
        "verdict": report.verdict,
        "scope": report.scope,
        "assumptions": list(report.assumptions),
        "reason": report.reason,
    }
