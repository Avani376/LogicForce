/**
 * 8086 panel: assembly editor, registers, interrupt trace, run/step controls.
 * Talks to /api/8086/* — the engine computes, this panel displays.
 */

import { useCallback, useEffect, useState } from 'react'

import { playError, playRunDone } from '../lib/sounds'
import { emitSparky } from './Sparky'

interface TraceEntry {
    kind: string
    step: number
    ip: number
    instruction: string
    register_changes: Record<string, number>
    flag_changes: Record<string, number>
    memory_changes: [number, number][]
    halted: boolean
    number?: number
    source?: string
    handler?: number
    resumed_at?: number
}

interface MemoryDump {
    segment: number
    offset: number
    bytes: number[]
}

interface RunResult {
    stop_reason: string
    registers: Record<string, number>
    flags: Record<string, number>
    trace: TraceEntry[]
    memory?: MemoryDump[]
}

interface PicEvent {
    at_step: number
    op: string
    line: number
    masked?: boolean
}

interface PicResult {
    deliveries: { at_step: number; line: number; vector: number }[]
    final_registers: { IRR: number; ISR: number; IMR: number }
    scope: string
    stop_reason?: string
}

const DEFAULT_PROGRAM = `MOV CX, 5
MOV AX, 0
MOV BX, 1
sum:
    ADD AX, BX
    INC BX
    LOOP sum
    HLT`

