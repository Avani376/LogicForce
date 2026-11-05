/**
 * Editor state model and pure transformations (circuit-building rules).
 *
 * The editor keeps one net per input pin (rewiring replaces the old feed) and one
 * driver per net, mirroring schema v1 so the engine's strict validation always passes
 * for well-formed edits. All functions here are pure; App owns state and history.
 */

import type {
  CircuitDoc,
  ComponentDoc,
  ComponentType,
  NetDoc,
  PinRefDoc,
} from '../types'

export interface EditorComponent {
  id: string
  type: ComponentType
  x: number
  y: number
  /** primary I/O display name (INPUT/OUTPUT only) */
  ioName?: string
  /** gate width (multi-input gates only) */
  width?: number
  label?: string
}

export interface EditorNet {
  id: string
  driver: PinRefDoc
  sinks: PinRefDoc[]
}

export interface EditorState {
  name: string
  components: EditorComponent[]
  nets: EditorNet[]
  /** primary input values, keyed by ioName */
  inputValues: Record<string, '0' | '1' | 'X'>
  nextAutoId: number
}

export const GATE_TYPES: ComponentType[] = [
  'AND',
  'OR',
  'NOT',
  'NAND',
  'NOR',
  'XOR',
  'XNOR',
  'BUFFER',
]

export function isMultiInput(type: ComponentType): boolean {
  return ['AND', 'OR', 'NAND', 'NOR', 'XOR', 'XNOR'].includes(type)
}

export function gateWidth(type: ComponentType, component: EditorComponent | undefined): number {
  if (!isMultiInput(type)) return 1
  return Math.max(2, component?.width ?? 2)
}

/** Input pin names for a component ('a', 'b', ... per width). */
export function inputPins(component: EditorComponent): string[] {
  if (component.type === 'OUTPUT') return ['in']
  if (!isMultiInput(component.type)) return ['a']
  return Array.from({ length: gateWidth(component.type, component) }, (_, i) =>
    String.fromCharCode(97 + i),
  )
}

export function hasOutputPin(type: ComponentType): boolean {
  return type !== 'OUTPUT'
}

export function emptyState(): EditorState {
  return {
    name: 'untitled',
    components: [],
    nets: [],
    inputValues: {},
    nextAutoId: 1,
  }
}

function findComponent(state: EditorState, id: string): EditorComponent | undefined {
  return state.components.find((c) => c.id === id)
}

/** Next letter for a primary input name (a..z, then a2, b2...). */
function nextIoName(state: EditorState, kind: 'INPUT' | 'OUTPUT'): string {
  const used = new Set(
    state.components
      .filter((c) => (kind === 'INPUT' ? c.type === 'INPUT' : c.type === 'OUTPUT'))
      .map((c) => c.ioName ?? ''),
  )
  if (kind === 'INPUT') {
    for (let round = 0; round < 26; round += 1) {
      for (let i = 0; i < 26; i += 1) {
        const candidate = round === 0 ? String.fromCharCode(97 + i) : `${String.fromCharCode(97 + i)}${round + 1}`
        if (!used.has(candidate)) return candidate
      }
    }
    return 'a'
  }
  for (let i = 1; i < 999; i += 1) {
    if (!used.has(`y${i}`)) return `y${i}`
  }
  return 'y'
}

export function addComponent(
  state: EditorState,
  type: ComponentType,
  x: number,
  y: number,
): EditorState {
  const id = `C${state.nextAutoId}`
  const component: EditorComponent = { id, type, x, y }
  if (type === 'INPUT' || type === 'OUTPUT') {
    component.ioName = nextIoName(state, type)
  }
  const inputValues = { ...state.inputValues }
  if (type === 'INPUT' && component.ioName) inputValues[component.ioName] = '0'
  return {
    ...state,
    components: [...state.components, component],
    inputValues,
    nextAutoId: state.nextAutoId + 1,
  }
}

export function moveComponent(state: EditorState, id: string, x: number, y: number): EditorState {
  return {
    ...state,
    components: state.components.map((c) => (c.id === id ? { ...c, x, y } : c)),
  }
}

export function deleteComponent(state: EditorState, id: string): EditorState {
  const alive = new Set(
    state.components.filter((c) => c.id !== id).map((c) => c.id),
  )
  const nets = state.nets
    .filter((net) => alive.has(net.driver.component))
    .map((net) => ({
      ...net,
      sinks: net.sinks.filter((s) => alive.has(s.component)),
    }))
    .filter((net) => net.sinks.length > 0)
  return {
    ...state,
    components: state.components.filter((c) => c.id !== id),
    nets,
  }
}

/** Rewire-safe connect: ensures the target input pin is fed by exactly one net. */
export function connectPins(
  state: EditorState,
  from: PinRefDoc,
  to: PinRefDoc,
): { state: EditorState; message: string } {
  const fromComp = findComponent(state, from.component)
  const toComp = findComponent(state, to.component)
  if (!fromComp || !toComp) {
    return { state, message: 'Unknown pin' }
  }
  const fromIsOutput = hasOutputPin(fromComp.type) && from.pin === 'out'
  const toIsInput =
    (toComp.type === 'OUTPUT' && to.pin === 'in') ||
    inputPins(toComp).includes(to.pin)

  let driver: PinRefDoc
  let sink: PinRefDoc
  if (fromIsOutput && toIsInput) {
    driver = from
    sink = to
  } else if (!fromIsOutput && toIsInput) {
    // clicked an input first — only valid if the second click is an output
    return { state, message: 'Select an output pin to start a wire' }
  } else if (fromIsOutput && !toIsInput) {
    return { state, message: 'Connect an output pin to an input pin' }
  } else {
    // both inputs — invalid
    return { state, message: 'Connect an output pin to an input pin' }
  }

  if (driver.component === sink.component) {
    return { state, message: 'Cannot connect a component to itself' }
  }

  // Remove any existing feed of the target input pin (rewire semantics).
  const nets: EditorNet[] = state.nets
    .map((net) => ({
      ...net,
      sinks: net.sinks.filter(
        (s) => !(s.component === sink.component && s.pin === sink.pin),
      ),
    }))
    .filter((net) => net.sinks.length > 0)

  const existing = nets.find(
    (net) => net.driver.component === driver.component && net.driver.pin === driver.pin,
  )
  if (existing) {
    existing.sinks = [...existing.sinks, sink]
    return { state: { ...state, nets: nets.map((n) => ({ ...n })) }, message: 'Connected' }
  }
  const netId = `w${state.nextAutoId}_from_${driver.component}`
  return {
    state: {
      ...state,
      nets: [...nets, { id: netId, driver, sinks: [sink] }],
      nextAutoId: state.nextAutoId + 1,
    },
    message: 'Connected',
  }
}

