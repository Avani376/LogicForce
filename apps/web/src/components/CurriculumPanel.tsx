/**
 * Curriculum panel ("Learn" tab): lessons and engine-graded exercises.
 * Talks to /api/curriculum/* — grading happens in the engines, never here.
 */

import { useCallback, useEffect, useState } from 'react'

import { playError, playSuccess } from '../lib/sounds'
import { emitSparky } from './Sparky'

interface LessonSummary {
  id: string
  unit: string
  title: string
  summary: string
  key_points: string[]
  related_exercise_ids: string[]
}

interface ExerciseSummary {
  id: string
  lesson_id: string
  kind: string
  prompt: string
  hint: string
  answer_kind: string
}

interface GradedResult {
  exercise_id: string
  passed: boolean
  scope: string
  feedback: string
  evidence: string[]
}

interface CurriculumPanelProps {
  onNotify?: (message: string) => void
}

export function CurriculumPanel({ onNotify }: CurriculumPanelProps): JSX.Element {
  const [lessons, setLessons] = useState<LessonSummary[]>([])
  const [exercises, setExercises] = useState<ExerciseSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [submission, setSubmission] = useState('')
  const [result, setResult] = useState<GradedResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [grading, setGrading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async (): Promise<void> => {
      try {
        const [lessonsRes, exercisesRes] = await Promise.all([
          fetch('/api/curriculum/lessons'),
          fetch('/api/curriculum/exercises'),
        ])
        if (!lessonsRes.ok || !exercisesRes.ok) {
          throw new Error(`HTTP ${lessonsRes.status}/${exercisesRes.status}`)
        }
        const lessonsBody = (await lessonsRes.json()) as { lessons: LessonSummary[] }
        const exercisesBody = (await exercisesRes.json()) as { exercises: ExerciseSummary[] }
        if (!cancelled) {
          setLessons(lessonsBody.lessons)
          setExercises(exercisesBody.exercises)
          if (exercisesBody.exercises.length > 0) setSelectedId(exercisesBody.exercises[0].id)
        }
      } catch (cause) {
        if (!cancelled) {
          setLoadError(cause instanceof Error ? cause.message : String(cause))
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const selected = exercises.find((e) => e.id === selectedId) ?? null

  const submit = useCallback(async (): Promise<void> => {
    if (selected === null || submission.trim() === '') return
    setGrading(true)
    setError(null)
    setResult(null)
    try {
      const response = await fetch('/api/curriculum/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exercise_id: selected.id, submission }),
      })
      const body = await response.json()
      if (!response.ok) {
        setError(body.detail?.message ?? `HTTP ${response.status}`)
        return
      }
      setResult(body as GradedResult)
      if (body.passed) playSuccess(); else playError()
      emitSparky(
        body.passed
          ? { mood: 'happy', message: 'Brilliant! A real engine just verified your answer — you earned that bounce! 🎉' }
          : { mood: 'sad', message: "Not yet — but the engine told you exactly why. Read the evidence and try again, I'm rooting for you!" }
      )
      if (onNotify !== undefined) {
        onNotify(body.passed ? 'Exercise passed — graded by the engine.' : 'Not yet — see the engine feedback.')
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setGrading(false)
    }
  }, [selected, submission, onNotify])

  if (loadError !== null) {
    return (
      <section className="panel" aria-label="Curriculum">
        <div className="banner banner-error" role="alert">
          Curriculum catalog unavailable: {loadError}. Start the API to load lessons.
        </div>
      </section>
    )
  }

  return (
    <div className="workspace" aria-label="Curriculum workspace">
      <section className="panel" aria-label="Lessons">
        <h2>Lessons</h2>
        {lessons.map((lesson) => (
          <div key={lesson.id}>
            <h3>
              Unit {lesson.unit} · {lesson.title}
            </h3>
            <p className="muted">{lesson.summary}</p>
            <ul className="issue-list">
              {lesson.key_points.map((point) => (
                <li key={point} className="issue">{point}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="panel" aria-label="Exercises">
        <h2>Exercises</h2>
        <div className="issue-list">
          {exercises.map((exercise) => (
            <button
              key={exercise.id}
              type="button"
              className={`tab-btn ${selectedId === exercise.id ? 'tab-active' : ''}`}
              onClick={() => {
                setSelectedId(exercise.id)
                setResult(null)
                setError(null)
                setSubmission('')
              }}
            >
              {exercise.id} ({exercise.kind})
            </button>
          ))}
        </div>

        {selected !== null && (
          <>
            <p>{selected.prompt}</p>
            <p className="muted">Hint: {selected.hint}</p>
            <label className="visually-hidden" htmlFor="curriculum-submission">Your answer</label>
            <textarea
              id="curriculum-submission"
              className="asm-editor"
              rows={3}
              value={submission}
              onChange={(e) => setSubmission(e.target.value)}
              placeholder={
                selected.answer_kind === 'expression'
                  ? 'e.g. !A & (B | C)'
                  : selected.answer_kind === 'binary'
                    ? 'e.g. 11110011'
                    : 'e.g. 47 or 0x2F'
              }
            />
            <button type="button" onClick={() => void submit()} disabled={grading || submission.trim() === ''}>
              {grading ? 'Grading…' : 'Grade with engine'}
            </button>
          </>
        )}

        {error !== null && <div className="banner banner-error" role="alert">{error}</div>}
        {result !== null && (
          <div className="counterexample" aria-live="polite">
            <p>
              <strong>{result.passed ? 'PASS' : 'NOT YET'}</strong> · scope {result.scope}
            </p>
            <p>{result.feedback}</p>
            <ul className="issue-list">
              {result.evidence.map((line) => (
                <li key={line} className="issue">{line}</li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
