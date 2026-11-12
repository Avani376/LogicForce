/**
 * Sound engine v2 — a small synthesizer for UI feedback and mascot voice.
 * Pure WebAudio: oscillators + filtered noise, zero assets, zero dependencies.
 * Every call is user-gesture driven (autoplay-policy safe); muted state
 * persists in localStorage ("sparky.muted").
 */

let ctx: AudioContext | null = null
let master: GainNode | null = null
let noiseBuffer: AudioBuffer | null = null

function ensureAudio(): AudioContext | null {
  if (isMuted()) return null
  try {
    if (ctx === null) {
      const Ctor =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (Ctor === undefined) return null
      ctx = new Ctor()
      master = ctx.createGain()
      master.gain.value = 0.9
      master.connect(ctx.destination)
      // Pre-render one second of white noise for swooshes and pops.
      noiseBuffer = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate)
      const data = noiseBuffer.getChannelData(0)
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
    }
    if (ctx.state === "suspended") void ctx.resume()
    return ctx
  } catch {
    return null
  }
}

export function isMuted(): boolean {
  try {
    return localStorage.getItem("sparky.muted") === "1"
  } catch {
    return false
  }
}

export function setMuted(muted: boolean): void {
  try {
    localStorage.setItem("sparky.muted", muted ? "1" : "0")
  } catch {
    /* private mode — ignore */
  }
}

interface ToneOptions {
  freq: number
  durationMs: number
  type?: OscillatorType
  gain?: number
  delayMs?: number
  slideTo?: number
  attackMs?: number
}

function tone(opts: ToneOptions): void {
  const ac = ensureAudio()
  if (ac === null || master === null) return
  const { freq, durationMs, type = "triangle", gain = 0.08, delayMs = 0, slideTo, attackMs = 12 } = opts
  const start = ac.currentTime + delayMs / 1000
  const dur = durationMs / 1000
  const osc = ac.createOscillator()
  const amp = ac.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, start)
  if (slideTo !== undefined) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(40, slideTo), start + dur)
  }
  amp.gain.setValueAtTime(0.0001, start)
  amp.gain.exponentialRampToValueAtTime(gain, start + attackMs / 1000)
  amp.gain.exponentialRampToValueAtTime(0.0001, start + dur)
  osc.connect(amp)
  amp.connect(master)
  osc.start(start)
  osc.stop(start + dur + 0.05)
}

function noise(durationMs: number, gain: number, delayMs: number, fromHz: number, toHz: number): void {
  const ac = ensureAudio()
  if (ac === null || master === null || noiseBuffer === null) return
  const start = ac.currentTime + delayMs / 1000
  const dur = durationMs / 1000
  const src = ac.createBufferSource()
  src.buffer = noiseBuffer
  const filter = ac.createBiquadFilter()
  filter.type = "bandpass"
  filter.frequency.setValueAtTime(fromHz, start)
  filter.frequency.exponentialRampToValueAtTime(Math.max(80, toHz), start + dur)
  filter.Q.value = 1.1
  const amp = ac.createGain()
  amp.gain.setValueAtTime(0.0001, start)
  amp.gain.exponentialRampToValueAtTime(gain, start + 0.02)
  amp.gain.exponentialRampToValueAtTime(0.0001, start + dur)
  src.connect(filter)
  filter.connect(amp)
  amp.connect(master)
  src.start(start)
  src.stop(start + dur + 0.05)
}

const PENTATONIC = [523.25, 587.33, 698.46, 783.99, 932.33] // C5 D5 F5 G5 A5 — always pleasant

/** Soft UI click — short, quiet, high. */
export function playClick(): void {
  tone({ freq: 1180, durationMs: 45, type: "triangle", gain: 0.06 })
}

/** Featherweight hover tick — barely there, throttled by nature of hover. */
export function playHover(): void {
  tone({ freq: 1560, durationMs: 28, type: "sine", gain: 0.028 })
}

/** Tab whoosh — filtered noise sweep with a rising tail note. */
export function playWhoosh(): void {
  noise(180, 0.05, 0, 420, 2400)
  tone({ freq: 440, durationMs: 140, type: "sine", gain: 0.045, slideTo: 880 })
}

