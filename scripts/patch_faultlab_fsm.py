"""Phase 7-deploy patch: FSM model + invariant fields in FaultLab."""
from __future__ import annotations

import io

p = "apps/web/src/components/FaultLab.tsx"
s = io.open(p, encoding="utf-8").read()
n = 0


def rep(old: str, new: str) -> None:
    global s, n
    assert old in s, f"missing: {old[:70]!r}"
    s = s.replace(old, new, 1)
    n += 1


rep(
    """const EXAMPLE_FSM_FAULT = {
  fault_schema_version: 1,
  id: 'F-tx',
  operator: 'transition_redirect',
  target: { transition_index: 0 },
  params: { to: 'B', set_outputs: {} },
}""",
    """const EXAMPLE_FSM_MODEL = {
  fsm_schema_version: 1,
  inputs: ['x'],
  outputs: ['a1', 'a2'],
  states: ['s0', 's1'],
  initial: 's0',
  transitions: [
    { from: 's0', when: { x: '0' }, to: 's0', outputs: { a1: '1', a2: '0' } },
    { from: 's0', when: { x: '1' }, to: 's1', outputs: { a1: '0', a2: '0' } },
    { from: 's1', when: { x: '0' }, to: 's1', outputs: { a1: '0', a2: '1' } },
    { from: 's1', when: { x: '1' }, to: 's0', outputs: { a1: '1', a2: '0' } },
  ],
}

const EXAMPLE_FSM_FAULT = {
  fault_schema_version: 1,
  id: 'F-tx',
  operator: 'transition_redirect',
  target: { transition_index: 0 },
  params: { to: 's1', set_outputs: { a1: '1', a2: '1' } },
}

const EXAMPLE_FSM_INVARIANT = '!(a1 & a2)'""",
)

rep(
    """  const [faultText, setFaultText] = useState(() => {""",
    """  const [fsmModelText, setFsmModelText] = useState(JSON.stringify(EXAMPLE_FSM_MODEL, null, 2))
  const [fsmInvariantText, setFsmInvariantText] = useState(EXAMPLE_FSM_INVARIANT)
  const [faultText, setFaultText] = useState(() => {""",
)

# model resolution: FSM mode uses the pasted model document
rep(
    """      const fault = JSON.parse(faultText) as Record<string, unknown>
      const model = modelKind === 'combinational' ? (JSON.parse(circuitDoc) as Record<string, unknown>) : null
      const properties: Record<string, unknown>[] =
        modelKind === 'combinational' && invariant.trim() !== ''
          ? [{
              property_schema_version: 1,
              id: 'P-ui',
              kind: 'combinational_invariant',
              expression: invariant.trim(),
            }]
          : []
      const response = await fetch('/api/fault-experiments', {""",
    """      const fault = JSON.parse(faultText) as Record<string, unknown>
      const model =
        modelKind === 'combinational'
          ? (JSON.parse(circuitDoc) as Record<string, unknown>)
          : (JSON.parse(fsmModelText) as Record<string, unknown>)
      const properties: Record<string, unknown>[] = buildProperties(modelKind, invariant, fsmInvariantText)
      const response = await fetch('/api/fault-experiments', {""",
)

rep(
    """      const fault = JSON.parse(faultText) as Record<string, unknown>
      const model = modelKind === 'combinational' ? (JSON.parse(circuitDoc) as Record<string, unknown>) : null
      const applyResponse = await fetch('/api/faults/apply', {""",
    """      const fault = JSON.parse(faultText) as Record<string, unknown>
      const model =
        modelKind === 'combinational'
          ? (JSON.parse(circuitDoc) as Record<string, unknown>)
          : (JSON.parse(fsmModelText) as Record<string, unknown>)
      const applyResponse = await fetch('/api/faults/apply', {""",
)

rep(
    """      const properties: Record<string, unknown>[] =
        modelKind === 'combinational' && invariant.trim() !== ''
          ? [{
              property_schema_version: 1,
              id: 'P-ui',
              kind: 'combinational_invariant',
              expression: invariant.trim(),
            }]
          : []
      const response = await fetch('/api/repair-search', {""",
    """      const properties: Record<string, unknown>[] = buildProperties(modelKind, invariant, fsmInvariantText)
      const response = await fetch('/api/repair-search', {""",
)

rep(
    "  }, [faultText, modelKind, circuitDoc, invariant])",
    "  }, [faultText, modelKind, circuitDoc, invariant, fsmModelText, fsmInvariantText])",
)

# FSM-mode UI: model + invariant fields
rep(
    """        {modelKind === 'fsm' && (
          <p className="muted">
            In FSM mode, paste the FSM document as "model" inside the fault JSON payload —
            the experiment endpoint receives it via the apply call below.
          </p>
        )}""",
    """        {modelKind === 'fsm' && (
          <>
            <label className="muted" htmlFor="fsm-model-text">
              FSM model document (the experiment applies the fault to this machine)
            </label>
            <textarea
              id="fsm-model-text"
              className="asm-editor"
              rows={10}
              value={fsmModelText}
              onChange={(e) => setFsmModelText(e.target.value)}
              spellCheck={false}
            />
            <div className="verify-form">
              <input
                className="verify-input"
                value={fsmInvariantText}
                onChange={(e) => setFsmInvariantText(e.target.value)}
                aria-label="FSM detection invariant"
                placeholder="detection invariant over outputs, e.g. !(a1 & a2)"
              />
            </div>
          </>
        )}""",
)

# dependency arrays for setKind: fsmModel defaults unaffected; keep as is.

# buildProperties helper before runExperiment
rep(
    "  const runExperiment = useCallback(async (): Promise<void> => {",
    """  const buildProperties = useCallback(
    (kind: 'combinational' | 'fsm', comb: string, fsm: string): Record<string, unknown>[] => {
      if (kind === 'combinational') {
        return comb.trim() === ''
          ? []
          : [{
              property_schema_version: 1,
              id: 'P-ui',
              kind: 'combinational_invariant',
              expression: comb.trim(),
            }]
      }
      return fsm.trim() === ''
        ? []
        : [{
            property_schema_version: 1,
            id: 'P-fsm',
            kind: 'fsm_invariant',
            statement: 'workspace detection invariant',
            expression: fsm.trim(),
          }]
    },
    [],
  )

  const runExperiment = useCallback(async (): Promise<void> => {""",
)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print(f"FaultLab patched: {n}")
