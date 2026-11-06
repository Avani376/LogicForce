"""Evidence-grounded explanation generator v1 (normative: explanations.md).

Rule-based analysis of real engine output. Deterministic. Every finding cites
trace steps or report verdicts. No LLM, no computation, no speculation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from logic_engine import SchemaError

EXPLANATION_SCHEMA_VERSION = 1
EXPLANATION_ENGINE_VERSION = "0.9.0"
EXPLANATION_KINDS = (
    "cpu_trace",
    "verification",
    "fault_experiment",
    "cosim",
    "circuit_truth_table",
)
DISCLAIMER = (
    "Generated from engine evidence by rule-based analysis. Not an AI model "
    "output. Suggestions are debugging hints, not verified results."
)


@dataclass(frozen=True)
class Finding:
    kind: str
    text: str
    evidence: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class Suggestion:
    text: str
    kind: str  # always "debugging_hint"


@dataclass(frozen=True)
class Explanation:
    engine_version: str
    kind: str
    summary: str
    findings: tuple[Finding, ...]
    suggestions: tuple[Suggestion, ...]
    disclaimer: str


def parse_explanation_request(raw: object) -> tuple[str, Mapping[str, object], str | None]:
    """Validate an explanation request; returns (kind, evidence, question)."""
    if not isinstance(raw, Mapping):
        raise SchemaError("EXPLANATION_SCHEMA_ERROR", "request must be a JSON object")
    version = raw.get("explanation_schema_version")
    if version != EXPLANATION_SCHEMA_VERSION:
        raise SchemaError(
            "EXPLANATION_SCHEMA_ERROR",
            f"expected explanation_schema_version {EXPLANATION_SCHEMA_VERSION}, got {version!r}",
        )
    kind = raw.get("kind")
    if kind not in EXPLANATION_KINDS:
        raise SchemaError(
            "EXPLANATION_KIND_UNKNOWN",
            f"'kind' must be one of {list(EXPLANATION_KINDS)}, got {kind!r}",
        )
    evidence = raw.get("evidence")
    if not isinstance(evidence, Mapping) or not evidence:
        raise SchemaError(
            "EXPLANATION_SCHEMA_ERROR",
            "'evidence' must be a non-empty object containing engine output",
        )
    question = raw.get("question")
    question = question if isinstance(question, str) else None
    return str(kind), evidence, question


def _finding(kind: str, text: str, source: str, **detail: object) -> Finding:
    return Finding(
        kind=kind,
        text=text,
        evidence=({"source": source, **detail},),
    )


def _explain_cpu_trace(
    evidence: Mapping[str, object],
) -> tuple[str, tuple[Finding, ...], tuple[Suggestion, ...]]:
    trace = evidence.get("trace", [])
    trace_list = list(trace) if isinstance(trace, list) else []
    stop_reason = str(evidence.get("stop_reason", "unknown"))
    findings: list[Finding] = []
    suggestions: list[Suggestion] = []

    reg_changes_total = sum(len(r.get("register_changes", {})) for r in trace_list if isinstance(r, Mapping))
    flag_changes_total = sum(len(r.get("flag_changes", {})) for r in trace_list if isinstance(r, Mapping))
    memory_changes_total = sum(len(r.get("memory_changes", [])) for r in trace_list if isinstance(r, Mapping))
    halted = any(r.get("halted") for r in trace_list if isinstance(r, Mapping))

    summary = (
        f"{len(trace_list)} instructions executed; "
        f"{reg_changes_total} register change(s); {flag_changes_total} flag change(s); "
        f"{memory_changes_total} memory write(s); stop_reason={stop_reason}"
    )

    for position, record in enumerate(trace_list):
        if not isinstance(record, Mapping):
            continue
        step = record.get("step", position)
        instruction = str(record.get("instruction", ""))
        kind = str(record.get("kind", "instruction"))

        if kind == "interrupt":
            findings.append(
                _finding(
                    "interrupt",
                    f"Interrupt {record.get('number')} ({record.get('source')}) fired at step {step}; "
                    f"handler at index {record.get('handler')}",
                    "trace",
                    step=step,
                )
            )
        elif kind == "iret":
            findings.append(
                _finding(
                    "iret",
                    f"IRET at step {step} resumed execution at index {record.get('resumed_at')}",
                    "trace",
                    step=step,
                )
            )
        elif kind == "pending_intr":
            findings.append(
                _finding(
                    "pending_intr",
                    f"Maskable interrupt {record.get('number')} parked at step {step} (IF=0)",
                    "trace",
                    step=step,
                )
            )

        reg_changes = record.get("register_changes", {})
        if isinstance(reg_changes, Mapping):
            for reg, value in reg_changes.items():
                findings.append(
                    _finding(
                        "register_change",
                        f"'{instruction}' at step {step} changed {reg} to {value}",
                        "trace",
                        step=step,
                        register=reg,
                        value=str(value),
                    )
                )

        flag_changes = record.get("flag_changes", {})
        if isinstance(flag_changes, Mapping):
            for flag, value in flag_changes.items():
                cause = _flag_cause(instruction, flag, value)
                findings.append(
                    _finding(
                        "flag_change",
                        f"'{instruction}' at step {step} set {flag}={value}: {cause}",
                        "trace",
                        step=step,
                        flag=flag,
                        value=str(value),
                    )
                )

        memory_changes = record.get("memory_changes", [])
        if isinstance(memory_changes, list):
            for mem_change in memory_changes:
                if isinstance(mem_change, (list, tuple)) and len(mem_change) >= 2:
                    findings.append(
                        _finding(
                            "memory_write",
                            f"'{instruction}' at step {step} wrote {mem_change[1]} to physical address {mem_change[0]}",
                            "trace",
                            step=step,
                        )
                    )

    if halted:
        findings.append(
            _finding(
                "halt",
                "CPU executed HLT",
                "trace",
            )
        )
    elif stop_reason == "max_steps":
        findings.append(
            _finding(
                "bounded",
                "Run stopped at the max_steps cap — the program may be in an infinite loop",
                "trace",
            )
        )
        suggestions.append(
            Suggestion(
                text="If the loop is intentional, increase max_steps; otherwise check the loop exit condition",
                kind="debugging_hint",
            )
        )

    if not findings:
        suggestions.append(
            Suggestion(
                text="No trace records were produced — check that the program has at least one instruction",
                kind="debugging_hint",
            )
        )

    return summary, tuple(findings), tuple(suggestions)


def _flag_cause(instruction: str, flag: str, value: int) -> str:
    """Human-readable cause for a flag change, derived from the instruction."""
    if value == 0:
        return f"{flag} cleared by {instruction.split()[0] if instruction else 'operation'}"
    causes = {
        "ZF": "result was zero",
        "SF": "result MSB is 1 (negative in two's complement)",
        "CF": "unsigned carry/borrow out of the operand width",
        "OF": "signed overflow (two's complement)",
        "AF": "BCD carry/borrow from bit 3 to bit 4",
        "PF": "low byte has even parity",
    }
    base = causes.get(flag, f"{flag} changed")
    return f"{flag} set: {base}"


def _explain_verification(
    evidence: Mapping[str, object],
) -> tuple[str, tuple[Finding, ...], tuple[Suggestion, ...]]:
    verdict = str(evidence.get("verdict", "unknown"))
    scope = str(evidence.get("scope", "unknown"))
    explored = evidence.get("explored_cases", 0)
    property_info = evidence.get("property", {})
    prop_id = str(property_info.get("id", "?")) if isinstance(property_info, Mapping) else "?"
    expression = str(property_info.get("expression", "?")) if isinstance(property_info, Mapping) else "?"
    counterexample = evidence.get("counterexample")
    reason = evidence.get("reason")

    summary = f"Property {prop_id} ({expression}): verdict={verdict}, scope={scope}, explored={explored} case(s)"
    findings: list[Finding] = []
    suggestions: list[Suggestion] = []

    findings.append(
        _finding(
            "verdict",
            f"Property {prop_id} verified {verdict} over {scope} ({explored} case(s) explored)",
            "report",
            verdict=verdict,
            scope=scope,
        )
    )
    if reason:
        findings.append(_finding("reason", f"Reason: {reason}", "report"))
    if counterexample is not None and isinstance(counterexample, Mapping):
        findings.append(
            _finding(
                "counterexample",
                f"Counterexample found: {_json_compact(counterexample)}",
                "report",
            )
        )
        suggestions.append(
            Suggestion(
                text="Replay the counterexample inputs through the simulation endpoint to reproduce the failure",
                kind="debugging_hint",
            )
        )
    if verdict == "INCOMPLETE":
        suggestions.append(
            Suggestion(
                text="The model exceeds the exhaustive bounds — consider reducing the input count or state space",
                kind="debugging_hint",
            )
        )
    return summary, tuple(findings), tuple(suggestions)


def _explain_fault_experiment(
    evidence: Mapping[str, object],
) -> tuple[str, tuple[Finding, ...], tuple[Suggestion, ...]]:
    detected = evidence.get("detected", False)
    checks = evidence.get("checks", [])
    check_list = list(checks) if isinstance(checks, list) else []
    behavior = evidence.get("behavior", {})
    summary = (
        f"Fault experiment: detected={detected}, {len(check_list)} check(s), "
        f"behavior probe kind={behavior.get('kind', '?') if isinstance(behavior, Mapping) else '?'}"
    )
    findings: list[Finding] = []
    suggestions: list[Suggestion] = []

    for check in check_list:
        if isinstance(check, Mapping):
            check_id = str(check.get("id", "?"))
            detected_by = check.get("detected", False)
            findings.append(
                _finding(
                    "check",
                    f"Check {check_id}: nominal={check.get('nominal_verdict')}, "
                    f"faulty={check.get('faulty_verdict')}, detected={detected_by}",
                    "report",
                    check_id=check_id,
                )
            )
    if detected:
        findings.append(_finding("detection", "The fault WAS detected by the property suite", "report"))
    else:
        findings.append(
            _finding(
                "detection",
                "The fault was NOT detected by this property suite — the suite may need additional properties",
                "report",
            )
        )
        suggestions.append(
            Suggestion(
                text="Add properties that cover the affected behavior to detect this fault class",
                kind="debugging_hint",
            )
        )
    return summary, tuple(findings), tuple(suggestions)


def _explain_cosim(
    evidence: Mapping[str, object],
) -> tuple[str, tuple[Finding, ...], tuple[Suggestion, ...]]:
    trace = evidence.get("trace", [])
    trace_list = list(trace) if isinstance(trace, list) else []
    verdict = str(evidence.get("verdict", "unknown"))
    port_writes_total = evidence.get("port_writes_total", 0)
    summary = f"Co-simulation: {len(trace_list)} cycle(s), {port_writes_total} port write(s), verdict={verdict}"
    findings: list[Finding] = []
    suggestions: list[Suggestion] = []

    for position, record in enumerate(trace_list):
        if not isinstance(record, Mapping):
            continue
        cycle = record.get("cycle", position)
        writes = record.get("port_writes", [])
        if isinstance(writes, list) and writes:
            for w in writes:
                if isinstance(w, Mapping):
                    findings.append(
                        _finding(
                            "port_write",
                            f"Cycle {cycle}: port {w.get('port')} wrote {w.get('value')} to signal {w.get('signal')!r} "
                            "(lands at next cycle's settle)",
                            "trace",
                            cycle=cycle,
                        )
                    )
        reads = record.get("port_reads", [])
        if isinstance(reads, list) and reads:
            for r in reads:
                if isinstance(r, Mapping):
                    findings.append(
                        _finding(
                            "port_read",
                            f"Cycle {cycle}: IN from port {r.get('port')} "
                            f"read {r.get('value')} (signal {r.get('signal')!r})",
                            "trace",
                            cycle=cycle,
                        )
                    )
    if verdict == "BOUNDED":
        suggestions.append(
            Suggestion(
                text="The cycle budget was exhausted — increase cycles or add an HLT to the program",
                kind="debugging_hint",
            )
        )
    return summary, tuple(findings), tuple(suggestions)


def _explain_truth_table(
    evidence: Mapping[str, object],
) -> tuple[str, tuple[Finding, ...], tuple[Suggestion, ...]]:
    rows = evidence.get("rows", [])
    row_list = list(rows) if isinstance(rows, list) else []
    scope = str(evidence.get("scope", "unknown"))
    x_count = sum(
        1
        for row in row_list
        if isinstance(row, Mapping) and any(str(v) in ("X", "Z") for v in row.get("outputs", {}).values())
    )
    summary = f"Truth table: {len(row_list)} row(s), scope={scope}, {x_count} row(s) with X/Z outputs"
    findings: list[Finding] = []
    suggestions: list[Suggestion] = []
    if x_count:
        findings.append(
            _finding(
                "x_propagation",
                f"{x_count} row(s) have X/Z outputs — unwritten or unresolved inputs propagate X",
                "report",
            )
        )
        suggestions.append(
            Suggestion(
                text="Drive all circuit inputs to 0 or 1 to eliminate X propagation",
                kind="debugging_hint",
            )
        )
    findings.append(
        _finding(
            "scope",
            f"Exhaustive over {len(row_list)} input vector(s)",
            "report",
        )
    )
    return summary, tuple(findings), tuple(suggestions)


def _json_compact(obj: object) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def explain(kind: str, evidence: Mapping[str, object], question: str | None = None) -> Explanation:
    """Generate a deterministic, evidence-cited explanation for the given kind."""
    if kind == "cpu_trace":
        summary, findings, suggestions = _explain_cpu_trace(evidence)
    elif kind == "verification":
        summary, findings, suggestions = _explain_verification(evidence)
    elif kind == "fault_experiment":
        summary, findings, suggestions = _explain_fault_experiment(evidence)
    elif kind == "cosim":
        summary, findings, suggestions = _explain_cosim(evidence)
    elif kind == "circuit_truth_table":
        summary, findings, suggestions = _explain_truth_table(evidence)
    else:
        raise SchemaError(
            "EXPLANATION_KIND_UNKNOWN",
            f"'kind' must be one of {list(EXPLANATION_KINDS)}, got {kind!r}",
        )
    return Explanation(
        engine_version=EXPLANATION_ENGINE_VERSION,
        kind=kind,
        summary=summary,
        findings=tuple(findings),
        suggestions=tuple(suggestions),
        disclaimer=DISCLAIMER,
    )


def explanation_to_dict(explanation: Explanation) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "engine_version": explanation.engine_version,
        "kind": explanation.kind,
        "summary": explanation.summary,
        "findings": [
            {
                "kind": f.kind,
                "text": f.text,
                "evidence": [dict(e) for e in f.evidence],
            }
            for f in explanation.findings
        ],
        "suggestions": [{"text": s.text, "kind": s.kind} for s in explanation.suggestions],
        "disclaimer": explanation.disclaimer,
    }
