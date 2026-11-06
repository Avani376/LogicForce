"""LogicForge boolean engine (v0.1.0)."""

from boolean_engine.boolean import (
    BoolExpr,
    evaluate,
    parse,
    to_nand_only,
    to_nor_only,
    to_pos,
    to_sop,
    truth_table,
    variables,
    verify_theorems,
)
from boolean_engine.kmap import kmap_simplify as kmap_simplify, quine_mccluskey as quine_mccluskey
from boolean_engine.version import BOOLEAN_ENGINE_VERSION

__all__ = [
    "BOOLEAN_ENGINE_VERSION",
    "BoolExpr",
    "parse",
    "evaluate",
    "variables",
    "truth_table",
    "to_sop",
    "to_pos",
    "verify_theorems",
    "to_nand_only",
    "to_nor_only",
]
