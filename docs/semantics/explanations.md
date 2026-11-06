# Semantics: Evidence-Grounded Explanation Engine v1

Status: **CONTRACT for Phase 9** (implemented in `engines/verify/verify_engine/explain.py`
— reuses verify_engine's package since it already imports every engine's report shapes)
Engine version: 0.9.0 · Explanation schema version: **1**

## What v1 produces

A **deterministic explanation generator** that consumes real engine output
(traces, verification reports, fault experiments, cosim cycles) and produces
structured, evidence-cited analyses. It is rule-based — NOT an LLM call, NOT
speculative. Every claim in the explanation carries explicit `evidence`
citations pointing to trace steps, report verdicts, or register deltas.

This satisfies the master prompt's AI rules without an LLM dependency:
- "AI receives only a structured evidence bundle" ✓ (the request IS the bundle)
- "Ground in trace data; label suggestions unverified" ✓ (rule 5 below)
- "Clearly distinguish verified engineering results from AI-generated
  suggestions" ✓ (rule 6 below)

## Explanation request (schema 1)

```json
{
  "explanation_schema_version": 1,
  "kind": "cpu_trace" | "verification" | "fault_experiment" | "cosim" | "circuit_truth_table",
  "evidence": { …the engine report/trace document, verbatim… },
  "question": "why did AL become 0x80?"  // optional free text, stored but NOT interpreted
}
```

The `question` is stored in the response for the user's context but is **never
interpreted by the engine** — the explanation is generated from the evidence
alone, making it deterministic and replayable.

## Explanation response (schema 1)

```json
{
  "schema_version": 1,
  "engine_version": "0.9.0",
  "kind": "cpu_trace",
  "summary": "3 instructions executed; 2 register changes; 1 flag change",
  "findings": [
    {
      "kind": "flag_change",
      "text": "ADD AL, 1 at step 2: AL 0x7F→0x80 caused OF=1 (signed overflow: 127+1 exceeds 8-bit max)",
      "evidence": [
        { "source": "trace", "step": 2, "detail": "register_changes.AL: 0x7F→0x80" },
        { "source": "trace", "step": 2, "detail": "flag_changes.OF: 0→1" }
      ]
    }
  ],
  "suggestions": [
    { "text": "If OF was unexpected, check whether AL is intended as signed or unsigned", "kind": "debugging_hint" }
  ],
  "disclaimer": "Generated from engine evidence by rule-based analysis. Not an AI model output. Suggestions are debugging hints, not verified results."
}
```

## Explanation rules (normative)

1. **Evidence-only**: every `findings` item carries ≥1 `evidence` citation
   pointing to a concrete trace step, register delta, or report verdict.
   Findings without evidence are a contract violation.
2. **No computation**: the explanation engine never computes new results —
   it re-reads and restates what the engines already produced.
3. **Deterministic**: same evidence bundle ⇒ byte-identical explanation
   (no randomness, no model inference).
4. **Scope**: the explanation covers exactly the evidence provided — it never
   speculates about unexecuted code, unexplored states, or unchecked properties.
5. **Suggestions are labeled**: `suggestions` items carry `kind:
   "debugging_hint"` and are excluded from the verified-findings count.
6. **Disclaimer mandatory**: every response ends with the disclaimer text.
7. **No novelty or safety claims**: the engine explains what happened; it does
   not claim the design is correct, safe, or novel.

## Explanation kinds (v1)

| Kind | Evidence shape | Findings generated |
|---|---|---|
| `cpu_trace` | cpu8086 run trace (trace + stop_reason + registers) | register changes, flag changes with cause analysis, HLT/bounds, interrupt events |
| `verification` | VerificationReport | PASS/FAIL/INCOMPLETE with scope and counterexample analysis |
| `fault_experiment` | FaultExperimentReport | detection status, behavior divergence, per-check results |
| `cosim` | CoSimReport | port writes/reads, one-cycle latency, X propagation, circuit outputs |
| `circuit_truth_table` | TruthTableResult | row count, X-propagation notes, scope label |

Unknown kinds raise `EXPLANATION_KIND_UNKNOWN` (typed, fail-fast).

## Out of scope for v1

LLM/transformer integration, natural-language question answering, cross-project
explanations, real-time streaming explanations. These require an AI provider
key and a data-flow contract — deferred to a future version with explicit
user consent and provider configuration.
