/**
 * LogicForge workspace: palette | SVG canvas | validation + probes | trace | truth table.
 *
 * Rules encoded here (master prompt):
 * - The API/engine computes everything; this UI never invents signal values.
 * - The user always sees which design is loaded, what was simulated (hash), what
 *   failed validation, and the exact scope label of every result.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  HealthStatus,
  PinRefDoc,
  SimulationResult,
  TruthTableResult,
  ValidationReport,
} from './types'
import {
  ApiHttpError,
  apiHealth,
  apiSimulate,
  apiTruthTable,
} from './lib/api'
import {
  addComponent,
  connectPins,
  deleteComponent,
  fromDoc,
  GATE_TYPES,
  halfAdderExample,
  moveComponent,
  toDoc,
  toggleInput,
  type EditorState,
} from './lib/circuit'
import { Canvas } from './components/Canvas'
import { TruthTablePanel } from './components/TruthTablePanel'
import { TracePanel } from './components/TracePanel'
import { ValidationPanel } from './components/ValidationPanel'

const STORAGE_KEY = 'logicforge.circuit.v1'

interface History {
  past: EditorState[]
  future: EditorState[]
}

function computeNetValues(sim: SimulationResult | null): Record<string, string> {
  const values: Record<string, string> = {}
  if (sim === null) return values
  for (const event of sim.trace) values[event.net] = event.new
  return values
}

export function App(): JSX.Element {
  const [present, setPresent] = useState<EditorState>(() => halfAdderExample())
  const history = useRef<History>({ past: [], future: [] })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pendingPin, setPendingPin] = useState<PinRefDoc | null>(null)
  const [sim, setSim] = useState<SimulationResult | null>(null)
  const [validation, setValidation] = useState<ValidationReport | null>(null)
  const [connError, setConnError] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState<string>('Ready')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [tt, setTt] = useState<TruthTableResult | null>(null)
  const [ttError, setTtError] = useState<string | null>(null)
  const [showTt, setShowTt] = useState(false)

  const docJson = useMemo(() => JSON.stringify(toDoc(present)), [present])
  const inputsJson = useMemo(() => JSON.stringify(present.inputValues), [present])

  // --- engine health ---------------------------------------------------------
  useEffect(() => {
    let cancelled = false
    apiHealth()
      .then((h) => {
        if (!cancelled) setHealth(h)
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setHealth(null)
          setConnError(cause instanceof Error ? cause.message : String(cause))
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  // --- auto-simulation (engine is the source of truth) -----------------------
  useEffect(() => {
    const doc = JSON.parse(docJson) as Parameters<typeof apiSimulate>[0]
    const inputs = JSON.parse(inputsJson) as Record<string, string>
    let cancelled = false
    apiSimulate(doc, inputs)
      .then((result) => {
        if (cancelled) return
        setSim(result)
        setValidation(null)
        setConnError(null)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        if (cause instanceof ApiHttpError && cause.detail.code === 'VALIDATION_FAILED') {
          setSim(null)
          setConnError(null)
          setValidation({
            schema_version: 1,
            engine_version: '',
            ok: false,
            errors: cause.detail.errors ?? [],
            warnings: cause.detail.warnings ?? [],
          })
        } else {
          setConnError(cause instanceof Error ? cause.message : String(cause))
        }
      })
    return () => {
      cancelled = true
    }
  }, [docJson, inputsJson])

  // --- history helpers -------------------------------------------------------
  const pushHistory = useCallback((snapshot: EditorState): void => {
    history.current.past = [...history.current.past.slice(-99), snapshot]
    history.current.future = []
  }, [])

  const commit = useCallback(
    (next: EditorState): void => {
      pushHistory(present)
      setPresent(next)
    },
    [present, pushHistory],
  )

  const undo = useCallback((): void => {
    const { past, future } = history.current
    if (past.length === 0) return
    const previous = past[past.length - 1]
    history.current = { past: past.slice(0, -1), future: [present, ...future] }
    setPresent(previous)
    setStatusMsg('Undo')
  }, [present])

  const redo = useCallback((): void => {
    const { past, future } = history.current
    if (future.length === 0) return
    const next = future[0]
    history.current = { past: [...past, present], future: future.slice(1) }
    setPresent(next)
    setStatusMsg('Redo')
  }, [present])

  // --- canvas callbacks ------------------------------------------------------
  const handlePinClick = useCallback(
    (pin: PinRefDoc): void => {
      if (pendingPin === null) {
        setPendingPin(pin)
        setStatusMsg(
          pin.pin === 'out'
            ? `Wiring from ${pin.component}.${pin.pin} — click an input pin`
            : `Wiring into ${pin.component}.${pin.pin} — click an output pin`,
        )
        return
      }
      const first = pendingPin
      const second = pin
      // Allow input-first selection by normalizing order (output first).
      const ordered =
        first.pin === 'out'
          ? { from: first, to: second }
          : { from: second, to: first }
      const result = connectPins(present, ordered.from, ordered.to)
      setPendingPin(null)
      if (result.message === 'Connected') {
        commit(result.state)
        setStatusMsg(`Connected ${ordered.from.component} → ${ordered.to.component}.${ordered.to.pin}`)
      } else {
        setStatusMsg(result.message)
      }
    },
    [pendingPin, present, commit],
  )

  const handleToggleInput = useCallback(
    (ioName: string): void => {
      commit(toggleInput(present, ioName))
    },
    [present, commit],
  )

  const handleMove = useCallback(
    (id: string, x: number, y: number): void => {
      setPresent((current) => moveComponent(current, id, x, y))
    },
    [],
  )

  const handleDragBegin = useCallback((): void => {
    pushHistory(present)
  }, [present, pushHistory])

  const handleDelete = useCallback(
    (id: string): void => {
      commit(deleteComponent(present, id))
      setSelectedId(null)
      setStatusMsg(`Deleted ${id}`)
    },
    [present, commit],
  )

  const handleMoveByKeyboard = useCallback(
    (id: string, dx: number, dy: number): void => {
      const component = present.components.find((c) => c.id === id)
      if (component === undefined) return
      commit(moveComponent(present, id, component.x + dx, component.y + dy))
    },
    [present, commit],
  )

  // --- toolbar actions -------------------------------------------------------
  const handleAdd = useCallback(
    (type: string): void => {
      const x = 220 + ((present.components.length * 37) % 220)
      const y = 120 + ((present.components.length * 53) % 180)
      commit(addComponent(present, type as never, x, y))
      setStatusMsg(`Added ${type}`)
    },
    [present, commit],
  )

  const handleAddPrimary = useCallback(
    (kind: 'INPUT' | 'OUTPUT'): void => {
      const x = kind === 'INPUT' ? 40 : 480
      const y = 120 + ((present.components.length * 41) % 200)
      commit(addComponent(present, kind, x, y))
      setStatusMsg(`Added ${kind}`)
    },
    [present, commit],
  )

  const handleSave = useCallback((): void => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toDoc(present)))
    setStatusMsg('Saved to browser storage')
  }, [present])

  const handleLoad = useCallback((): void => {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === null) {
      setStatusMsg('Nothing saved yet')
      return
    }
    try {
      const loaded = fromDoc(JSON.parse(raw) as never)
      if (typeof loaded === 'string') {
        setStatusMsg(loaded)
        return
      }
      commit(loaded)
      setStatusMsg('Loaded saved circuit')
    } catch {
      setStatusMsg('Saved data is not valid JSON')
    }
  }, [commit])

  const handleExport = useCallback((): void => {
    const blob = new Blob([JSON.stringify(toDoc(present), null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${present.name || 'circuit'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setStatusMsg('Exported JSON')
  }, [present])

  const handleImport = useCallback(
    (file: File): void => {
      file
        .text()
        .then((text) => {
          const loaded = fromDoc(JSON.parse(text) as never)
          if (typeof loaded === 'string') {
            setStatusMsg(loaded)
            return
          }
          commit(loaded)
          setStatusMsg(`Imported ${loaded.name}`)
        })
        .catch(() => setStatusMsg('Import failed: not a valid circuit JSON file'))
    },
    [commit],
  )

  const handleTruthTable = useCallback((): void => {
    setShowTt(true)
    setTtError(null)
    setTt(null)
    apiTruthTable(JSON.parse(docJson) as Parameters<typeof apiTruthTable>[0])
      .then((result) => setTt(result))
      .catch((cause: unknown) => {
        if (cause instanceof ApiHttpError) {
          setTtError(
            `${cause.detail.code}${cause.detail.message ? `: ${cause.detail.message}` : ''}`,
          )
        } else {
          setTtError(cause instanceof Error ? cause.message : String(cause))
        }
      })
  }, [docJson])

  const handleClear = useCallback((): void => {
    commit({
      name: 'untitled',
      components: [],
      nets: [],
      inputValues: {},
      nextAutoId: 1,
    })
    setStatusMsg('Cleared canvas')
  }, [commit])

  // keyboard shortcuts
  useEffect(() => {
    const handler = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        setPendingPin(null)
        setSelectedId(null)
        setShowTt(false)
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.shiftKey) redo()
        else undo()
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
        event.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo])

  const netValues = useMemo(() => computeNetValues(sim), [sim])
  const inputComponents = present.components.filter((c) => c.type === 'INPUT')

  return (
    <div className="workspace">
      <header className="topbar">
        <h1>LogicForge</h1>
        <span className="subtitle">self-verifying digital systems workspace</span>
        <span
          className={`engine-chip ${health === null ? 'engine-off' : 'engine-on'}`}
          role="status"
          aria-label={
            health === null
              ? 'Engine status: offline'
              : `Engine status: online, version ${health.engine_version}`
          }
        >
          {health === null
            ? 'engine offline'
            : `engine ${health.engine_version} · api v${health.api_version}`}
        </span>
      </header>

      {connError !== null && (
        <div className="banner banner-error" role="alert">
          {connError}
        </div>
      )}

      <div className="toolbar" role="toolbar" aria-label="Circuit actions">
        {GATE_TYPES.map((type) => (
          <button key={type} type="button" onClick={() => handleAdd(type)}>
            + {type}
          </button>
        ))}
        <button type="button" onClick={() => handleAddPrimary('INPUT')}>
          + Input
        </button>
        <button type="button" onClick={() => handleAddPrimary('OUTPUT')}>
          + Output
        </button>
        <span className="toolbar-sep" aria-hidden="true" />
        <button type="button" onClick={undo} disabled={history.current.past.length === 0}>
          Undo
        </button>
        <button type="button" onClick={redo} disabled={history.current.future.length === 0}>
          Redo
        </button>
        <span className="toolbar-sep" aria-hidden="true" />
        <button type="button" onClick={handleSave}>Save</button>
        <button type="button" onClick={handleLoad}>Load</button>
        <button type="button" onClick={handleExport}>Export</button>
        <label className="import-label">
          Import
          <input
            type="file"
            accept="application/json,.json"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file !== undefined) handleImport(file)
              event.target.value = ''
            }}
          />
        </label>
        <button type="button" onClick={handleTruthTable}>Truth table</button>
        <button type="button" onClick={() => commit(halfAdderExample())}>
          Example
        </button>
        <button type="button" onClick={handleClear}>Clear</button>
      </div>

      <div className="main-grid">
        <section
          className="canvas-area"
          aria-label="Circuit canvas. Use arrow keys to move the selected component, Delete to remove it."
        >
          <Canvas
            state={present}
            netValues={netValues}
            outputs={sim?.outputs ?? {}}
            selectedId={selectedId}
            pendingPin={pendingPin}
            onSelect={setSelectedId}
            onPinClick={handlePinClick}
            onToggleInput={handleToggleInput}
            onMove={handleMove}
            onDragBegin={handleDragBegin}
            onDelete={handleDelete}
            onMoveByKeyboard={handleMoveByKeyboard}
          />
          {inputComponents.length === 0 && (
            <p className="canvas-hint">
              Add an Input, then gates, then wire their output pins (small circles) to
              inputs. Press Escape to cancel a wire.
            </p>
          )}
        </section>

        <aside className="side-panel" aria-label="Simulation status and validation">
          <ValidationPanel report={validation} sim={sim} />
          <section className="panel" aria-label="Primary outputs">
            <h2>Outputs</h2>
            {sim === null || Object.keys(sim.outputs).length === 0 ? (
              <p className="muted">No OUTPUT components yet.</p>
            ) : (
              <ul className="probe-list">
                {Object.entries(sim.outputs).map(([name, value]) => (
                  <li key={name}>
                    <span className="probe-name">{name}</span>
                    <span className={`probe-value value-${value}`} aria-label={`${name} is ${value}`}>
                      {value}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="panel" aria-label="Inputs">
            <h2>Input values</h2>
            {inputComponents.length === 0 ? (
              <p className="muted">No inputs yet.</p>
            ) : (
              <ul className="probe-list">
                {inputComponents.map((c) => (
                  <li key={c.id}>
                    <span className="probe-name">{c.ioName}</span>
                    <span className={`probe-value value-${present.inputValues[c.ioName ?? ''] ?? 'X'}`}>
                      {present.inputValues[c.ioName ?? ''] ?? 'X'}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleToggleInput(c.ioName ?? '')}
                      aria-label={`Toggle input ${c.ioName}`}
                    >
                      toggle
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <p className="muted status-note">
            Selected: {selectedId ?? 'none'} · {statusMsg}
          </p>
        </aside>
      </div>

      <TracePanel trace={sim?.trace ?? []} eventCount={sim?.event_count ?? 0} scope={sim?.scope ?? ''} hash={sim?.input_hash ?? ''} />

      {showTt && (
        <TruthTablePanel
          result={tt}
          error={ttError}
          onClose={() => setShowTt(false)}
        />
      )}
    </div>
  )
}
