/**
 * TypeScript mirror of circuit JSON schema v1 (docs/semantics/circuit-graph-schema.md).
 * The Python engine is the source of truth; these types only shape the payloads.
 */

export type LogicValueStr = '0' | '1' | 'X' | 'Z'

export type ComponentType =
  | 'INPUT'
  | 'OUTPUT'
  | 'CONST0'
  | 'CONST1'
  | 'BUFFER'
  | 'NOT'
  | 'AND'
  | 'OR'
  | 'NAND'
  | 'NOR'
  | 'XOR'
  | 'XNOR'
  | 'DFF'
  | 'TFF'
  | 'JKFF'
  | 'SRFF'
  | 'REGISTER'
  | 'COUNTER'

export interface ComponentParams {
  name?: string
  width?: number
}

export interface ComponentDoc {
  id: string
  type: ComponentType
  params?: ComponentParams
  label?: string
  position?: { x: number; y: number }
}

export interface PinRefDoc {
  component: string
  pin: string
}

export interface NetDoc {
  id: string
  driver: PinRefDoc | null
  sinks: PinRefDoc[]
}

export interface CircuitDoc {
  schema_version: 1 | 2
  name?: string
  components: ComponentDoc[]
  nets: NetDoc[]
}

export interface ValidationIssue {
  code: string
  message: string
  component_id?: string | null
  net_id?: string | null
}

export interface ValidationReport {
  schema_version: number
  engine_version: string
  ok: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export interface TraceCause {
  type: 'primary_input' | 'constant' | 'gate'
  component: string
}

export interface TraceEvent {
  seq: number
  delta: number
  net: string
  old: string
  new: string
  cause: TraceCause
}

export interface SimulationResult {
  schema_version: number
  engine_version: string
  input_hash: string
  scope: string
  outputs: Record<string, string>
  event_count: number
  trace: TraceEvent[]
}

export interface TruthTableRow {
  inputs: Record<string, string>
  outputs: Record<string, string>
}

export interface TruthTableResult {
  schema_version: number
  engine_version: string
  input_hash: string
  scope: string
  input_names: string[]
  output_names: string[]
  rows: TruthTableRow[]
}

export interface HealthStatus {
  status: string
  api_version: string
  engine_version: string
}

/** detail payload of a 400 error response (docs/API.md error envelope) */
export interface ApiErrorDetail {
  code: string
  message?: string
  input?: string
  input_count?: number
  limit?: number
  errors?: ValidationIssue[]
  warnings?: ValidationIssue[]
}

/** Sequential engine result (schema v2, docs/semantics/clock-edge-rules.md). */
export interface SeqEvent {
  cycle: number
  component: string
  pin: string
  old: string
  new: string
  cause: string
}

export interface SequentialResult {
  engine_version: string
  scope: string
  input_hash: string
  cycles: { cycle: number; inputs: Record<string, string>; state: Record<string, string>; outputs: Record<string, string> }[]
  events: SeqEvent[]
  waveforms: Record<string, string[]>
  final_state: Record<string, string>
  state_components: string[]
}
