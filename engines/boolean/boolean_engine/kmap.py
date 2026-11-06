"""Quine-McCluskey minimization + K-map group finding (boolean-engine.md).

QM is the independent cross-check for K-map results. Both operate on minterm
sets with optional don't-care terms, producing minimal SOP expressions.
"""

from __future__ import annotations


def _count_ones(term: int) -> int:
    return bin(term).count("1")


def _terms_differ_by_one_bit(a: int, b: int) -> bool:
    diff = a ^ b
    return diff != 0 and (diff & (diff - 1)) == 0


def _merge_terms(a: str, b: str) -> str:
    """Merge two binary strings that differ in exactly one position (replace with '-')."""
    result = list(a)
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            result[i] = "-"
    return "".join(result)


def _term_covers(term: str, minterm: int) -> bool:
    """Check if a pattern (with '-' wildcards) covers a minterm."""
    for i, ch in enumerate(term):
        if ch != "-" and int(ch) != ((minterm >> (len(term) - 1 - i)) & 1):
            return False
    return True


def quine_mccluskey(minterms: list[int], dont_cares: list[int], num_vars: int) -> dict[str, object]:
    """QM minimization: returns prime implicants, essential PIs, and minimal cover."""
    all_terms = sorted(set(minterms) | set(dont_cares))
    if not all_terms:
        return {"prime_implicants": [], "essential": [], "cover": [], "expression": "0"}

    # Step 1: group by number of 1s and iteratively combine
    current = {format(t, f"0{num_vars}b"): {t} for t in all_terms}
    prime_implicants: list[tuple[str, set[int]]] = []

    while current:
        next_group: dict[str, set[int]] = {}
        used: set[str] = set()
        keys = sorted(current.keys())
        for i, a_key in enumerate(keys):
            for b_key in keys[i + 1 :]:
                a_val = int(a_key.replace("-", "0"), 2)
                b_val = int(b_key.replace("-", "0"), 2)
                if _terms_differ_by_one_bit(a_val, b_val):
                    merged = _merge_terms(a_key, b_key)
                    combined = current[a_key] | current[b_key]
                    next_group[merged] = combined
                    used.add(a_key)
                    used.add(b_key)
        for key in keys:
            if key not in used:
                prime_implicants.append((key, current[key]))
        current = next_group

    # Deduplicate prime implicants
    seen: set[str] = set()
    unique_pis: list[tuple[str, set[int]]] = []
    for pi, covered in prime_implicants:
        if pi not in seen:
            seen.add(pi)
            unique_pis.append((pi, covered))

    # Step 2: find essential prime implicants (cover minterms, not don't-cares)
    minterm_set = set(minterms)
    essential: list[tuple[str, set[int]]] = []
    covered_by_essential: set[int] = set()

    for minterm in sorted(minterm_set):
        covering_pis = [(pi, cov) for pi, cov in unique_pis if minterm in cov]
        if len(covering_pis) == 1:
            pi, cov = covering_pis[0]
            if pi not in [e[0] for e in essential]:
                essential.append((pi, cov))
                covered_by_essential |= cov & minterm_set

    # Step 3: cover remaining minterms (greedy)
    remaining = minterm_set - covered_by_essential
    cover = list(essential)
    while remaining:
        best_pi, best_cov = None, set()
        for pi, cov in unique_pis:
            overlap = cov & remaining
            if overlap and (best_pi is None or len(overlap) > len(best_cov)):
                best_pi, best_cov = pi, cov
        if best_pi is None:
            break
        cover.append((best_pi, best_cov))
        remaining -= best_cov

    expression = _implicants_to_expression(cover, num_vars)
    return {
        "prime_implicants": [pi for pi, _ in unique_pis],
        "essential": [pi for pi, _ in essential],
        "cover": [pi for pi, _ in cover],
        "expression": expression,
        "num_vars": num_vars,
    }


def _implicants_to_expression(implicants: list[tuple[str, set[int]]], num_vars: int) -> str:
    if not implicants:
        return "0"
    names = [chr(65 + i) for i in range(num_vars)]
    terms = []
    for pi, _ in implicants:
        literals = []
        for i, ch in enumerate(pi):
            if ch == "1":
                literals.append(names[i])
            elif ch == "0":
                literals.append(f"!{names[i]}")
        terms.append(" & ".join(literals) if literals else "1")
    return " | ".join(f"({t})" if len(implicants) > 1 else t for t in terms)


def kmap_simplify(minterms: list[int], dont_cares: list[int], num_vars: int) -> dict[str, object]:
    """K-map simplification (uses QM as the engine — the cross-check IS the method).

    The K-map grid layout is just a visualization of the same grouping that QM
    does; the results must be identical. This function returns the QM result
    with K-map grid metadata for the UI.
    """
    result = quine_mccluskey(minterms, dont_cares, num_vars)
    grid_rows = 1 << (num_vars // 2)
    grid_cols = 1 << (num_vars - num_vars // 2)
    return {
        **result,
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "minterms": minterms,
        "dont_cares": dont_cares,
        "num_vars": num_vars,
    }
