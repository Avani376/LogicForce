"""Explanation engine tests: all 5 kinds, evidence citations, determinism."""

from __future__ import annotations

import json
from typing import Any

import pytest
from verify_engine import explain, explanation_to_dict, parse_explanation_request

CPU_TRACE_EVIDENCE: dict[str, Any] = {
    "stop_reason": "hlt",
    "trace": [
        {
            "kind": "instruction",
            "step": 1,
            "ip": 0,
            "instruction": "MOV AL, 0x7F",
            "register_changes": {"AL": 0x7F, "IP": 1},
            "flag_changes": {},
            "memory_changes": [],
            "halted": False,
        },
        {
            "kind": "instruction",
            "step": 2,
            "ip": 1,
            "instruction": "ADD AL, 1",
            "register_changes": {"AL": 0x80, "IP": 2},
            "flag_changes": {"OF": 1, "SF": 1, "AF": 1},
            "memory_changes": [],
            "halted": False,
        },
        {
            "kind": "instruction",
            "step": 3,
            "ip": 2,
            "instruction": "HLT",
            "register_changes": {"IP": 3},
            "flag_changes": {},
            "memory_changes": [],
            "halted": True,
        },
    ],
}


def test_cpu_trace_explanation_cites_evidence() -> None:
    explanation = explain("cpu_trace", CPU_TRACE_EVIDENCE)
    assert explanation.summary.startswith("3 instructions executed")
    assert len(explanation.findings) >= 3
    for finding in explanation.findings:
        assert len(finding.evidence) >= 1
        assert all(e["source"] == "trace" for e in finding.evidence)
    # flag change cited with cause
    of_findings = [f for f in explanation.findings if "OF=1" in f.text]
    assert len(of_findings) >= 1
    assert "signed overflow" in of_findings[0].text


def test_cpu_trace_explanation_deterministic() -> None:
    a = explanation_to_dict(explain("cpu_trace", CPU_TRACE_EVIDENCE))
    b = explanation_to_dict(explain("cpu_trace", CPU_TRACE_EVIDENCE))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_cpu_trace_hlt_and_bounded() -> None:
    explanation = explain("cpu_trace", CPU_TRACE_EVIDENCE)
    assert any(f.kind == "halt" for f in explanation.findings)

    bounded_evidence = {
        **CPU_TRACE_EVIDENCE,
        "stop_reason": "max_steps",
        "trace": CPU_TRACE_EVIDENCE["trace"][:1],
    }
    bounded = explain("cpu_trace", bounded_evidence)
    assert any("infinite loop" in f.text for f in bounded.findings)
    assert len(bounded.suggestions) >= 1


def test_verification_explanation_pass_and_fail() -> None:
    pass_evidence = {
        "verdict": "PASS",
        "scope": "EXHAUSTIVE(8 firings over 4 of 4 states)",
        "explored_cases": 8,
        "property": {"id": "P1", "expression": "!(a & b)"},
        "counterexample": None,
        "reason": None,
    }
    explanation = explain("verification", pass_evidence)
    assert "PASS" in explanation.summary
    assert any(f.kind == "verdict" for f in explanation.findings)

    fail_evidence = {
        "verdict": "FAIL",
        "scope": "EXHAUSTIVE(8 firings over 4 of 4 states)",
        "explored_cases": 8,
        "property": {"id": "P1", "expression": "!(a & b)"},
        "counterexample": {
            "inputs_sequence": [{"x": "1"}],
            "violating_state": "s1",
            "outputs": {"a": "1", "b": "1"},
        },
        "reason": None,
    }
    fail_explanation = explain("verification", fail_evidence)
    assert "FAIL" in fail_explanation.summary
    assert any("counterexample" in f.text.lower() for f in fail_explanation.findings)
    assert any("replay" in s.text.lower() for s in fail_explanation.suggestions)


def test_fault_experiment_explanation_detected_and_undetected() -> None:
    detected = {
        "detected": True,
        "checks": [{"id": "P1", "nominal_verdict": "PASS", "faulty_verdict": "FAIL", "detected": True}],
        "behavior": {"kind": "fsm", "first_divergence": {"cycle": 1}},
    }
    explanation = explain("fault_experiment", detected)
    assert "detected=True" in explanation.summary
    assert any("WAS detected" in f.text for f in explanation.findings if f.kind == "detection")

    undetected = {**detected, "detected": False}
    undetected["checks"] = [{"id": "P1", "nominal_verdict": "PASS", "faulty_verdict": "PASS", "detected": False}]
    undetected_explanation = explain("fault_experiment", undetected)
    assert "detected=False" in undetected_explanation.summary
    assert any("NOT detected" in f.text for f in undetected_explanation.findings)
    assert any("Add properties" in s.text for s in undetected_explanation.suggestions)