/** Mascot attention blip — quick slide up. */
export function playPop(): void {
  tone({ freq: 520, durationMs: 110, type: "sine", gain: 0.09, slideTo: 940 })
}

/** Chat open — two-note lift with sparkle. */
export function playOpen(): void {
  tone({ freq: 494, durationMs: 90, type: "triangle", gain: 0.07 })
  tone({ freq: 740, durationMs: 130, type: "triangle", gain: 0.07, delayMs: 80 })
  tone({ freq: 1560, durationMs: 90, type: "sine", gain: 0.03, delayMs: 130 })
}

/**
 * Animalese — Sparky "speaks": each chunk of the text becomes a short pitched
 * squeak. Deterministic per message so the same reply sounds the same twice.
 */
export function playSpeech(text: string): void {
  const chunks = text
    .replace(/[^a-zA-Z0-9 ]/g, "")
    .split(/\s+/)
    .filter((w) => w.length > 0)
    .slice(0, 14)
  chunks.forEach((word, i) => {
    const seed = [...word].reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
    const freq = PENTATONIC[seed % PENTATONIC.length] * (1 + ((seed % 3) - 1) * 0.12)
    tone({
      freq,
      durationMs: 70 + (word.length % 3) * 25,
      type: "square",
      gain: 0.035,
      delayMs: i * 74,
      slideTo: freq * 1.18,
    })
  })
}

/** Grade/exercise success — fanfare: pentatonic arpeggio + shimmer pad + pop. */
export function playSuccess(): void {
  noise(140, 0.04, 0, 1800, 5200) // sparkle riser
  const notes = [523.25, 659.25, 783.99, 1046.5]
  notes.forEach((f, i) => {
    tone({ freq: f, durationMs: 150, type: "triangle", gain: 0.085, delayMs: i * 105 })
    tone({ freq: f * 2, durationMs: 120, type: "sine", gain: 0.028, delayMs: i * 105 + 15 })
  })
  tone({ freq: 1318.5, durationMs: 420, type: "triangle", gain: 0.07, delayMs: 460 })
  tone({ freq: 1046.5, durationMs: 520, type: "sine", gain: 0.05, delayMs: 460 })
}

/** Confetti pop — noise burst + fast ascending glissando. */
export function playConfetti(): void {
  noise(120, 0.06, 0, 900, 3600)
  for (let i = 0; i < 6; i++) {
    tone({
      freq: PENTATONIC[i % PENTATONIC.length] * (i < 3 ? 1 : 2),
      durationMs: 60,
      type: "sine",
      gain: 0.04,
      delayMs: i * 55,
    })
  }
}

/** Failure / error — soft descending minor pair, never harsh. */
export function playError(): void {
  tone({ freq: 311, durationMs: 170, type: "sawtooth", gain: 0.045 })
  tone({ freq: 233, durationMs: 240, type: "sawtooth", gain: 0.04, delayMs: 150 })
}

/** Send message — quick two-step chirp. */
export function playSend(): void {
  tone({ freq: 660, durationMs: 70, type: "square", gain: 0.05 })
  tone({ freq: 880, durationMs: 70, type: "square", gain: 0.05, delayMs: 80 })
}

/** Run finished — engine hum resolving upward, machine-like double blip first. */
export function playRunDone(): void {
  tone({ freq: 220, durationMs: 60, type: "square", gain: 0.04 })
  tone({ freq: 220, durationMs: 60, type: "square", gain: 0.04, delayMs: 90 })
  tone({ freq: 330, durationMs: 200, type: "sine", gain: 0.07, delayMs: 190, slideTo: 660 })
}

/** Theme sting — plays once on workspace load. Warm, three chord tones. */
export function playThemeSting(): void {
  const chord = [261.63, 329.63, 392.0] // C major
  chord.forEach((f, i) => {
    tone({ freq: f, durationMs: 900, type: "triangle", gain: 0.05, delayMs: i * 70, attackMs: 60 })
  })
  tone({ freq: 1046.5, durationMs: 500, type: "sine", gain: 0.035, delayMs: 420 })
}
