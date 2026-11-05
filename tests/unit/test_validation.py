"""Validation report tests — every code from the authoritative schema-v1 table."""

from __future__ import annotations

from typing import Any

import pytest
from logic_engine import parse_circuit, validate


def circuit(**overrides: Any) -> dict[str, Any]:
    """Minimal valid circuit: one input, one buffer, one output."""
    doc: dict[str, Any] = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "G", "type": "BUFFER"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n1",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G", "pin": "a"}],
            },
            {
                "id": "n2",
                "driver": {"component": "G", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
        ],
    }
    doc.update(overrides)
    return doc


def codes(doc: dict[str, Any]) -> list[str]:
    report = validate(parse_circuit(doc))
    return [issue.code for issue in report.errors]


def test_minimal_valid_circuit_ok() -> None:
    report = validate(parse_circuit(circuit()))
    assert report.ok
    assert report.errors == ()
    assert report.warnings == ()


def test_dangling_input_pin() -> None:
    doc = circuit()
    doc["nets"] = [doc["nets"][0]]  # drop the net feeding the output
    # OUT_y.in becomes dangling; G's undriven output pin is harmless in v1
    # (no net consumes it, so it cannot corrupt any value).
    assert codes(doc) == ["DANGLING_INPUT_PIN"]


def test_multi_driver_net_two_outputs() -> None:
    doc = circuit()
    doc["components"].append({"id": "IN_b", "type": "INPUT", "params": {"name": "b"}})
    doc["nets"][0]["driver"] = {"component": "IN_b", "pin": "out"}
    doc["nets"].append(
        {
            "id": "n3",
            "driver": {"component": "IN_a", "pin": "out"},
            "sinks": [{"component": "G", "pin": "a"}],
        }
    )
    assert "MULTI_DRIVER_NET" in codes(doc)


def test_multi_driver_net_input_fed_twice() -> None:
    doc = circuit()
    doc["components"].append({"id": "IN_b", "type": "INPUT", "params": {"name": "b"}})
    doc["nets"][0]["sinks"].append({"component": "G", "pin": "a"})
    doc["nets"].append(
        {
            "id": "n3",
            "driver": {"component": "IN_b", "pin": "out"},
            "sinks": [{"component": "G", "pin": "a"}],
        }
    )
    assert "MULTI_DRIVER_NET" in codes(doc)


def test_net_without_driver() -> None:
    doc = circuit()
    doc["nets"][0]["driver"] = None
    assert "MULTI_DRIVER_NET" in codes(doc)


def test_unknown_pin_reference_driver() -> None:
    doc = circuit()
    doc["nets"][0]["driver"] = {"component": "G", "pin": "in"}
    assert "UNKNOWN_PIN_REFERENCE" in codes(doc)


def test_unknown_pin_reference_missing_component() -> None:
    doc = circuit()
    doc["nets"][0]["driver"] = {"component": "GHOST", "pin": "out"}
    assert "UNKNOWN_PIN_REFERENCE" in codes(doc)


def test_unknown_component_type() -> None:
    doc = circuit()
    doc["components"][1]["type"] = "MAGIC"
    assert "UNKNOWN_COMPONENT_TYPE" in codes(doc)


def test_duplicate_component_id() -> None:
    doc = circuit()
    doc["components"].append({"id": "G", "type": "NOT"})
    assert "DUPLICATE_COMPONENT_ID" in codes(doc)


def test_duplicate_net_id() -> None:
    doc = circuit()
    doc["nets"][1]["id"] = "n1"
    assert "DUPLICATE_NET_ID" in codes(doc)


def test_duplicate_input_name() -> None:
    doc = circuit()
    doc["components"].append({"id": "IN_a2", "type": "INPUT", "params": {"name": "a"}})
    assert "DUPLICATE_IO_NAME" in codes(doc)


def test_duplicate_output_name() -> None:
    doc = circuit()
    doc["components"].append(
        {"id": "OUT_y2", "type": "OUTPUT", "params": {"name": "y"}}
    )
    assert "DUPLICATE_IO_NAME" in codes(doc)


def test_same_name_across_kinds_is_allowed() -> None:
    doc = circuit()
    doc["components"].append(
        {"id": "OUT_a", "type": "OUTPUT", "params": {"name": "a"}}
    )
    out_net = {
        "id": "n3",
        "driver": {"component": "G", "pin": "out"},
        "sinks": [{"component": "OUT_a", "pin": "in"}],
    }
    doc["nets"].append(out_net)
    assert validate(parse_circuit(doc)).ok