def test_cosim_explanation_port_events() -> None:
    cosim_evidence = {
        "verdict": "HALTED",
        "port_writes_total": 2,
        "trace": [
            {
                "cycle": 0,
                "kind": "instruction",
                "port_writes": [],
                "port_reads": [],
                "circuit_outputs": {"y": "X"},
            },
            {
                "cycle": 1,
                "kind": "instruction",
                "port_writes": [{"port": 64, "value": 1, "signal": "a"}],
                "port_reads": [],
                "circuit_outputs": {"y": "X"},
            },
            {
                "cycle": 2,
                "kind": "instruction",
                "port_writes": [],
                "port_reads": [{"port": 66, "value": "1", "signal": "y"}],
                "circuit_outputs": {"y": "1"},
            },
            {
                "cycle": 3,
                "kind": "halt",
                "port_writes": [],
                "port_reads": [],
                "circuit_outputs": {"y": "1"},
            },
        ],
    }
    explanation = explain("cosim", cosim_evidence)
    assert "port write" in explanation.summary
    assert any("port 64" in f.text and "next cycle" in f.text for f in explanation.findings)
    assert any("port 66" in f.text for f in explanation.findings)


def test_truth_table_explanation_x_propagation() -> None:
    tt_evidence = {
        "scope": "EXHAUSTIVE(4 input vectors)",
        "rows": [
            {"inputs": {"a": "0", "b": "0"}, "outputs": {"y": "0"}},
            {"inputs": {"a": "0", "b": "1"}, "outputs": {"y": "0"}},
            {"inputs": {"a": "1", "b": "0"}, "outputs": {"y": "0"}},
            {"inputs": {"a": "1", "b": "1"}, "outputs": {"y": "X"}},
        ],
    }
    explanation = explain("circuit_truth_table", tt_evidence)
    assert any("X/Z outputs" in f.text for f in explanation.findings)
    assert any("Drive all circuit inputs" in s.text for s in explanation.suggestions)


def test_unknown_kind_rejected() -> None:
    with pytest.raises(Exception) as excinfo:
        explain("quantum_entanglement", {"trace": []})
    assert "quantum" in str(excinfo.value)


def test_parse_request_validates() -> None:
    kind, evidence, question = parse_explanation_request(
        {
            "explanation_schema_version": 1,
            "kind": "cpu_trace",
            "evidence": {"trace": []},
            "question": "what happened?",
        }
    )
    assert kind == "cpu_trace"
    assert question == "what happened?"

    with pytest.raises(Exception) as excinfo:
        parse_explanation_request({"explanation_schema_version": 99, "kind": "cpu_trace", "evidence": {}})
    assert "SCHEMA" in str(excinfo.value) or "EXPLANATION" in str(excinfo.value)

    with pytest.raises(Exception) as excinfo:
        parse_explanation_request({"explanation_schema_version": 1, "kind": "cpu_trace", "evidence": {}})
    assert "non-empty" in str(excinfo.value)


def test_disclaimer_always_present() -> None:
    for kind in ("cpu_trace", "verification", "fault_experiment", "cosim", "circuit_truth_table"):
        evidence = {"trace": [], "rows": [], "verdict": "PASS", "detected": False}
        explanation = explain(kind, evidence)
        assert explanation.disclaimer.startswith("Generated from engine evidence")
        assert "Not an AI model output" in explanation.disclaimer


def test_serialization_shape() -> None:
    payload = explanation_to_dict(explain("cpu_trace", CPU_TRACE_EVIDENCE))
    assert set(payload) == {
        "schema_version",
        "engine_version",
        "kind",
        "summary",
        "findings",
        "suggestions",
        "disclaimer",
    }
    assert payload["schema_version"] == 1
    assert payload["engine_version"] == "0.9.0"
    for finding in payload["findings"]:
        assert set(finding) == {"kind", "text", "evidence"}
        assert len(finding["evidence"]) >= 1