export function deleteNet(state: EditorState, netId: string): EditorState {
  return { ...state, nets: state.nets.filter((n) => n.id !== netId) }
}

const VALUE_CYCLE: Record<'0' | '1' | 'X', '0' | '1' | 'X'> = {
  '0': '1',
  '1': 'X',
  X: '0',
}

export function toggleInput(state: EditorState, ioName: string): EditorState {
  const current = state.inputValues[ioName] ?? 'X'
  return {
    ...state,
    inputValues: { ...state.inputValues, [ioName]: VALUE_CYCLE[current] },
  }
}

/** Serialize editor state into schema-v1 document for the engine. */
export function toDoc(state: EditorState): CircuitDoc {
  const components: ComponentDoc[] = state.components.map((c) => {
    const doc: ComponentDoc = {
      id: c.id,
      type: c.type,
      position: { x: Math.round(c.x), y: Math.round(c.y) },
    }
    if (c.ioName !== undefined) doc.params = { name: c.ioName }
    if (isMultiInput(c.type) && gateWidth(c.type, c) !== 2) {
      doc.params = { ...(doc.params ?? {}), width: gateWidth(c.type, c) }
    }
    if (c.label !== undefined) doc.label = c.label
    return doc
  })
  const nets: NetDoc[] = state.nets.map((n) => ({
    id: n.id,
    driver: { component: n.driver.component, pin: n.driver.pin },
    sinks: n.sinks.map((s) => ({ component: s.component, pin: s.pin })),
  }))
  return {
    schema_version: 1,
    name: state.name,
    components,
    nets,
  }
}

/** Load a schema-v1 document (save file) back into editor state. */
export function fromDoc(doc: CircuitDoc): EditorState | string {
  if (doc?.schema_version !== 1 || !Array.isArray(doc.components) || !Array.isArray(doc.nets)) {
    return 'Not a LogicForge schema-v1 circuit document'
  }
  const components: EditorComponent[] = doc.components.map((c, index) => ({
    id: c.id,
    type: c.type,
    x: c.position?.x ?? 80 + (index % 6) * 150,
    y: c.position?.y ?? 80 + Math.floor(index / 6) * 110,
    ioName: c.params?.name,
    width: c.params?.width,
    label: c.label,
  }))
  const nets: EditorNet[] = []
  for (const n of doc.nets) {
    if (n.driver === null) continue
    nets.push({
      id: n.id,
      driver: { component: n.driver.component, pin: n.driver.pin },
      sinks: n.sinks.map((s) => ({ component: s.component, pin: s.pin })),
    })
  }
  const inputValues: Record<string, '0' | '1' | 'X'> = {}
  for (const c of components) {
    if (c.type === 'INPUT' && c.ioName) inputValues[c.ioName] = '0'
  }
  const maxAuto = components
    .map((c) => Number.parseInt(c.id.replace(/^C/, ''), 10))
    .filter((n) => Number.isFinite(n))
  return {
    name: doc.name ?? 'untitled',
    components,
    nets,
    inputValues,
    nextAutoId: (maxAuto.length > 0 ? Math.max(...maxAuto) : 0) + 1,
  }
}

/** Reference example: half adder, mirroring tests/golden/fixtures/half_adder.json. */
export function halfAdderExample(): EditorState {
  const base = emptyState()
  const state: EditorState = {
    ...base,
    name: 'half_adder',
    nextAutoId: 10,
    components: [
      { id: 'C1', type: 'INPUT', x: 40, y: 90, ioName: 'a' },
      { id: 'C2', type: 'INPUT', x: 40, y: 230, ioName: 'b' },
      { id: 'C3', type: 'XOR', x: 260, y: 100, label: 'sum' },
      { id: 'C4', type: 'AND', x: 260, y: 240, label: 'carry' },
      { id: 'C5', type: 'OUTPUT', x: 470, y: 110, ioName: 'sum' },
      { id: 'C6', type: 'OUTPUT', x: 470, y: 250, ioName: 'carry_out' },
    ],
    inputValues: { a: '0', b: '0' },
    nets: [
      {
        id: 'w1',
        driver: { component: 'C1', pin: 'out' },
        sinks: [
          { component: 'C3', pin: 'a' },
          { component: 'C4', pin: 'a' },
        ],
      },
      {
        id: 'w2',
        driver: { component: 'C2', pin: 'out' },
        sinks: [
          { component: 'C3', pin: 'b' },
          { component: 'C4', pin: 'b' },
        ],
      },
      { id: 'w3', driver: { component: 'C3', pin: 'out' }, sinks: [{ component: 'C5', pin: 'in' }] },
      { id: 'w4', driver: { component: 'C4', pin: 'out' }, sinks: [{ component: 'C6', pin: 'in' }] },
    ],
  }
  return state
}
