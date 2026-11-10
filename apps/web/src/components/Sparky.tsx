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
}

interface AskResponse {
  answer: string
  kind: string
  grounding: string
  suggestions?: string[]
  data?: { tab?: string }
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
    setChat((c) => [...c, { who: 'you', text: question }])
    setDraft('')
    setThinking(true)
    setMood('thinking')
    try {
      const response = await fetch('/api/assistant/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const body = (await response.json()) as AskResponse & { detail?: { message?: string } }
      if (!response.ok) {
        setChat((c) => [...c, { who: 'sparky', text: body.detail?.message ?? `HTTP ${response.status}` }])
        setMood('sad')
      } else {
        setChat((c) => [
          ...c,
          {
            who: 'sparky',
            text: body.answer,
            suggestions: body.suggestions,
            tab: body.data?.tab,
          },
        ])
        setMood(body.grounding === 'engine_output' ? 'happy' : 'idle')
      }
    } catch (cause) {
      setChat((c) => [
        ...c,
        { who: 'sparky', text: cause instanceof Error ? cause.message : String(cause) },
      ])
      setMood('sad')
    } finally {
      setThinking(false)
      window.clearTimeout(resetTimer.current)
      resetTimer.current = window.setTimeout(() => setMood('idle'), 3500)
    }
  }, [draft])

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
            <span>Ask Sparky</span>
            <button type="button" aria-label="Close chat" onClick={() => setChatOpen(false)}>×</button>
          </div>
          <div className="sparky-chat-feed">
            {chat.map((m, i) => (
              <div key={i} className={`sparky-msg sparky-msg-${m.who}`}>
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

      <button
        type="button"
        className={`sparky-bot sparky-${mood} ${tipIndex % 2 === 1 ? 'sparky-wiggle' : ''}`}
        aria-label="Sparky the mascot — click for a tip, double-click to chat"
        onClick={() => { setOpen((o) => !o); cycleTip() }}
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