def test_missing_input_name() -> None:
    doc = circuit()
    doc["components"][0]["params"] = {}
    assert "MISSING_PARAM" in codes(doc)


def test_empty_input_name_invalid() -> None:
    doc = circuit()
    doc["components"][0]["params"] = {"name": ""}
    assert "INVALID_PARAM" in codes(doc)


@pytest.mark.parametrize("width", [1, 17, "2", True, False, 2.0, None])
def test_invalid_gate_width(width: object) -> None:
    doc = circuit()
    doc["components"][1] = {"id": "G", "type": "AND", "params": {"width": width}}
    doc["nets"][0]["sinks"].append({"component": "G", "pin": "b"})
    assert "INVALID_PARAM" in codes(doc)


def test_unexpected_param_rejected() -> None:
    doc = circuit()
    doc["components"][1]["params"] = {"frobnicate": True}
    assert "INVALID_PARAM" in codes(doc)


def test_label_and_position_are_display_only() -> None:
    doc = circuit()
    doc["components"][1]["label"] = "isolation buffer"
    doc["components"][1]["position"] = {"x": 10, "y": 20}
    assert validate(parse_circuit(doc)).ok


def test_unread_net_is_warning_not_error() -> None:
    doc = circuit()
    doc["components"].append({"id": "IN_sp", "type": "INPUT", "params": {"name": "spare"}})
    doc["nets"].append(
        {"id": "n9", "driver": {"component": "IN_sp", "pin": "out"}, "sinks": []}
    )
    report = validate(parse_circuit(doc))
    assert report.ok
    assert [w.code for w in report.warnings] == ["UNREAD_NET"]


def test_two_gate_cycle() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "I", "type": "INPUT", "params": {"name": "i"}},
            {"id": "A", "type": "NAND"},
            {"id": "B", "type": "NAND"},
        ],
        "nets": [
            {
                "id": "n1",
                "driver": {"component": "A", "pin": "out"},
                "sinks": [{"component": "B", "pin": "a"}],
            },
            {
                "id": "n2",
                "driver": {"component": "B", "pin": "out"},
                "sinks": [{"component": "A", "pin": "a"}],
            },
            {
                "id": "n3",
                "driver": {"component": "I", "pin": "out"},
                "sinks": [{"component": "A", "pin": "b"}],
            },
        ],
    }
    assert "COMBINATIONAL_LOOP" in codes(doc)


def test_self_loop_is_cycle() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "I", "type": "INPUT", "params": {"name": "i"}},
            {"id": "A", "type": "NOR"},
        ],
        "nets": [
            {
                "id": "n1",
                "driver": {"component": "A", "pin": "out"},
                "sinks": [{"component": "A", "pin": "a"}],
            },
            {
                "id": "n2",
                "driver": {"component": "I", "pin": "out"},
                "sinks": [{"component": "A", "pin": "b"}],
            },
        ],
    }
    assert "COMBINATIONAL_LOOP" in codes(doc)


def test_validation_is_complete_not_fail_fast() -> None:
    doc = circuit()
    doc["components"].append({"id": "IN_a", "type": "INPUT", "params": {"name": "a"}})
    doc["components"].append({"id": "G2", "type": "WEDGE"})
    found = codes(doc)
    assert "DUPLICATE_COMPONENT_ID" in found
    assert "DUPLICATE_IO_NAME" in found
    assert "UNKNOWN_COMPONENT_TYPE" in found
    assert len(found) == 3


def test_unsupported_schema_version_raises() -> None:
    doc = circuit()
    doc["schema_version"] = 2
    from logic_engine import SchemaError

    with pytest.raises(SchemaError) as excinfo:
        parse_circuit(doc)
    assert excinfo.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_non_object_document_raises() -> None:
    from logic_engine import SchemaError

    with pytest.raises(SchemaError) as excinfo:
        parse_circuit(["not", "a", "document"])
    assert excinfo.value.code == "INVALID_DOCUMENT"


def test_width_three_gate_pins_are_abc() -> None:
    """width=3 gate: pin 'c' is real; leaving it unconnected must be an error."""
    doc = circuit()
    doc["components"][1] = {"id": "G", "type": "AND", "params": {"width": 3}}
    report = validate(parse_circuit(doc))
    dangling = [e for e in report.errors if e.code == "DANGLING_INPUT_PIN"]
    assert any("G.c" in e.message for e in dangling)
