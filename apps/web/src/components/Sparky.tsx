/**
 * Sparky — the LogicForge mascot.
 * A cute chip-bot that reacts to every interaction: blinks, bobs, celebrates
 * passes, consoles failures, guides users to the next step, and answers
 * questions via the grounded /api/assistant/ask endpoint (never invents).
 *
 * App events (any component):
 *   window.dispatchEvent(new CustomEvent('sparky:event', {
 *     detail: { mood: 'happy'|'sad'|'thinking', message: string, cta?: { label, tab } }
 *   }))
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { isMuted, playError, playPop, playSend, playSuccess, setMuted } from '../lib/sounds'

type Mood = 'idle' | 'happy' | 'sad' | 'thinking'

interface SparkyEvent {
  mood?: Mood
  message?: string
  cta?: { label: string; tab: string }
}

export function emitSparky(detail: SparkyEvent): void {
  window.dispatchEvent(new CustomEvent('sparky:event', { detail }))
}

export type WorkspaceTabName = 'circuit' | '8086' | 'verify' | 'explain' | 'learn' | 'visuals'

const TAB_TIPS: Record<WorkspaceTabName, string> = {
  circuit:
    "This is the canvas! Add an Input, drop some gates, and wire them up. Then press Simulate — I'll cheer when it works!",
  '8086':
    'Write some assembly and press ▶ Run. Watch the registers light up — try the sum loop that is already loaded!',
  verify: 'Verify an invariant here. If it fails, you get a counterexample you can replay — failures are friends!',
  explain: 'Ask for an explanation and every claim will cite real trace steps. I never make things up!',
  learn: 'Pick an exercise — a real engine grades your answer. Get it right and watch me celebrate!',
  visuals: 'Your session data comes alive here! Run a simulation or a truth table first so the charts have something true to show.',
}

const WELCOME: SparkyEvent[] = [
  { mood: 'happy', message: "Hi, I'm Sparky! ⚡ I'm LogicForge's mascot — and I never lie: every number you see comes from a real deterministic engine." },
  { mood: 'idle', message: 'Start in the Circuit tab: add an Input, drop a gate, wire it, and Simulate. Or ask me anything — click me anytime!', cta: { label: 'Go to Circuit →', tab: 'circuit' } },
]

interface ChatMessage {
  who: 'you' | 'sparky'
  text: string
  suggestions?: string[]
  tab?: string
  grounding?: 'generative' | 'grounded'
  model?: string
}

interface AskResponse {
  answer: string
  kind: string
  grounding: string
  suggestions?: string[]
  data?: { tab?: string }
}

interface ChatApiResponse extends AskResponse {
  model?: string
}

export function SparkyMascot({
  currentTab,
  onNavigate,
}: {
  currentTab: WorkspaceTabName
  onNavigate: (tab: WorkspaceTabName) => void
}): JSX.Element {
  const [mood, setMood] = useState<Mood>('idle')
  const [message, setMessage] = useState<string>(WELCOME[0].message ?? '')
  const [cta, setCta] = useState<{ label: string; tab: string } | null>(WELCOME[0].cta ?? null)
  const [tipIndex, setTipIndex] = useState(0)
  const [open, setOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [chat, setChat] = useState<ChatMessage[]>([
    { who: 'sparky', text: 'Ask me anything about LogicForge — I route answers to real engines and the lesson catalog.' },
  ])
  const [draft, setDraft] = useState('')
  const [thinking, setThinking] = useState(false)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('sparky.apiKey') ?? '')
  const [baseUrl, setBaseUrl] = useState(() => localStorage.getItem('sparky.baseUrl') ?? '')
  const [modelName, setModelName] = useState(() => localStorage.getItem('sparky.model') ?? '')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [muted, setMutedState] = useState(() => isMuted())
  const [confetti, setConfetti] = useState(0)
  const welcomeStep = useRef(0)
  const resetTimer = useRef<number | undefined>(undefined)

  // Welcome sequence on first mount.
  useEffect(() => {
    const t = window.setTimeout(() => {
      welcomeStep.current = 1
      setMessage(WELCOME[1].message ?? '')
      setCta(WELCOME[1].cta ?? null)
    }, 4200)
    return () => window.clearTimeout(t)
  }, [])

  // React to app events.
  useEffect(() => {
    const handler = (event: Event): void => {
      const detail = (event as CustomEvent<SparkyEvent>).detail ?? {}
      if (detail.mood === 'happy') setConfetti((c) => c + 1)
      if (detail.mood !== undefined) setMood(detail.mood)
      if (detail.message !== undefined) {
        setMessage(detail.message)
        setCta(detail.cta ?? null)
      }
      window.clearTimeout(resetTimer.current)
      resetTimer.current = window.setTimeout(() => setMood('idle'), 3500)
    }
    window.addEventListener('sparky:event', handler)
    return () => {
      window.removeEventListener('sparky:event', handler)
      window.clearTimeout(resetTimer.current)
    }
  }, [])

  const cycleTip = useCallback((): void => {
    if (chatOpen) {
      setChatOpen(false)
      return
    }
    setMood('happy')
    setMessage(TAB_TIPS[currentTab])
    setCta(null)
    setTipIndex((i) => i + 1)
    window.clearTimeout(resetTimer.current)
    resetTimer.current = window.setTimeout(() => setMood('idle'), 3500)
  }, [currentTab])

  const sendQuestion = useCallback(async (): Promise<void> => {
    const question = draft.trim()
    if (question === '') return
    playSend()
    setChat((c) => [...c, { who: 'you', text: question }])
    setDraft('')
    setThinking(true)
    setMood('thinking')
    const key = apiKey.trim()
    try {
      if (key !== '') {
        // Brain mode: BYOK generative answers with grounded prompting on the server.
        const response = await fetch('/api/assistant/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Assistant-Key': key },
          body: JSON.stringify({
            question,
            messages: chat.slice(-8).map((m) => ({ role: m.who === 'you' ? 'user' : 'assistant', content: m.text })),
            ...(baseUrl.trim() !== '' ? { base_url: baseUrl.trim() } : {}),
            ...(modelName.trim() !== '' ? { model: modelName.trim() } : {}),
          }),
        })
        const body = (await response.json()) as ChatApiResponse & { detail?: { message?: string } }
        if (!response.ok) {
          // Key or upstream problem — fall back to the grounded catalog so the chat never dies.
          const fallback = await fetch('/api/assistant/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
          })
          const fb = (await fallback.json()) as AskResponse & { detail?: { message?: string } }
          setChat((c) => [
            ...c,
            {
              who: 'sparky',
              text:
                `Brain mode is off right now (${body.detail?.message ?? `HTTP ${response.status}`}). ` +
                (fallback.ok ? `Grounded answer instead: ${fb.answer}` : (fb.detail?.message ?? 'No grounded answer available.')),
              grounding: 'grounded',
              suggestions: fb.suggestions,
              tab: fb.data?.tab,
            },
          ])
          setMood('sad')
          playError()
        } else {
          setChat((c) => [
            ...c,
            {
              who: 'sparky',
              text: body.answer,
              grounding: 'generative',
              model: body.model,
              suggestions: body.suggestions,
              tab: body.data?.tab,
            },
          ])
          setMood('happy')
          playSuccess()
        }
      } else {
        // Grounded mode: the deterministic router (always available).
        const response = await fetch('/api/assistant/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question }),
        })
        const body = (await response.json()) as AskResponse & { detail?: { message?: string } }
        if (!response.ok) {
          setChat((c) => [...c, { who: 'sparky', text: body.detail?.message ?? `HTTP ${response.status}` }])
          setMood('sad')
          playError()
        } else {
          setChat((c) => [
            ...c,
            {
              who: 'sparky',
              text: body.answer,
              grounding: 'grounded',
              suggestions: body.suggestions,
              tab: body.data?.tab,
            },
          ])
          setMood(body.grounding === 'engine_output' ? 'happy' : 'idle')
          playPop()
        }
      }
    } catch (cause) {
      setChat((c) => [
        ...c,
        { who: 'sparky', text: cause instanceof Error ? cause.message : String(cause) },
      ])
      setMood('sad')
      playError()
    } finally {
      setThinking(false)
      window.clearTimeout(resetTimer.current)
      resetTimer.current = window.setTimeout(() => setMood('idle'), 3500)
    }
  }, [draft, apiKey, baseUrl, modelName, chat])

  return (
    <div className="sparky-root">
      {open && (
        <div className="sparky-bubble" role="status" aria-live="polite">
          <button type="button" className="sparky-bubble-close" aria-label="Close tip"
            onClick={() => setOpen(false)}>×</button>
          <p>{message}</p>
          {cta !== null && (
            <button type="button" className="sparky-cta"
              onClick={() => { onNavigate(cta.tab as WorkspaceTabName); setOpen(false) }}>
              {cta.label}
            </button>
          )}
          <button type="button" className="sparky-cta sparky-cta-ghost"
            onClick={() => { setChatOpen(true); setOpen(false) }}>
            Ask me anything 💬
          </button>
        </div>
      )}

      {chatOpen && (
        <div className="sparky-chat" role="dialog" aria-label="Ask Sparky">
          <div className="sparky-chat-head">
            <span>Ask Sparky {apiKey.trim() !== '' ? '· brain on' : '· grounded'}</span>
            <span className="sparky-head-actions">
              <button type="button" aria-label={muted ? 'Unmute sounds' : 'Mute sounds'}
                onClick={() => { const m = !muted; setMuted(m); setMutedState(m); if (!m) playPop() }}>
                {muted ? 'M' : 'S'}
              </button>
              <button type="button" aria-label="Chat settings" onClick={() => setSettingsOpen(true)}>settings</button>
              <button type="button" aria-label="Close chat" onClick={() => setChatOpen(false)}>x</button>
            </span>
          </div>
          <div className="sparky-chat-feed">
            {chat.map((m, i) => (
              <div key={i} className={`sparky-msg sparky-msg-${m.who} sparky-msg-in`}>
                {m.grounding !== undefined && (
                  <span className={`sparky-badge sparky-badge-${m.grounding}`}>
                    {m.grounding === 'generative' ? `generative${m.model ? ` · ${m.model}` : ''}` : 'grounded'}
                  </span>
                )}
                <p>{m.text}</p>
                {m.suggestions?.map((s) => (
                  <button key={s} type="button" className="sparky-suggest"
                    onClick={() => { setDraft(s); void sendQuestion() }}>{s}</button>
                ))}
                {m.tab !== undefined && (
                  <button type="button" className="sparky-cta"
                    onClick={() => { onNavigate(m.tab as WorkspaceTabName); setChatOpen(false) }}>
                    Open the {m.tab} tab →
                  </button>
                )}
              </div>
            ))}
            {thinking && <div className="sparky-msg sparky-msg-sparky"><p className="sparky-typing">···</p></div>}
          </div>
          <div className="sparky-chat-input">
            <input
              value={draft}
              placeholder="e.g. what is a K-map?"
              aria-label="Ask Sparky a question"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void sendQuestion() }}
            />
            <button type="button" onClick={() => void sendQuestion()} disabled={thinking || draft.trim() === ''}>
              Ask
            </button>
          </div>
        </div>
      )}

      {confetti > 0 && mood === 'happy' && (
        <div className="sparky-confetti" aria-hidden="true" key={confetti}>
          {Array.from({ length: 14 }, (_, i) => (
            <span key={i} className="sparky-confetto" style={{ ['--i' as string]: String(i) }} />
          ))}
        </div>
      )}

      {settingsOpen && (
        <div className="sparky-settings" role="dialog" aria-label="Sparky brain settings">
          <div className="sparky-chat-head">
            <span>Sparky's brain</span>
            <button type="button" aria-label="Close settings" onClick={() => setSettingsOpen(false)}>x</button>
          </div>
          <div className="sparky-settings-body">
            <p className="muted">
              Paste an OpenAI-compatible API key to switch Sparky from grounded answers to
              generative ones (deep reasoning on top of the same engine facts). The key is stored
              only in this browser's localStorage and sent per-request — never stored on the server.
            </p>
            <label>
              API key
              <input type="password" value={apiKey} placeholder="sk-…" aria-label="API key"
                onChange={(e) => setApiKey(e.target.value)} />
            </label>
            <label>
              Base URL (optional — any OpenAI-compatible provider)
              <input value={baseUrl} placeholder="https://api.openai.com/v1" aria-label="Base URL"
                onChange={(e) => setBaseUrl(e.target.value)} />
            </label>
            <label>
              Model (optional)
              <input value={modelName} placeholder="gpt-4o-mini" aria-label="Model"
                onChange={(e) => setModelName(e.target.value)} />
            </label>
            <div className="sparky-settings-actions">
              <button type="button" className="sparky-cta" onClick={() => {
                localStorage.setItem('sparky.apiKey', apiKey.trim())
                localStorage.setItem('sparky.baseUrl', baseUrl.trim())
                localStorage.setItem('sparky.model', modelName.trim())
                setSettingsOpen(false)
                playSuccess()
              }}>Save brain</button>
              <button type="button" className="sparky-cta sparky-cta-ghost" onClick={() => {
                localStorage.removeItem('sparky.apiKey')
                localStorage.removeItem('sparky.baseUrl')
                localStorage.removeItem('sparky.model')
                setApiKey(''); setBaseUrl(''); setModelName('')
                setSettingsOpen(false)
              }}>Remove key</button>
            </div>
          </div>
        </div>
      )}

      <button
        type="button"
        className={`sparky-bot sparky-${mood} ${tipIndex % 2 === 1 ? 'sparky-wiggle' : ''}`}
        aria-label="Sparky the mascot — click for a tip, double-click to chat"
        onClick={() => { playPop(); setOpen((o) => !o); cycleTip() }}
        onDoubleClick={() => { setChatOpen(true); setOpen(false) }}
      >
        <svg viewBox="0 0 120 120" width="86" height="86" aria-hidden="true">
          {/* antenna */}
          <line x1="60" y1="26" x2="60" y2="12" stroke="#5b6ee1" strokeWidth="4" strokeLinecap="round" />
          <circle className="sparky-antenna" cx="60" cy="9" r="6" fill="#ffd166" />
          {/* body (chip) */}
          <rect x="24" y="26" width="72" height="64" rx="16" fill="#5b6ee1" />
          <rect x="32" y="34" width="56" height="48" rx="12" fill="#eef1ff" />
          {/* chip legs */}
          <g stroke="#5b6ee1" strokeWidth="5" strokeLinecap="round">
            <line x1="40" y1="90" x2="40" y2="98" />
            <line x1="60" y1="90" x2="60" y2="98" />
            <line x1="80" y1="90" x2="80" y2="98" />
          </g>
          {/* eyes: mood-driven */}
          {mood === 'happy' ? (
            <g stroke="#2d3561" strokeWidth="4" strokeLinecap="round" fill="none">
              <path d="M 42 54 q 6 -8 12 0" />
              <path d="M 66 54 q 6 -8 12 0" />
            </g>
          ) : mood === 'sad' ? (
            <g fill="#2d3561">
              <circle cx="48" cy="56" r="4.5" />
              <circle cx="72" cy="56" r="4.5" />
              <path d="M 50 68 q 10 -6 20 0" stroke="#2d3561" strokeWidth="3.5" fill="none" strokeLinecap="round" />
            </g>
          ) : (
            <g className="sparky-eyes">
              <circle cx="48" cy="54" r="6" fill="#2d3561" />
              <circle cx="72" cy="54" r="6" fill="#2d3561" />
              <circle cx="50" cy="52" r="2" fill="#ffffff" />
              <circle cx="74" cy="52" r="2" fill="#ffffff" />
            </g>
          )}
          {/* mouth */}
          {mood === 'happy' && <path d="M 50 66 q 10 10 20 0" stroke="#2d3561" strokeWidth="3.5" fill="none" strokeLinecap="round" />}
          {mood === 'thinking' && <circle cx="60" cy="68" r="3.5" fill="#2d3561" />}
          {mood === 'idle' && <path d="M 52 68 q 8 6 16 0" stroke="#2d3561" strokeWidth="3.5" fill="none" strokeLinecap="round" />}
          {mood === 'sad' && <path d="M 52 70 q 8 -5 16 0" stroke="#2d3561" strokeWidth="3.5" fill="none" strokeLinecap="round" />}
          {/* cheeks */}
          <circle cx="38" cy="62" r="3" fill="#ffb3c1" opacity="0.8" />
          <circle cx="82" cy="62" r="3" fill="#ffb3c1" opacity="0.8" />
        </svg>
      </button>

      <button type="button" className="sparky-chat-fab" aria-label="Open chat with Sparky"
        onClick={() => { setChatOpen(true); setOpen(false) }}>💬</button>
    </div>
  )
}
