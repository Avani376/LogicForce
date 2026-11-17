"""SIGNATURE ACCEPTANCE TEST — Phase 9 exit criterion.

Master prompt requirement: "Explanation grounded in engine evidence."
Every finding in the explanation MUST cite a concrete trace step or report
verdict. The explanation is deterministic (same evidence → same output).
"""

from __future__ import annotations

from verify_engine import explain, explanation_to_dict

CPU_TRACE = {
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


def test_phase9_signature_every_finding_cites_evidence() -> None:
    explanation = explain("cpu_trace", CPU_TRACE)
    assert len(explanation.findings) >= 3
    for finding in explanation.findings:
        assert len(finding.evidence) >= 1, f"finding without evidence: {finding.text}"
        for citation in finding.evidence:
            assert "source" in citation
            assert citation["source"] in ("trace", "report")


def test_phase9_signature_deterministic() -> None:
    a = explanation_to_dict(explain("cpu_trace", CPU_TRACE))
    b = explanation_to_dict(explain("cpu_trace", CPU_TRACE))
    assert a == b  # byte-identical (engine rule 2)


def test_phase9_signature_flag_cause_cited() -> None:
    """The OF=1 explanation cites the ADD instruction at step 2 with the
    signed-overflow cause — derived from the engine's flag computation."""
    explanation = explain("cpu_trace", CPU_TRACE)
    of_findings = [f for f in explanation.findings if "OF=1" in f.text]
    assert len(of_findings) >= 1
    assert "ADD AL, 1" in of_findings[0].text
    assert "signed overflow" in of_findings[0].text
    assert any(e.get("step") == 2 for e in of_findings[0].evidence)
