"""One-shot patch: upgrade Sparky with the brain (BYOK chat), sounds, confetti.

Run from repo root:  .venv/Scripts/python scripts/patch_sparky_brain.py
Idempotency: asserts anchors; a re-run fails loudly rather than double-applying.
"""
from __future__ import annotations

import io

p = "apps/web/src/components/Sparky.tsx"
s = io.open(p, encoding="utf-8").read()
changed = 0


def rep(old: str, new: str) -> None:
    global s, changed
    assert old in s, f"anchor missing: {old[:70]!r}"
    s = s.replace(old, new, 1)
    changed += 1


rep(
    "import { useCallback, useEffect, useRef, useState } from 'react'",
    "import { useCallback, useEffect, useRef, useState } from 'react'\n\n"
    "import { isMuted, playClick, playError, playPop, playSend, playSuccess, setMuted } from '../lib/sounds'",
)

rep(
    """interface ChatMessage {
  who: 'you' | 'sparky'
  text: string
  suggestions?: string[]
  tab?: string
}""",
    """interface ChatMessage {
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
}""",
)

rep(
    """interface AskResponse {
  answer: string
  kind: string
  grounding: string
  suggestions?: string[]
  data?: { tab?: string }
}

export function SparkyMascot""",
    "export function SparkyMascot",
)

rep(
    """  const [draft, setDraft] = useState('')
  const [thinking, setThinking] = useState(false)""",
    """  const [draft, setDraft] = useState('')
  const [thinking, setThinking] = useState(false)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('sparky.apiKey') ?? '')
  const [baseUrl, setBaseUrl] = useState(() => localStorage.getItem('sparky.baseUrl') ?? '')
  const [modelName, setModelName] = useState(() => localStorage.getItem('sparky.model') ?? '')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [muted, setMutedState] = useState(() => isMuted())
  const [confetti, setConfetti] = useState(0)""",
)

rep(
    """    const handler = (event: Event): void => {
      const detail = (event as CustomEvent<SparkyEvent>).detail ?? {}
      if (detail.mood !== undefined) setMood(detail.mood)""",
    """    const handler = (event: Event): void => {
      const detail = (event as CustomEvent<SparkyEvent>).detail ?? {}
      if (detail.mood === 'happy') setConfetti((c) => c + 1)
      if (detail.mood !== undefined) setMood(detail.mood)""",
)

old_send = """  const sendQuestion = useCallback(async (): Promise<void> => {
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
  }, [draft])"""

new_send = """  const sendQuestion = useCallback(async (): Promise<void> => {
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
  }, [draft, apiKey, baseUrl, modelName, chat])"""
rep(old_send, new_send)

rep(
    """          <div className="sparky-chat-head">
            <span>Ask Sparky</span>
            <button type="button" aria-label="Close chat" onClick={() => setChatOpen(false)}>×</button>
          </div>""",
    """          <div className="sparky-chat-head">
            <span>Ask Sparky {apiKey.trim() !== '' ? '· brain on' : '· grounded'}</span>
            <span className="sparky-head-actions">
              <button type="button" aria-label={muted ? 'Unmute sounds' : 'Mute sounds'}
                onClick={() => { const m = !muted; setMuted(m); setMutedState(m); if (!m) playPop() }}>
                {muted ? 'M' : 'S'}
              </button>
              <button type="button" aria-label="Chat settings" onClick={() => setSettingsOpen(true)}>settings</button>
              <button type="button" aria-label="Close chat" onClick={() => setChatOpen(false)}>x</button>
            </span>
          </div>""",
)

rep(
    """              <div key={i} className={`sparky-msg sparky-msg-${m.who}`}>
                <p>{m.text}</p>""",
    """              <div key={i} className={`sparky-msg sparky-msg-${m.who} sparky-msg-in`}>
                {m.grounding !== undefined && (
                  <span className={`sparky-badge sparky-badge-${m.grounding}`}>
                    {m.grounding === 'generative' ? `generative${m.model ? ` · ${m.model}` : ''}` : 'grounded'}
                  </span>
                )}
                <p>{m.text}</p>""",
)

rep(
    """      <button
        type="button"
        className={`sparky-bot sparky-${mood} ${tipIndex % 2 === 1 ? 'sparky-wiggle' : ''}`}""",
    """      {confetti > 0 && mood === 'happy' && (
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
        className={`sparky-bot sparky-${mood} ${tipIndex % 2 === 1 ? 'sparky-wiggle' : ''}`}""",
)

rep(
    """        onClick={() => { setOpen((o) => !o); cycleTip() }}""",
    """        onClick={() => { playPop(); setOpen((o) => !o); cycleTip() }}""",
)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print(f"Sparky upgraded: {changed} patches applied")
