"""Phase 4 patch: debugger upgrade in Cpu8086Panel (breakpoints, memory + stack viewer, loading states).

Run: .venv/Scripts/python scripts/patch_debugger.py  (idempotency by asserts)
"""
from __future__ import annotations

import io

p = "apps/web/src/components/Cpu8086Panel.tsx"
s = io.open(p, encoding="utf-8").read()
n = 0


def rep(old: str, new: str) -> None:
    global s, n
    assert old in s, f"missing: {old[:70]!r}"
    s = s.replace(old, new, 1)
    n += 1


# 1. memory dump type + RunResult extension
rep(
    """interface PicResult {""",
    """interface MemoryDump {
    segment: number
    offset: number
    bytes: number[]
}

interface PicResult {""",
)

rep(
    """interface RunResult {
    stop_reason: string
    registers: Record<string, number>
    flags: Record<string, number>
    trace: TraceEntry[]
}""",
    """interface RunResult {
    stop_reason: string
    registers: Record<string, number>
    flags: Record<string, number>
    trace: TraceEntry[]
    memory?: MemoryDump[]
}""",
)

# 2. state: breakpoints, memory regions, running flag
rep(
    """    const [picError, setPicError] = useState<string | null>(null)""",
    """    const [picError, setPicError] = useState<string | null>(null)
    const [running, setRunning] = useState(false)
    const [breakpointsText, setBreakpointsText] = useState('')
    const [memSegment, setMemSegment] = useState(0)
    const [memOffset, setMemOffset] = useState(0x300)
    const [memLength, setMemLength] = useState(16)""",
)

# 3. run(): parse breakpoints + request memory dumps + loading state
rep(
    """    const run = useCallback(async (): Promise<void> => {
        setError(null)
        try {
            const response = await fetch('/api/8086/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source, max_steps: maxSteps, breakpoints: [] }),
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
        }
    }, [source, maxSteps])""",
    """    const parseBreakpoints = useCallback((): number[] => {
        return breakpointsText
            .split(/[\\s,]+/)
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
                        { segment: memSegment, offset: memOffset, length: memLength },
                        { segment: 0, offset: 0xFFEC, length: 16 }, // stack window near SP
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
            setMemSegment((seg) => seg)
        }
    }, [source, maxSteps, parseBreakpoints, memSegment, memOffset, memLength])""",
)

# 4. debugger controls UI: breakpoints + memory region inputs
rep(
    """                    <div className="cpu8086-controls">
                        <label>
                            max_steps: <input type="number" value={maxSteps} min={1} max={100000}
                                onChange={(e) => setMaxSteps(Number(e.target.value) || 200)} />
                        </label>
                        <button type="button" onClick={() => void run()}>▶ Run</button>
                    </div>""",
    """                    <div className="cpu8086-controls">
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
                            memory: <input value={`0x${memSegment.toString(16)}:${memOffset.toString(16)}`} readOnly />
                        </label>
                        <label>
                            length: <input type="number" value={memLength} min={1} max={256}
                                aria-label="Memory dump length"
                                onChange={(e) => setMemLength(Number(e.target.value) || 16)} />
                        </label>
                    </div>""",
)

# 5. memory + stack grid in the state column, after flags
rep(
    """                    <h3>Trace</h3>""",
    """                    <h3>Memory</h3>
                    {(() => {
                        const dump = result?.memory?.[0]
                        if (!dump) return <p className="muted">Run to snapshot memory (segment 0, offset set above).</p>
                        const rows: string[] = []
                        for (let i = 0; i < dump.bytes.length; i += 8) {
                            const chunk = dump.bytes.slice(i, i + 8)
                            const addr = (dump.offset + i).toString(16).toUpperCase().padStart(4, '0')
                            rows.push(`${addr}: ${chunk.map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' ')}`)
                        }
                        return <pre className="counterexample memory-grid">{rows.join('\\n')}</pre>
                    })()}
                    {(() => {
                        const regs = result?.registers ?? {}
                        const sp = regs.SP ?? 0xFFFE
                        const dump = result?.memory?.[1]
                        if (!dump) return null
                        const words: string[] = []
                        for (let i = 0; i + 1 < dump.bytes.length; i += 2) {
                            const value = dump.bytes[i] | (dump.bytes[i + 1] << 8)
                            words.push(`0x${(sp + i).toString(16).toUpperCase().padStart(4, '0')}: 0x${value.toString(16).toUpperCase().padStart(4, '0')}`)
                        }
                        return (
                            <>
                                <h3>Stack at SS:SP</h3>
                                <pre className="counterexample memory-grid">{words.join('\\n')}</pre>
                            </>
                        )
                    })()}

                    <h3>Trace</h3>""",
)

