/**
 * Typed fetch wrappers around the LogicForge API.
 * The API (and behind it, the Python engine) is the single source of truth —
 * this module never computes simulation results locally.
 */

import type {
  ApiErrorDetail,
  CircuitDoc,
  HealthStatus,
  SequentialResult,
  SimulationResult,
  TruthTableResult,
  ValidationReport,
} from '../types'

export class ApiHttpError extends Error {
  readonly status: number
  readonly detail: ApiErrorDetail

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail.message ?? detail.code)
    this.status = status
    this.detail = detail
  }
}

export class ApiUnreachableError extends Error {
  constructor(cause: unknown) {
    super('LogicForge API is unreachable. Start it with: uvicorn logicforge_api.main:app --port 8000')
    this.cause = cause
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (cause) {
    throw new ApiUnreachableError(cause)
  }
  if (!response.ok) {
    let detail: ApiErrorDetail = { code: 'UNKNOWN_ERROR' }
    try {
      const payload = (await response.json()) as { detail?: ApiErrorDetail }
      if (payload.detail !== undefined && payload.detail !== null) {
        detail = payload.detail
      }
    } catch {
      // keep default detail — the status code is still surfaced
    }
    throw new ApiHttpError(response.status, detail)
  }
  return (await response.json()) as T
}

export async function apiHealth(): Promise<HealthStatus> {
  try {
    const response = await fetch('/api/health')
    if (!response.ok) {
      throw new ApiHttpError(response.status, { code: 'HEALTH_FAILED' })
    }
    return (await response.json()) as HealthStatus
  } catch (cause) {
    if (cause instanceof ApiHttpError) throw cause
    throw new ApiUnreachableError(cause)
  }
}

export function apiValidate(circuit: CircuitDoc): Promise<ValidationReport> {
  return postJson('/api/circuits/validate', { circuit })
}

export function apiSimulate(
  circuit: CircuitDoc,
  inputs: Record<string, string>,
): Promise<SimulationResult> {
  return postJson('/api/circuits/simulate', { circuit, inputs })
}

export function apiTruthTable(circuit: CircuitDoc): Promise<TruthTableResult> {
  return postJson('/api/circuits/truth-table', { circuit })
}

export function apiSimulateSequential(
  circuit: CircuitDoc,
  cycles: number,
  inputsPerCycle: Record<string, string>[],
): Promise<SequentialResult> {
  return postJson('/api/sequential/simulate', {
    circuit,
    cycles,
    inputs_per_cycle: inputsPerCycle,
  })
}
