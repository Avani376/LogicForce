"""Boolean engine property tests: NAND/NOR transforms and QM must preserve
function behavior — checked by evaluating over the full input space with the
engine's own evaluator (independent of the transform code being tested)."""

from __future__ import annotations

from boolean_engine import evaluate, kmap_simplify, parse, quine_mccluskey
from hypothesis import given, settings
from hypothesis import strategies as st

VARS = ["a", "b", "c"]
ENVS = [{v: bool(i >> k & 1) for k, v in enumerate(VARS)} for i in range(8)]


def _expr_tree(text: str):
    return parse(text)


class TestTransformEquivalence:
    @settings(max_examples=60, deadline=None)
    @given(seed=st.integers(min_value=0, max_value=0xFFFF))
    def test_nand_only_preserves_behavior(self, seed: int) -> None:
        original = "!(a & (b | !c)) | !(!a & b)"
        tree = _expr_tree(original)
        from boolean_engine import to_nand_only

        nand_text = to_nand_only(original)["nand_expression"]
        nand_tree = _expr_tree(nand_text)
        for env in ENVS:
            assert evaluate(tree, env) == evaluate(nand_tree, env), (seed, env)

    @settings(max_examples=60, deadline=None)
    @given(seed=st.integers(min_value=0, max_value=0xFFFF))
    def test_nor_only_preserves_behavior(self, seed: int) -> None:
        original = "!((a | !b) & (!a | c))"
        tree = _expr_tree(original)
        from boolean_engine import to_nor_only

        nor_text = to_nor_only(original)["nor_expression"]
        nor_tree = _expr_tree(nor_text)
        for env in ENVS:
            assert evaluate(tree, env) == evaluate(nor_tree, env), (seed, env)


class TestQmEquivalenceAndMinimality:
    @settings(max_examples=40, deadline=None)
    @given(
        m0=st.booleans(),
        m1=st.booleans(),
        m2=st.booleans(),
        m3=st.booleans(),
    )
    def test_kmap_and_qm_agree_2var(self, m0: bool, m1: bool, m2: bool, m3: bool) -> None:
        """For every 2-variable function, K-map and QM must produce equivalent expressions."""
        minterms = [i for i, on in enumerate([m0, m1, m2, m3]) if on]
        if not minterms:
            return
        kmap = kmap_simplify(minterms, [], 2)
        qm = quine_mccluskey(minterms, [], 2)
        kmap_tree = _expr_tree(str(kmap["expression"]))
        qm_tree = _expr_tree(str(qm["expression"]))
        for env in ENVS[:4]:  # 2^2 rows
            assert evaluate(kmap_tree, env) == evaluate(qm_tree, env), (minterms, env)

    @settings(max_examples=25, deadline=None)
    @given(
        m0=st.booleans(),
        m1=st.booleans(),
        m2=st.booleans(),
        m3=st.booleans(),
        m4=st.booleans(),
        m5=st.booleans(),
        m6=st.booleans(),
        m7=st.booleans(),
    )
    def test_qm_result_matches_minterms_3var(
        self, m0: bool, m1: bool, m2: bool, m3: bool, m4: bool, m5: bool, m6: bool, m7: bool
    ) -> None:
        """The QM expression must be 1 exactly on the minterms, 0 elsewhere."""
        bits = [m0, m1, m2, m3, m4, m5, m6, m7]
        minterms = [i for i, on in enumerate(bits) if on]
        if not minterms:
            return
        qm = quine_mccluskey(minterms, [], 3)
        tree = _expr_tree(str(qm["expression"]))
        for env_values in range(8):
            # QM emits uppercase variable names (A, B, C) — match them.
            env = {"A": bool(env_values >> 2 & 1), "B": bool(env_values >> 1 & 1), "C": bool(env_values & 1)}
            expected = env_values in minterms
            assert evaluate(tree, env) == expected, (minterms, env_values)
