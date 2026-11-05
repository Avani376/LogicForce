"""Graph parsing / serialization and reproducibility hashing tests."""

from __future__ import annotations

import pytest
from logic_engine import SchemaError, circuit_to_dict, parse_circuit
from logic_engine.hashing import canonical_inputs, canonical_json, input_hash
from logic_engine.values import LogicValue


def minimal_doc() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "min",
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n1",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            }
        ],
    }


def test_roundtrip_serialization_preserves_semantics() -> None:
    doc = minimal_doc()
    graph = parse_circuit(doc)
    rebuilt = circuit_to_dict(graph)
    assert rebuilt == doc


def test_roundtrip_with_label_and_position() -> None:
    doc = minimal_doc()
    doc["components"][1]["label"] = "primary output"  # type: ignore[index]
    doc["components"][1]["position"] = {"x": 12.5, "y": 3}  # type: ignore[index]
    graph = parse_circuit(doc)
    rebuilt = circuit_to_dict(graph)
    assert rebuilt == doc


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema_version=0),
        lambda d: d.update(schema_version="1"),
        lambda d: None if d.pop("components") else None,
        lambda d: d.update(components="nope"),
        lambda d: d.update(nets={"not": "a list"}),
        lambda d: d["components"].append({"id": "", "type": "NOT"}),
        lambda d: d["components"].append({"id": "X"}),
        lambda d: d["components"].append({"id": "X", "type": ""}),
        lambda d: d["components"].append("not-a-dict"),
        lambda d: d["components"].append({"id": "X", "type": "NOT", "params": [1]}),
        lambda d: d["nets"].append({"id": 123, "driver": None, "sinks": []}),
        lambda d: d["nets"].append({"id": "", "driver": None, "sinks": []}),
        lambda d: d["nets"][0].update(sinks="bad"),
        lambda d: d["nets"][0].update(sinks=["not-a-ref"]),
        lambda d: d.update(schema_version=None),
    ],
)
def test_malformed_documents_raise_typed_schema_errors(mutate: object) -> None:
    doc = minimal_doc()
    mutate(doc)
    with pytest.raises(SchemaError) as excinfo:
        parse_circuit(doc)
    assert excinfo.value.code in ("UNSUPPORTED_SCHEMA_VERSION", "INVALID_DOCUMENT")


def test_non_mapping_document_raises() -> None:
    with pytest.raises(SchemaError):
        parse_circuit(42)


def test_schema_version_and_name_survive() -> None:
    graph = parse_circuit(minimal_doc())
    assert graph.schema_version == 1
    assert graph.name == "min"


def test_canonical_json_sorts_keys_and_is_order_insensitive() -> None:
    value = {"b": 1, "a": [1, 2, {"z": "x"}]}
    assert canonical_json(value) == '{"a":[1,2,{"z":"x"}],"b":1}'
    assert canonical_json(value) == canonical_json(dict(reversed(list(value.items()))))


def test_canonical_inputs_normalizes_and_sorts() -> None:
    assert canonical_inputs({"b": 1, "a": "X"}) == {"a": "X", "b": "1"}
    assert canonical_inputs({}) == {}


def test_input_hash_is_stable_and_sensitive() -> None:
    doc = minimal_doc()
    h1 = input_hash(doc, {"a": "1"})
    h2 = input_hash(dict(doc), {"a": 1})
    assert h1 == h2  # normalization makes int and str forms identical
    assert len(h1) == 64
    assert h1 != input_hash(doc, {"a": "0"})
    changed = minimal_doc()
    changed["name"] = "other"
    assert h1 != input_hash(changed, {"a": "1"})


def test_input_hash_accepts_enum_values() -> None:
    doc = minimal_doc()
    assert input_hash(doc, {"a": LogicValue.ONE}) == input_hash(doc, {"a": "1"})
