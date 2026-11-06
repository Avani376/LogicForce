"""Delta-guided repair search (normative: faults-and-repair.md).

Strategy v1: diff the faulty model against the nominal reference, generate
candidate patches (the full restore first, then each single-field restore),
cap them, and **re-verify every candidate against the full property suite**.
A candidate is valid only when every property PASSes on it; "repaired" is
claimed only for such a candidate.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fault_engine.version import MAX_CANDIDATES
from logic_engine import CircuitNotValidError, SchemaError
from logic_engine.hashing import canonical_json
from verify_engine import verify_combinational_invariant, verify_fsm_invariant

from repair_engine.version import REPAIR_ENGINE_VERSION, REPAIR_SCHEMA_VERSION

REPAIR_OPS = (
    "restore_nominal",
    "set_to",
    "set_transition_outputs",
    "add_transition",
    "remove_transition",
    "set_component",
    "remove_component",
    "add_component",
    "set_net",
    "remove_net",
    "add_net",
)


@dataclass(frozen=True)
class RepairCandidate:
    patch: dict[str, object]
    valid: bool
    verdicts: tuple[dict[str, str], ...]
    note: str | None


@dataclass(frozen=True)
class RepairReport:
    engine_version: str
    input_hash: str
    candidates_considered: int
    cap: int
    candidates: tuple[RepairCandidate, ...]
    repaired_model: dict[str, object] | None
    re_verified: bool


def _doc_hash(doc: Mapping[str, object]) -> str:

    return hashlib.sha256(canonical_json(dict(doc)).encode("utf-8")).hexdigest()


def _set_to(nominal: Mapping[str, object], faulty: Mapping[str, object]) -> list[dict[str, object]]:
    """FSM transition deltas, aligned by index."""
    deltas: list[dict[str, object]] = []
    nominal_t = nominal.get("transitions", [])
    faulty_t = faulty.get("transitions", [])
    nominal_list = nominal_t if isinstance(nominal_t, list) else []
    faulty_list = faulty_t if isinstance(faulty_t, list) else []
    length = max(len(nominal_list), len(faulty_list))
    for index in range(length):
        if index >= len(faulty_list):
            deltas.append(
                {
                    "op": "add_transition",
                    "transition_index": index,
                    "value": copy.deepcopy(nominal_list[index]),
                }
            )
            continue
        if index >= len(nominal_list):
            deltas.append({"op": "remove_transition", "transition_index": index})
            continue
        nominal_entry = nominal_list[index]
        faulty_entry = faulty_list[index]
        if not isinstance(nominal_entry, Mapping) or not isinstance(faulty_entry, Mapping):
            continue
        if nominal_entry.get("to") != faulty_entry.get("to"):
            deltas.append({"op": "set_to", "transition_index": index, "value": nominal_entry.get("to")})
        if nominal_entry.get("outputs") != faulty_entry.get("outputs"):
            deltas.append(
                {
                    "op": "set_transition_outputs",
                    "transition_index": index,
                    "value": copy.deepcopy(dict(nominal_entry.get("outputs", {}))),
                }
            )
    return deltas


def _comb_deltas(nominal: Mapping[str, object], faulty: Mapping[str, object]) -> list[dict[str, object]]:
    deltas: list[dict[str, object]] = []
    nominal_components = _by_id(nominal, "components")
    faulty_components = _by_id(faulty, "components")
    for component_id in sorted(set(faulty_components) | set(nominal_components)):
        if component_id not in nominal_components:
            deltas.append({"op": "remove_component", "component_id": component_id})
        elif component_id not in faulty_components:
            deltas.append(
                {
                    "op": "add_component",
                    "component_id": component_id,
                    "value": copy.deepcopy(dict(nominal_components[component_id])),
                }
            )
        elif nominal_components[component_id] != faulty_components[component_id]:
            deltas.append(
                {
                    "op": "set_component",
                    "component_id": component_id,
                    "value": copy.deepcopy(dict(nominal_components[component_id])),
                }
            )
    nominal_nets = _by_id(nominal, "nets")
    faulty_nets = _by_id(faulty, "nets")
    for net_id in sorted(set(faulty_nets) | set(nominal_nets)):
        if net_id not in nominal_nets:
            deltas.append({"op": "remove_net", "net_id": net_id})
        elif net_id not in faulty_nets:
            deltas.append(
                {
                    "op": "add_net",
                    "net_id": net_id,
                    "value": copy.deepcopy(dict(nominal_nets[net_id])),
                }
            )
        elif nominal_nets[net_id] != faulty_nets[net_id]:
            deltas.append(
                {
                    "op": "set_net",
                    "net_id": net_id,
                    "value": copy.deepcopy(dict(nominal_nets[net_id])),
                }
            )
    return deltas


def _by_id(model: Mapping[str, object], key: str) -> dict[str, Mapping[str, object]]:
    items = model.get(key, [])
    result: dict[str, Mapping[str, object]] = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                result[str(item["id"])] = item
    return result


def compute_deltas(
    model_kind: str, nominal: Mapping[str, object], faulty: Mapping[str, object]
) -> list[dict[str, object]]:
    """Differences between faulty and nominal, as ordered repair deltas."""
    if model_kind == "fsm":
        return _set_to(nominal, faulty)
    if model_kind == "combinational":
        return _comb_deltas(nominal, faulty)
    raise SchemaError(
        "FAULT_SCHEMA_ERROR",
        f"model_kind must be 'fsm' or 'combinational', got {model_kind!r}",
    )


def apply_patch(model_kind: str, model: Mapping[str, object], patch: Mapping[str, object]) -> dict[str, object]:
    """Apply a repair patch to a copy of the model (never mutates the input)."""
    patched = copy.deepcopy(dict(model))
    if patch.get("op") == "restore_nominal":
        ops = patch.get("ops", [])
        if isinstance(ops, list):
            for delta in ops:
                if isinstance(delta, Mapping):
                    patched = apply_patch(model_kind, patched, delta)
        return patched

    op = str(patch.get("op", ""))
    if model_kind == "fsm":
        transitions = patched.get("transitions", [])
        if not isinstance(transitions, list):
            raise SchemaError("FAULT_APPLICATION_ERROR", "FSM model has no transitions array")
        if op == "set_to":
            index = _index(patch)
            transitions[index]["to"] = patch.get("value")
            return patched
        if op == "set_transition_outputs":
            index = _index(patch)
            transitions[index]["outputs"] = copy.deepcopy(patch.get("value", {}))
            return patched
        if op == "add_transition":
            index = _index(patch)
            transitions.insert(index, copy.deepcopy(patch.get("value", {})))
            return patched
        if op == "remove_transition":
            index = _index(patch)
            transitions.pop(index)
            return patched
        raise SchemaError("FAULT_APPLICATION_ERROR", f"unsupported repair op {op!r} for FSM")

    if model_kind == "combinational":
        components = patched.get("components", [])
        nets = patched.get("nets", [])
        if not isinstance(components, list) or not isinstance(nets, list):
            raise SchemaError("FAULT_APPLICATION_ERROR", "circuit model is malformed")
        if op == "set_component":
            component_id = str(patch.get("component_id"))
            for position, component in enumerate(components):
                if isinstance(component, Mapping) and component.get("id") == component_id:
                    components[position] = copy.deepcopy(patch.get("value", {}))
                    return patched
            raise SchemaError("FAULT_APPLICATION_ERROR", f"component {component_id!r} vanished")
        if op == "remove_component":
            component_id = str(patch.get("component_id"))
            patched["components"] = [
                c for c in components if not (isinstance(c, Mapping) and c.get("id") == component_id)
            ]
            return patched
        if op == "add_component":
            components.append(copy.deepcopy(patch.get("value", {})))
            return patched
        if op == "set_net":
            net_id = str(patch.get("net_id"))
            for position, net in enumerate(nets):
                if isinstance(net, Mapping) and net.get("id") == net_id:
                    nets[position] = copy.deepcopy(patch.get("value", {}))
                    return patched
            raise SchemaError("FAULT_APPLICATION_ERROR", f"net {net_id!r} vanished")
        if op == "remove_net":
            net_id = str(patch.get("net_id"))
            patched["nets"] = [n for n in nets if not (isinstance(n, Mapping) and n.get("id") == net_id)]
            return patched
        if op == "add_net":
            nets.append(copy.deepcopy(patch.get("value", {})))
            return patched
        raise SchemaError("FAULT_APPLICATION_ERROR", f"unsupported repair op {op!r} for circuits")

    raise SchemaError("FAULT_SCHEMA_ERROR", f"model_kind must be 'fsm' or 'combinational', got {model_kind!r}")


def _index(patch: Mapping[str, object]) -> int:
    value = patch.get("transition_index")
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError("FAULT_APPLICATION_ERROR", "patch missing transition_index")
    return value


def search_repairs(
    model_kind: str,
    nominal: Mapping[str, object],
    faulty: Mapping[str, object],
    properties: Sequence[Mapping[str, object]],
    max_candidates: int = 16,
) -> RepairReport:
    """Generate capped candidate patches and re-verify each against the suite."""
    if not 1 <= max_candidates <= MAX_CANDIDATES:
        raise SchemaError(
            "FAULT_SCHEMA_ERROR",
            f"max_candidates must be in [1, {MAX_CANDIDATES}], got {max_candidates}",
        )
    if not properties:
        raise SchemaError(
            "FAULT_SCHEMA_ERROR",
            "repair requires at least one property: 'repaired' is a safety claim "
            "and cannot be verified against an empty suite",
        )
    deltas = compute_deltas(model_kind, nominal, faulty)
    candidates: list[dict[str, object]] = [{"op": "restore_nominal", "ops": copy.deepcopy(deltas)}]
    candidates.extend(copy.deepcopy(delta) for delta in deltas)
    considered = len(candidates)
    candidates = candidates[:max_candidates]

    built: list[RepairCandidate] = []
    repaired_model: dict[str, object] | None = None
    for candidate in candidates:
        verdicts: list[dict[str, str]] = []
        valid = True
        note: str | None = None
        try:
            patched = apply_patch(model_kind, faulty, candidate)
            for property_raw in properties:
                if model_kind == "fsm":
                    report = verify_fsm_invariant(patched, property_raw)
                else:
                    report = verify_combinational_invariant(patched, property_raw)
                verdicts.append({"id": str(property_raw.get("id", "unnamed")), "verdict": report.verdict})
                if report.verdict != "PASS":
                    valid = False
        except (CircuitNotValidError, SchemaError) as exc:
            valid = False
            note = (
                f"candidate unusable: {exc.code}: {exc.message}"
                if isinstance(exc, SchemaError)
                else f"candidate model failed validation ({exc})"
            )
        built.append(
            RepairCandidate(
                patch=copy.deepcopy(dict(candidate)),
                valid=valid,
                verdicts=tuple(verdicts),
                note=note,
            )
        )
        if valid and repaired_model is None:
            try:
                repaired_model = apply_patch(model_kind, faulty, candidate)
            except SchemaError:  # pragma: no cover - same apply already succeeded
                repaired_model = None

    hash_hex = _doc_hash(
        {
            "nominal": dict(nominal),
            "faulty": dict(faulty),
            "properties": [dict(p) for p in properties],
            "max_candidates": max_candidates,
        }
    )
    return RepairReport(
        engine_version=REPAIR_ENGINE_VERSION,
        input_hash=hash_hex,
        candidates_considered=considered,
        cap=max_candidates,
        candidates=tuple(built),
        repaired_model=repaired_model,
        re_verified=repaired_model is not None,
    )


def repair_report_to_dict(report: RepairReport) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "schema_version": REPAIR_SCHEMA_VERSION,
        "engine_version": report.engine_version,
        "input_hash": report.input_hash,
        "candidates_considered": report.candidates_considered,
        "cap": report.cap,
        "candidates": [
            {
                "patch": candidate.patch,
                "valid": candidate.valid,
                "verdicts": [dict(v) for v in candidate.verdicts],
                "note": candidate.note,
            }
            for candidate in report.candidates
        ],
        "repaired_model": report.repaired_model,
        "re_verified": report.re_verified,
    }


__all__ = [
    "REPAIR_OPS",
    "RepairCandidate",
    "RepairReport",
    "compute_deltas",
    "apply_patch",
    "search_repairs",
    "repair_report_to_dict",
]