const WORD_REGS = ['AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'IP']

const FLAG_NAMES = ['CF', 'PF', 'AF', 'ZF', 'SF', 'OF', 'IF', 'DF']

export function Cpu8086Panel(): JSX.Element {
    const [source, setSource] = useState(DEFAULT_PROGRAM)
    const [result, setResult] = useState<RunResult | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [maxSteps, setMaxSteps] = useState(200)
    const [picBase, setPicBase] = useState(8)
    const [picEvents, setPicEvents] = useState('[{ "at_step": 3, "op": "request", "line": 2 }]')
    const [picResult, setPicResult] = useState<PicResult | null>(null)
    const [picError, setPicError] = useState<string | null>(null)
    const [running, setRunning] = useState(false)
    const [breakpointsText, setBreakpointsText] = useState('')
    const [memOffset, setMemOffset] = useState(0x300)
    const [memLength, setMemLength] = useState(16)

    const parseBreakpoints = useCallback((): number[] => {
        return breakpointsText
            .split(/[\s,]+/)
            .filter((t) => t.trim() !== '')
            .map((t) => parseInt(t, 16))
            .filter((v) => !Number.isNaN(v))
    }, [breakpointsText])

    const run = useCallback(async (): Promise<void> => {
        setError(null)
        setRunning(true)
        try {
            const response = await fetch('/api/8086/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source,
                    max_steps: maxSteps,
                    breakpoints: parseBreakpoints(),
                    memory_dumps: [
                        { segment: 0, offset: memOffset, length: memLength },
                        { segment: 0, offset: 0xFFEC, length: 16 }, // stack window below SP
                    ],
                }),
            })
            if (!response.ok) {
                const body = await response.json()
                setError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`)
                return
            }
            const body = (await response.json()) as RunResult
            setResult(body)
            playRunDone()
            if (body.stop_reason === 'hlt') {
                emitSparky({
                    mood: 'happy',
                    message: `Halted cleanly after ${body.trace.length} steps — AX = ${body.registers.AX ?? 0}. Lovely!`,
                })
            } else {
                emitSparky({ mood: 'thinking', message: `Run bounded at ${body.trace.length} steps (stop_reason: ${body.stop_reason}).` })
            }
        } catch (cause) {
            playError()
            emitSparky({ mood: 'sad', message: 'That run hit an error — check the message above, the assembler is very specific!' })
            setError(cause instanceof Error ? cause.message : String(cause))
        } finally {
            setRunning(false)
        }
    }, [source, maxSteps, parseBreakpoints, memOffset, memLength])

    const runPic = useCallback(async (): Promise<void> => {
        setPicError(null)
        setPicResult(null)
        try {
            const events = JSON.parse(picEvents) as PicEvent[]
            const withProgram = window.confirm(
                'Also run the current assembly with the PIC-derived schedule? (Cancel = resolve flow only)'
            )
            const payload: Record<string, unknown> = {
                base_vector: picBase,
                events,
                ...(withProgram ? { program: { source, max_steps: maxSteps } } : {}),
            }
            const response = await fetch('/api/8086/pic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            })
            const body = await response.json()
            if (!response.ok) {
                setPicError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`)
                return
            }
            setPicResult(body as PicResult)
        } catch (cause) {
            setPicError(cause instanceof Error ? cause.message : String(cause))
        }
    }, [picBase, picEvents, source, maxSteps])

    useEffect(() => { void run() }, []) // initial run

    const regs = result?.registers ?? {}
    const flags = result?.flags ?? {}
    const trace = result?.trace ?? []

    return (
        <div className="cpu8086-panel">
            <h2>8086 Virtual Processor</h2>
            <div className="cpu8086-grid">
                <div className="cpu8086-editor">
                    <h3>Assembly</h3>
                    <textarea
                        className="asm-editor"
                        value={source}
                        onChange={(e) => setSource(e.target.value)}
                        rows={14}
                        spellCheck={false}
                        aria-label="8086 assembly source code"
                    />
                    <div className="cpu8086-controls">
                        <label>
                            max_steps: <input type="number" value={maxSteps} min={1} max={100000}
                                onChange={(e) => setMaxSteps(Number(e.target.value) || 200)} />
                        </label>
                        <label>
                            breakpoints: <input value={breakpointsText} placeholder="e.g. 4, 0xA"
                                aria-label="Breakpoint instruction indices (hex or decimal)"
                                onChange={(e) => setBreakpointsText(e.target.value)} />
                        </label>
                        <button type="button" onClick={() => void run()} disabled={running}>
                            {running ? 'Running…' : '▶ Run'}
                        </button>
                    </div>
                    <div className="cpu8086-controls">
                        <label>
                            memory at 0:{' '}
                            <input type="number" value={memOffset} min={0} max={65535}
                                aria-label="Memory dump start offset"
                                onChange={(e) => setMemOffset(Number(e.target.value) || 0)} />
                        </label>
                        <label>
                            length: <input type="number" value={memLength} min={1} max={256}
                                aria-label="Memory dump length"
                                onChange={(e) => setMemLength(Number(e.target.value) || 16)} />
                        </label>
                    </div>
                    {error && <p className="banner-error">{error}</p>}
                    <h3>8259 PIC (Phase C7)</h3>
                    <div className="cpu8086-controls">
                        <label>
                            base_vector: <input type="number" value={picBase} min={0} max={248} step={8}
                                onChange={(e) => setPicBase(Number(e.target.value) || 8)} />
                        </label>
                        <button type="button" onClick={() => void runPic()}>Resolve PIC flow</button>
                    </div>
                    <textarea
                        className="asm-editor"
                        value={picEvents}
                        onChange={(e) => setPicEvents(e.target.value)}
                        rows={3}
                        spellCheck={false}
                        aria-label="PIC scheduled events as JSON"
                    />
                    {picError && <p className="banner-error">{picError}</p>}
                    {picResult && (
                        <div className="counterexample">
                            <p>scope {picResult.scope} · IRR={picResult.final_registers.IRR} ISR={picResult.final_registers.ISR} IMR={picResult.final_registers.IMR}</p>
                            <ul className="issue-list">
                                {picResult.deliveries.length === 0
                                    ? <li className="issue">No vectors delivered.</li>
                                    : picResult.deliveries.map((d) => (
                                        <li key={`${d.at_step}-${d.vector}`} className="issue">
                                            step {d.at_step}: IR{d.line} → vector {d.vector}
                                            {picResult.stop_reason !== undefined ? ' (ran through CPU)' : ''}
                                        </li>
                                    ))}
                            </ul>
                        </div>
                    )}
                </div>
                <div className="cpu8086-state">
                    <h3>Registers</h3>
                    <div className="reg-grid">
                        {WORD_REGS.map((name) => (
                            <div key={name} className="reg-item">
                                <span className="reg-name">{name}</span>
                                <span className="reg-value">{(regs[name] ?? 0).toString(16).toUpperCase().padStart(4, '0')}</span>
                            </div>
                        ))}
                    </div>
                    <h3>Flags</h3>
                    <div className="flag-grid">
                        {FLAG_NAMES.map((name) => (
                            <span key={name} className={`flag-chip ${flags[name] ? 'flag-set' : 'flag-clear'}`}>
                                {name}={flags[name] ?? 0}
                            </span>
                        ))}
                    </div>
                    <h3>Memory</h3>
                    {(() => {
                        const dump = result?.memory?.[0]
                        if (!dump) return <p className="muted">Run to snapshot memory at the offset above.</p>
                        const rows: string[] = []
                        for (let i = 0; i < dump.bytes.length; i += 8) {
                            const chunk = dump.bytes.slice(i, i + 8)
                            const addr = (dump.offset + i).toString(16).toUpperCase().padStart(4, '0')
                            rows.push(`${addr}: ${chunk.map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' ')}`)
                        }
                        return <pre className="counterexample memory-grid">{rows.join('\n')}</pre>
                    })()}
                    {(() => {
                        const dump = result?.memory?.[1]
                        if (!dump) return null
                        const sp = regs.SP ?? 0xFFFE
                        const words: string[] = []
                        for (let i = 0; i + 1 < dump.bytes.length; i += 2) {
                            const value = dump.bytes[i] | (dump.bytes[i + 1] << 8)
                            words.push(`0x${(0xFFEC + i).toString(16).toUpperCase().padStart(4, '0')}: 0x${value.toString(16).toUpperCase().padStart(4, '0')}`)
                        }
                        return (
                            <>
                                <h3>Stack window</h3>
                                <pre className="counterexample memory-grid">{words.join('\n')}</pre>
                                <p className="muted">SP = 0x{sp.toString(16).toUpperCase().padStart(4, '0')}</p>
                            </>
                        )
                    })()}

                    <h3>Trace</h3>
                    <div className="trace-scroll">
                        <table className="trace-table">
                            <thead><tr><th>step</th><th>ip</th><th>instruction</th><th>changes</th></tr></thead>
                            <tbody>
                                {trace.map((entry, i) => (
                                    <tr key={i} className={entry.kind !== 'instruction' ? 'trace-int' : ''}>
                                        <td>{entry.step}</td>
                                        <td>{entry.ip}</td>
                                        <td>
                                            {entry.kind === 'interrupt' && <span className="int-chip">INT {entry.number} ({entry.source})</span>}
                                            {entry.kind === 'iret' && <span className="int-chip">IRET</span>}
                                            {entry.kind === 'instruction' && entry.instruction}
                                        </td>
                                        <td>
                                            {Object.entries(entry.register_changes).map(([k, v]) => `${k}=${v}`).join(' ')}
                                            {Object.entries(entry.flag_changes).map(([k, v]) => ` ${k}=${v}`)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    )
}
