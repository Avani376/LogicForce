"""Deterministic tick-loop sequential simulation (normative: clock-edge-rules.md).

Architecture: each cycle settles the combinational network by reusing the *v1*
engine wholesale — state outputs become synthetic primary inputs (``SQ:``) and
state capture/async pins become synthetic observation outputs (``SP:``) on a
derived v1 graph. This guarantees the settle stage follows exactly the same
documented propagation rules as Phase 1, with zero duplicated semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from logic_engine.components import TYPE_INPUT, TYPE_OUTPUT, Component
from logic_engine.errors import CircuitNotValidError, InvalidInputValueError, SchemaError
from logic_engine.graph import CircuitGraph, Net, PinRef
from logic_engine.hashing import canonical_json
from logic_engine.simulator import simulate as v1_simulate
from logic_engine.validation import ValidationReport
from logic_engine.values import LogicValue, normalize_value, not_

from sequential_engine.flipflops import (
    async_apply,
    counter_next,
    dff_next,
    jkff_next,
    srff_next,
    tff_next,
)
from sequential_engine.graph import resolve_state_spec
from sequential_engine.validation import validate_sequential
from sequential_engine.version import (
    MAX_CYCLES,
    SEQUENTIAL_ENGINE_VERSION,
)


@dataclass(frozen=True)
class SeqEvent:
    """One state-bit change with its cause (async override or clock edge)."""

    cycle: int
    component: str
    pin: str
    old: str
    new: str
    cause: str


@dataclass(frozen=True)
class CycleRecord:
    """Observation of one clock cycle: state during the cycle and settled outputs."""

    cycle: int
    inputs: dict[str, str]
    state: dict[str, str]
    outputs: dict[str, str]


@dataclass(frozen=True)
class SequentialResult:
    engine_version: str
    scope: str
    input_hash: str
    cycles: tuple[CycleRecord, ...]
    events: tuple[SeqEvent, ...]
    waveforms: dict[str, tuple[str, ...]]
    final_state: dict[str, str]
    state_components: tuple[str, ...]


@dataclass
class _StateSpec:
    id: str
    type: str
    capture_pins: tuple[str, ...]
    async_pins: tuple[str, ...]
    state_bits: tuple[str, ...]
    has_complement: bool

    def signal_key(self, bit: str) -> str:
        """Waveform/state key (``FF1.q`` or ``REG1.q0``)."""
        return f"{self.id}.{bit}"


@dataclass
class _Prepared:
    """Derived settle network plus the synthetic-name cross-references."""

    v1_graph: CircuitGraph
    state_specs: list[_StateSpec]
    primary_input_names: tuple[str, ...]
    q_inputs: dict[str, tuple[str, str]]  # SQ name -> (comp id, state bit)
    qn_inputs: dict[str, str]  # SQ name -> comp id (complement)
    capture_outputs: dict[str, tuple[str, str]]  # SP name -> (comp id, capture pin)
    async_outputs: dict[str, tuple[str, str]]  # SP name -> (comp id, async pin)


def _build_prepared(components: list[Component], nets: list[Net], name: str | None) -> _Prepared:
    """Derive the settle network: state pins become synthetic IO on a v1 graph."""
    state_specs: list[_StateSpec] = []
    for comp in sorted(components, key=lambda c: c.id):
        spec = resolve_state_spec(comp)
        if spec is not None:
            state_specs.append(
                _StateSpec(
                    id=spec.id,
                    type=spec.type,
                    capture_pins=spec.capture_pins,
                    async_pins=spec.async_pins,
                    state_bits=spec.state_bits,
                    has_complement=spec.has_complement,
                )
            )
    state_ids = {spec.id for spec in state_specs}
    state_input_pins: dict[str, frozenset[str]] = {}
    for comp in components:
        spec = resolve_state_spec(comp)
        if spec is None:
            continue
        state_input_pins[comp.id] = frozenset({*spec.capture_pins, *spec.async_pins})

    settle_components: list[Component] = []
    settle_nets: list[Net] = []
    q_inputs: dict[str, tuple[str, str]] = {}
    qn_inputs: dict[str, str] = {}
    capture_outputs: dict[str, tuple[str, str]] = {}
    async_outputs: dict[str, tuple[str, str]] = {}
    sq_ids: dict[str, str] = {}  # synthetic input name -> component id (deduped)

    for comp in components:
        if comp.id in state_ids:
            continue  # state components are replaced by synthetic IO
        settle_components.append(comp)

    for net in nets:
        driver = net.driver
        assert driver is not None  # validated: every net has exactly one driver
        if driver.component in state_ids:
            # State output drives this net -> one synthetic INPUT per state pin,
            # shared across every net that pin drives (deduped by name).
            bit = driver.pin
            if bit == "qn":
                synth_name = f"SQ:{driver.component}:qn"
                qn_inputs[synth_name] = driver.component
            else:
                synth_name = f"SQ:{driver.component}:{bit}"
                q_inputs[synth_name] = (driver.component, bit)
            synth_id = sq_ids.get(synth_name)
            if synth_id is None:
                synth_id = synth_name.replace(":", "::")
                sq_ids[synth_name] = synth_id
                settle_components.append(
                    Component(id=synth_id, type=TYPE_INPUT, params={"name": synth_name})
                )
            new_driver = {"component": synth_id, "pin": "out"}
        else:
            new_driver = {"component": driver.component, "pin": driver.pin}
        sinks: list[PinRef] = []
        for sink in net.sinks:
            if sink.component in state_ids and sink.pin in state_input_pins[sink.component]:
                # State input pins do not exist in the settle network; the net is
                # observed through a synthetic SP output instead of the raw sink.
                sp_name = f"SP:{sink.component}:{sink.pin}"
                sp_id = sp_name.replace(":", "::")
                settle_components.append(
                    Component(id=sp_id, type=TYPE_OUTPUT, params={"name": sp_name})
                )
                sinks.append(PinRef(component=sp_id, pin="in"))
                stspec = next(s for s in state_specs if s.id == sink.component)
                if sink.pin in stspec.capture_pins:
                    capture_outputs[sp_name] = (sink.component, sink.pin)
                else:
                    async_outputs[sp_name] = (sink.component, sink.pin)
            else:
                sinks.append(sink)
        settle_nets.append(Net(id=net.id, driver=_pin_ref_of(new_driver), sinks=tuple(sinks)))

    v1_graph = CircuitGraph(
        schema_version=1, name=name, components=tuple(settle_components), nets=tuple(settle_nets)
    )
    primary_input_names = tuple(
        sorted(
            str(comp.params["name"])
            for comp in components
            if comp.type == TYPE_INPUT and isinstance(comp.params.get("name"), str)
        )
    )
    return _Prepared(
        v1_graph=v1_graph,
        state_specs=state_specs,
        primary_input_names=primary_input_names,
        q_inputs=q_inputs,
        qn_inputs=qn_inputs,
        capture_outputs=capture_outputs,
        async_outputs=async_outputs,
    )


def _pin_ref_of(entry: dict[str, str]) -> PinRef:
    return PinRef(component=entry["component"], pin=entry["pin"])


def _normalize_cycle_inputs(
    raw: Mapping[str, object], names: Sequence[str]
) -> dict[str, LogicValue]:
    normalized: dict[str, LogicValue] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise InvalidInputValueError(str(key), value)
        try:
            normalized[key] = normalize_value(value)
        except ValueError as exc:
            raise InvalidInputValueError(key, value) from exc
    return {name: normalized.get(name, LogicValue.UNKNOWN) for name in names}


def simulate_sequential(
    circuit: Mapping[str, object],
    cycles: int,
    inputs_per_cycle: Sequence[Mapping[str, object]],
) -> SequentialResult:
    """Run ``cycles`` ticks of the documented five-stage loop.

    Raises typed errors: ``SchemaError`` (structural), ``CircuitNotValidError``
    (validation), ``InvalidInputValueError`` (bad input values), ``SchemaError``
    with codes ``CYCLES_LIMIT_EXCEEDED`` / ``INPUT_SEQUENCE_TOO_LONG`` for request
    misuse. Deterministic: same inputs ⇒ byte-identical result.
    """
    if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 1:
        raise SchemaError(
            "INVALID_INPUT_SEQUENCE", f"cycles must be an integer in [1, {MAX_CYCLES}]"
        )
    if cycles > MAX_CYCLES:
        raise SchemaError(
            "CYCLES_LIMIT_EXCEEDED",
            f"{cycles} cycles exceeds the hard bound of {MAX_CYCLES}",
        )
    if len(inputs_per_cycle) > cycles:
        raise SchemaError(
            "INPUT_SEQUENCE_TOO_LONG",
            f"inputs_per_cycle has {len(inputs_per_cycle)} entries for {cycles} cycles",
        )

    components, nets, name = _parse_checked(circuit)
    report: ValidationReport = validate_sequential(components, nets, name)
    if not report.ok:
        raise CircuitNotValidError(report)
    prepared = _build_prepared(components, nets, name)

    state: dict[str, LogicValue] = {}
    for spec in prepared.state_specs:
        for bit in spec.state_bits:
            state[f"{spec.id}:{bit}"] = LogicValue.ZERO

    events: list[SeqEvent] = []
    cycle_rows: list[CycleRecord] = []
    waveform_keys: list[str] = [f"in:{n}" for n in prepared.primary_input_names]
    for spec in prepared.state_specs:
        for bit in spec.state_bits:
            waveform_keys.append(spec.signal_key(bit))
    waveforms: dict[str, list[str]] = {key: [] for key in waveform_keys}
    out_names: list[str] = sorted(
        str(comp.params["name"])
        for comp in components
        if comp.type == TYPE_OUTPUT and isinstance(comp.params.get("name"), str)
    )
    for out_name in out_names:
        waveforms[f"out:{out_name}"] = []

    for cycle in range(cycles):
        raw_vector = dict(inputs_per_cycle[cycle]) if cycle < len(inputs_per_cycle) else {}
        vector = _normalize_cycle_inputs(raw_vector, prepared.primary_input_names)

        settled = _settle(prepared, state, vector)

        # Stage 2: async apply (from settled async pin values).
        overridden: dict[str, LogicValue] = {}
        async_changed = False
        for spec in prepared.state_specs:
            async_values = {pin: settled[f"SP:{spec.id}:{pin}"] for pin in spec.async_pins}
            if len(spec.async_pins) == 2:
                override = async_apply(async_values["pre"], async_values["clr"])
            else:
                override = async_apply(LogicValue.ZERO, async_values["clr"])
            if override is None:
                continue
            for bit in spec.state_bits:
                key = f"{spec.id}:{bit}"
                old = state[key]
                if old != override:
                    events.append(
                        SeqEvent(
                            cycle=cycle,
                            component=spec.id,
                            pin=bit,
                            old=old.value,
                            new=override.value,
                            cause="async",
                        )
                    )
                    state[key] = override
                    overridden[key] = override
                    async_changed = True
        if async_changed:
            settled = _settle(prepared, state, vector)

        # Stage 3: capture next state from settled capture pins.
        next_state: dict[str, LogicValue] = {}
        for spec in prepared.state_specs:
            forced_bits = [f"{spec.id}:{bit}" for bit in spec.state_bits]
            if all(key in overridden for key in forced_bits):
                for key in forced_bits:
                    next_state[key] = state[key]
                continue
            for bit_index, bit in enumerate(spec.state_bits):
                current = state[f"{spec.id}:{bit}"]
                if spec.type == "DFF":
                    value = dff_next(settled[f"SP:{spec.id}:d"])
                elif spec.type == "TFF":
                    value = tff_next(settled[f"SP:{spec.id}:t"], current)
                elif spec.type == "JKFF":
                    value = jkff_next(
                        settled[f"SP:{spec.id}:j"], settled[f"SP:{spec.id}:k"], current
                    )
                elif spec.type == "SRFF":
                    value = srff_next(
                        settled[f"SP:{spec.id}:s"], settled[f"SP:{spec.id}:r"], current
                    )
                elif spec.type == "REGISTER":
                    value = dff_next(settled[f"SP:{spec.id}:d{bit_index}"])
                else:  # COUNTER
                    en = settled[f"SP:{spec.id}:en"]
                    bits = [state[f"{spec.id}:{b}"] for b in spec.state_bits]
                    value = counter_next(en, bits)[bit_index]
                next_state[f"{spec.id}:{bit}"] = value

        # Stage 5 record data: the OBSERVED state (S_c, async-corrected) and the
        # settled outputs — captured BEFORE the commit modifies the state.
        state_row: dict[str, str] = {}
        for spec in prepared.state_specs:
            for bit in spec.state_bits:
                state_row[spec.signal_key(bit)] = state[f"{spec.id}:{bit}"].value
        output_row = {out_name: settled[f"OUT:{out_name}"].value for out_name in out_names}

        # Stage 4: simultaneous commit (state becomes S_{c+1} for the next cycle).
        for key in sorted(next_state):
            old = state[key]
            new = next_state[key]
            if old != new:
                comp_id, bit = key.split(":", 1)
                events.append(
                    SeqEvent(
                        cycle=cycle,
                        component=comp_id,
                        pin=bit,
                        old=old.value,
                        new=new.value,
                        cause="clock_edge",
                    )
                )
                state[key] = new

        cycle_rows.append(
            CycleRecord(
                cycle=cycle,
                inputs={name_: vector[name_].value for name_ in prepared.primary_input_names},
                state=state_row,
                outputs=output_row,
            )
        )
        for name_ in prepared.primary_input_names:
            waveforms[f"in:{name_}"].append(vector[name_].value)
        for signal_key, state_value in state_row.items():
            waveforms[signal_key].append(state_value)
        for out_name in out_names:
            waveforms[f"out:{out_name}"].append(output_row[out_name])

    final_keyed: dict[str, str] = {}
    for spec in prepared.state_specs:
        for bit in spec.state_bits:
            final_keyed[spec.signal_key(bit)] = state[f"{spec.id}:{bit}"].value

    return SequentialResult(
        engine_version=SEQUENTIAL_ENGINE_VERSION,
        scope=f"BOUNDED({cycles} cycles)",
        input_hash=_sequential_input_hash(circuit, cycles, inputs_per_cycle),
        cycles=tuple(cycle_rows),
        events=tuple(events),
        waveforms={key: tuple(values) for key, values in waveforms.items()},
        final_state=final_keyed,
        state_components=tuple(spec.id for spec in prepared.state_specs),
    )


def _settle(
    prepared: _Prepared,
    state: dict[str, LogicValue],
    vector: Mapping[str, LogicValue],
) -> dict[str, LogicValue]:
    """Settle the combinational network; returns map keyed by SP:/OUT: names."""
    inputs: dict[str, LogicValue] = dict(vector)
    for synth_name, (comp_id, bit) in prepared.q_inputs.items():
        inputs[synth_name] = state[f"{comp_id}:{bit}"]
    for synth_name, comp_id in prepared.qn_inputs.items():
        q_value = None
        for spec in prepared.state_specs:
            if spec.id == comp_id:
                q_value = state[f"{comp_id}:q"]
                break
        inputs[synth_name] = not_(q_value) if q_value is not None else LogicValue.UNKNOWN
    result = v1_simulate(prepared.v1_graph, inputs)
    settled: dict[str, LogicValue] = {}
    for synth_name in prepared.capture_outputs:
        settled[synth_name] = LogicValue(result.outputs[synth_name])
    for synth_name in prepared.async_outputs:
        settled[synth_name] = LogicValue(result.outputs[synth_name])
    for out_name in result.outputs:
        if not out_name.startswith("SP:"):
            settled[f"OUT:{out_name}"] = LogicValue(result.outputs[out_name])
    return settled


def _sequential_input_hash(
    circuit: Mapping[str, object],
    cycles: int,
    inputs_per_cycle: Sequence[Mapping[str, object]],
) -> str:
    import hashlib

    normalized_sequence = []
    for entry in inputs_per_cycle:
        normalized_sequence.append(
            {
                name: normalize_value(value).value
                for name, value in sorted(entry.items())
                if isinstance(name, str)
            }
        )
    payload = (
        f"2|{canonical_json(dict(circuit))}|"
        f"{canonical_json({'cycles': cycles, 'inputs': normalized_sequence})}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_checked(circuit: Mapping[str, object]) -> tuple[list[Component], list[Net], str | None]:
    from sequential_engine.graph import parse_circuit_v2

    return parse_circuit_v2(dict(circuit))


def sequential_result_to_dict(result: SequentialResult) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "engine_version": result.engine_version,
        "scope": result.scope,
        "input_hash": result.input_hash,
        "cycles": [
            {
                "cycle": row.cycle,
                "inputs": row.inputs,
                "state": row.state,
                "outputs": row.outputs,
            }
            for row in result.cycles
        ],
        "events": [
            {
                "cycle": event.cycle,
                "component": event.component,
                "pin": event.pin,
                "old": event.old,
                "new": event.new,
                "cause": event.cause,
            }
            for event in result.events
        ],
        "waveforms": {key: list(values) for key, values in result.waveforms.items()},
        "final_state": result.final_state,
        "state_components": list(result.state_components),
    }