io.open(p, encoding="utf-8").read()
n = 0


def rep(old: str, new: str) -> None:
    global s, n
    assert old in s, f"missing: {old[:70]!r}"
    s = s.replace(old, new, 1)
    n += 1


# 1. memory dump type + RunResult extension
rep(
    """interface PicResult {""",
    """interface MemoryDump {
    segment: number
    offset: number
    bytes: number[]
}

interface PicResult {""",
)

rep(
    """interface RunResult {
    stop_reason: string
    registers: Record<string, number>
    flags: Record<string, number>
    trace: TraceEntry[]
}""",
    """interface RunResult {
    stop_reason: string
    registers: Record<string, number>
    flags: Record<string, number>
    trace: TraceEntry[]
    memory?: MemoryDump[]
}""",
)

# 2. state: breakpoints, memory regions, running flag
rep(
    """    const [picError, setPicError] = useState<string | null>(null)""",
    """    const [picError, setPicError] = useState<string | null>(null)
    const [running, setRunning] = useState(false)
    const [breakpointsText, setBreakpointsText] = useState('')
    const [memSegment, setMemSegment] = useState(0)
    const [memOffset, setMemOffset] = useState(0x300)
    const [memLength, setMemLength] = useState(16)""",
)

# 3. run(): parse breakpoints + request memory dumps + loading state
rep(
    """    const run = useCallback(async (): Promise<void> => {
        setError(null)
        try {
            const response = await fetch('/api/8086/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source, max_steps: maxSteps, breakpoints: [] }),
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
        }
    }, [source, maxSteps])""",
    """    const parseBreakpoints = useCallback((): number[] => {
        return breakpointsText
            .split(/[\\s,]+/)
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
                        { segment: memSegment, offset: memOffset, length: memLength },
                        { segment: 0, offset: 0xFFEC, length: 16 }, // stack window near SP
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
            setMemSegment((seg) => seg)
        }
    }, [source, maxSteps, parseBreakpoints, memSegment, memOffset, memLength])""",
)

# 4. debugger controls UI: breakpoints + memory region inputs
rep(
    """                    <div className="cpu8086-controls">
                        <label>
                            max_steps: <input type="number" value={maxSteps} min={1} max={100000}
                                onChange={(e) => setMaxSteps(Number(e.target.value) || 200)} />
                        </label>
                        <button type="button" onClick={() => void run()}>▶ Run</button>
                    </div>""",
    """                    <div className="cpu8086-controls">
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
                            memory: <input value={`0x${memSegment.toString(16)}:${memOffset.toString(16)}`} readOnly />
                        </label>
                        <label>
                            length: <input type="number" value={memLength} min={1} max={256}
                                aria-label="Memory dump length"
                                onChange={(e) => setMemLength(Number(e.target.value) || 16)} />
                        </label>
                    </div>""",
)

# 5. memory + stack grid in the state column, after flags
rep(
    """                    <h3>Trace</h3>""",
    """                    <h3>Memory</h3>
                    {(() => {
                        const dump = result?.memory?.[0]
                        if (!dump) return <p className="muted">Run to snapshot memory (segment 0, offset set above).</p>
                        const rows: string[] = []
                        for (let i = 0; i < dump.bytes.length; i += 8) {
                            const chunk = dump.bytes.slice(i, i + 8)
                            const addr = (dump.offset + i).toString(16).toUpperCase().padStart(4, '0')
                            rows.push(`${addr}: ${chunk.map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' ')}`)
                        }
                        return <pre className="counterexample memory-grid">{rows.join('\\n')}</pre>
                    })()}
                    {(() => {
                        const regs = result?.registers ?? {}
                        const sp = regs.SP ?? 0xFFFE
                        const dump = result?.memory?.[1]
                        if (!dump) return null
                        const words: string[] = []
                        for (let i = 0; i + 1 < dump.bytes.length; i += 2) {
                            const value = dump.bytes[i] | (dump.bytes[i + 1] << 8)
                            words.push(`0x${(sp + i).toString(16).toUpperCase().padStart(4, '0')}: 0x${value.toString(16).toUpperCase().padStart(4, '0')}`)
                        }
                        return (
                            <>
                                <h3>Stack at SS:SP</h3>
                                <pre className="counterexample memory-grid">{words.join('\\n')}</pre>
                            </>
                        )
                    })()}

                    <h3>Trace</h3>""",
)

# 6. run button label respects running state (Run → disabled while running)
rep(
    """                        <button type="button" onClick={() => void run()}>▶ Run</button>""",
    """                        <button type="button" onClick={() => void run()} disabled={running}>{running ? 'Running…' : '▶ Run'}</button>""",
)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print(f"Cpu8086Panel patched: {n}")
