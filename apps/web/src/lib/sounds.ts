/**
 * Tiny WebAudio synth for UI feedback — no audio files, no dependencies.
 * Every sound is triggered by a user gesture (autoplay-policy safe).
 * Muted state persists in localStorage ("sparky.muted").
 */

let ctx: AudioContext | null = null

function audioContext(): AudioContext | null {
  if (isMuted()) return null
  try {
    if (ctx === null) {
      const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (Ctor === undefined) return null
      ctx = new Ctor()
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

function tone(
  freq: number,
  durationMs: number,
  type: OscillatorType,
  gain: number,
  delayMs = 0,
  slideTo?: number,
): void {
  const ac = audioContext()
  if (ac === null) return
  const start = ac.currentTime + delayMs / 1000
  const osc = ac.createOscillator()
  const amp = ac.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, start)
  if (slideTo !== undefined) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(40, slideTo), start + durationMs / 1000)
  }
  amp.gain.setValueAtTime(0.0001, start)
  amp.gain.exponentialRampToValueAtTime(gain, start + 0.012)
  amp.gain.exponentialRampToValueAtTime(0.0001, start + durationMs / 1000)
  osc.connect(amp)
  amp.connect(ac.destination)
  osc.start(start)
  osc.stop(start + durationMs / 1000 + 0.05)
}

/** Soft UI click — short, quiet, high. */
export function playClick(): void {
  tone(1180, 45, "triangle", 0.06)
}

/** Mascot attention blip — quick slide up. */
export function playPop(): void {
  tone(520, 110, "sine", 0.09, 0, 940)
}

/** Grade/exercise success — bright three-note arpeggio. */
export function playSuccess(): void {
  tone(523, 120, "triangle", 0.08)
  tone(659, 120, "triangle", 0.08, 110)
  tone(784, 180, "triangle", 0.09, 220)
}

/** Failure / error — gentle low buzz, not harsh. */
export function playError(): void {
  tone(220, 180, "sawtooth", 0.05, 0, 160)
}

/** Send message — quick two-step chirp. */
export function playSend(): void {
  tone(660, 70, "square", 0.05)
  tone(880, 70, "square", 0.05, 80)
}

/** Run finished — engine hum resolving upward. */
export function playRunDone(): void {
  tone(330, 140, "sine", 0.07, 0, 660)
}
