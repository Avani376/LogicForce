"""Canonical serialization and reproducibility hashing.

The ``input_hash`` recorded with every result identifies the exact circuit document
and input vector that produced it: SHA-256 over
``schema_version | canonical(circuit) | canonical(inputs)``.

Canonicalization rules (``docs/semantics/circuit-graph-schema.md``): JSON with
``(",", ":")`` separators, non-ASCII preserved, key order as constructed (document
order), inputs normalized to ``{"name": "0"|"1"}`` sorted by name.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from logic_engine.version import SCHEMA_VERSION


def canonical_json(value: object) -> str:
    """Deterministic compact JSON text for hashing.

    Keys are sorted lexicographically, so two documents that differ only in key
    order hash identically — the hash identifies the *design*, not its serialization
    quirks. Lists keep document order.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_inputs(inputs: Mapping[str, object]) -> dict[str, str]:
    """Normalize an input vector to sorted ``{"name": "0"|"1"|"X"|"Z"}`` strings."""
    from logic_engine.values import normalize_value

    normalized: dict[str, str] = {}
    for name in sorted(inputs):
        normalized[name] = normalize_value(inputs[name]).value
    return normalized


def input_hash(circuit: Mapping[str, object], inputs: Mapping[str, object]) -> str:
    """SHA-256 reproducibility hash of a circuit document plus input vector."""
    payload = (
        f"{SCHEMA_VERSION}|"
        f"{canonical_json(dict(circuit))}|"
        f"{canonical_json(canonical_inputs(inputs))}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
