"""v2 validation tests: sequential additions + v1 codes still enforced."""

from __future__ import annotations

from typing import Any

import pytest
from logic_engine import SchemaError, parse_circuit
from sequential_engine import validate_sequential
from sequential_engine.graph import parse_circuit_v2


def dff_circuit(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "FF1", "type": "DFF"},
            {"id": "OUT_q", "type": "OUTPUT", "params": {"name": "q"}},
        ],
        "nets": [
            {
                "id": "n_pre",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "pre"}],
            },
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "clr"}],
            },
            {
                "id": "n_q",
                "driver": {"component": "FF1", "pin": "q"},
                "sinks": [{"component": "OUT_q", "pin": "in"}],
            },
        ],
    }
    doc.update(overrides)
    return doc


def codes(doc: dict[str, Any]) -> list[str]:
    components, nets, name = parse_circuit_v2(doc)
    report = validate_sequential(components, nets, name)
    return [issue.code for issue in report.errors]


def test_valid_dff_feedback_circuit() -> None:
    doc = dff_circuit()
    doc["components"].append({"id": "N1", "type": "NOT"})
    doc["nets"].append(
        {
            "id": "n_q2",
            "driver": {"component": "FF1", "pin": "qn"},
            "sinks": [{"component": "N1", "pin": "a"}],
        }
    )
    doc["nets"].append(
        {
            "id": "n_d",
            "driver": {"component": "N1", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "d"}],
        }
    )
    assert codes(doc) == []


def test_feedback_through_state_is_not_a_loop() -> None:
    """q -> gate -> d is the whole point of sequential circuits — must validate."""
    doc = dff_circuit()
    doc["components"].append({"id": "N1", "type": "NOT"})
    doc["nets"].append(
        {
            "id": "n_q2",
            "driver": {"component": "FF1", "pin": "qn"},
            "sinks": [{"component": "N1", "pin": "a"}],
        }
    )
    doc["nets"].append(
        {
            "id": "n_d",
            "driver": {"component": "N1", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "d"}],
        }
    )
    assert "COMBINATIONAL_LOOP" not in codes(doc)


def test_pure_gate_loop_is_still_an_error() -> None:
    doc = dff_circuit()
    doc["components"].append({"id": "A", "type": "NAND"})
    doc["components"].append({"id": "B", "type": "NAND"})
    doc["nets"].append(
        {
            "id": "n1",
            "driver": {"component": "A", "pin": "out"},
            "sinks": [{"component": "B", "pin": "a"}],
        }
    )
    doc["nets"].append(
        {
            "id": "n2",
            "driver": {"component": "B", "pin": "out"},
            "sinks": [{"component": "A", "pin": "a"}],
        }
    )
    doc["nets"].append(
        {
            "id": "n3",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "A", "pin": "b"}],
        }
    )
    assert "COMBINATIONAL_LOOP" in codes(doc)


def test_dangling_async_pin_is_error() -> None:
    doc = dff_circuit()
    doc["nets"] = [n for n in doc["nets"] if n["id"] != "n_clr"]
    assert "DANGLING_INPUT_PIN" in codes(doc)


def test_invalid_register_widths() -> None:
    doc = dff_circuit()
    doc["components"].append({"id": "REG", "type": "REGISTER"})  # width missing
    doc["nets"].append(
        {
            "id": "nr1",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "REG", "pin": "pre"}],
        }
    )
    doc["nets"].append(
        {
            "id": "nr2",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "REG", "pin": "clr"}],
        }
    )
    doc["nets"].append(
        {
            "id": "nr3",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "REG", "pin": "d0"}],
        }
    )
    assert "INVALID_STATE_WIDTH" in codes(doc)

    doc["components"][-1] = {"id": "REG", "type": "REGISTER", "params": {"width": 17}}
    assert "INVALID_STATE_WIDTH" in codes(doc)

    doc["components"][-1] = {"id": "REG", "type": "REGISTER", "params": {"width": True}}
    assert "INVALID_STATE_WIDTH" in codes(doc)


def test_unknown_state_pin() -> None:
    doc = dff_circuit()
    doc["nets"].append(
        {
            "id": "nx",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "clock"}],
        }
    )
    assert "UNKNOWN_STATE_PIN" in codes(doc)


def test_reserved_io_names_rejected() -> None:
    doc = dff_circuit()
    doc["components"].append({"id": "IN_x", "type": "INPUT", "params": {"name": "SQ:hack"}})
    assert "RESERVED_IO_NAME" in codes(doc)

    doc2 = dff_circuit()
    doc2["components"].append({"id": "SQ:evil", "type": "CONST0"})
    assert "RESERVED_IO_NAME" in codes(doc2)


def test_v1_gate_types_still_accepted() -> None:
    doc = dff_circuit()
    doc["components"].append({"id": "G", "type": "XOR", "params": {"width": 3}})
    for pin in ("a", "b", "c"):
        doc["nets"].append(
            {
                "id": f"ng_{pin}",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "G", "pin": pin}],
            }
        )
    doc["nets"].append(
        {
            "id": "n_d",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "d"}],
        }
    )
    assert codes(doc) == []


def test_v1_document_rejected_by_v2_parser() -> None:
    doc = dff_circuit()
    doc["schema_version"] = 1
    # a v1-tagged document must be refused by the sequential parser (strict)
    with pytest.raises(SchemaError) as excinfo:
        parse_circuit_v2(doc)
    assert excinfo.value.code == "UNSUPPORTED_SCHEMA_VERSION"
    # and the v1 parser accepts it structurally (state types are validation's job)
    parse_circuit(doc)
