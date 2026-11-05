/**
 * SVG circuit canvas: gates, primary I/O, pins, wires.
 *
 * Accessibility: every gate and pin is a focusable, labeled target; the canvas is
 * keyboard-operable (arrows move selection, Delete removes, Escape cancels wiring);
 * values are shown as text (0/1/X) — never color alone (color-blind safe).
 */

import { useCallback, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import type { PinRefDoc } from '../types'
import {
  gateWidth,
  inputPins,
  isMultiInput,
  type EditorComponent,
  type EditorState,
} from '../lib/circuit'

const GATE_W = 110
const GATE_H = 56
const PIN_R = 6

interface CanvasProps {
  state: EditorState
  netValues: Record<string, string>
  outputs: Record<string, string>
  selectedId: string | null
  pendingPin: PinRefDoc | null
  onSelect: (id: string | null) => void
  onPinClick: (pin: PinRefDoc) => void
  onToggleInput: (ioName: string) => void
  onMove: (id: string, x: number, y: number) => void
  onDragBegin: () => void
  onDelete: (id: string) => void
  onMoveByKeyboard: (id: string, dx: number, dy: number) => void
}

function netIdFor(state: EditorState, component: string, pin: string): string | null {
  for (const net of state.nets) {
    if (net.driver.component === component && net.driver.pin === pin) return net.id
    for (const sink of net.sinks) {
      if (sink.component === component && sink.pin === pin) return net.id
    }
  }
  return null
}

function pinPosition(
  component: EditorComponent,
  pin: string,
): { x: number; y: number } {
  const pins = component.type === 'OUTPUT' ? ['in'] : inputPins(component)
  if (pin === 'out') {
    return { x: component.x + GATE_W, y: component.y + GATE_H / 2 }
  }
  const index = pins.indexOf(pin)
  const count = pins.length
  const y = component.y + ((index + 1) * GATE_H) / (count + 1)
  return { x: component.x, y }
}

export function Canvas(props: CanvasProps): JSX.Element {
  const {
    state,
    netValues,
    outputs,
    selectedId,
    pendingPin,
    onSelect,
    onPinClick,
    onToggleInput,
    onMove,
    onDragBegin,
    onDelete,
    onMoveByKeyboard,
  } = props

  const svgRef = useRef<SVGSVGElement | null>(null)
  const dragState = useRef<{ id: string; offsetX: number; offsetY: number } | null>(null)
  const [dragging, setDragging] = useState(false)

  const svgPoint = useCallback((event: { clientX: number; clientY: number }) => {
    const svg = svgRef.current
    if (svg === null) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }, [])

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<SVGGElement>, component: EditorComponent): void => {
      if (component.type === 'INPUT') return // inputs toggle, not drag
      event.preventDefault()
      const point = svgPoint(event)
      dragState.current = {
        id: component.id,
        offsetX: point.x - component.x,
        offsetY: point.y - component.y,
      }
      setDragging(true)
      onSelect(component.id)
      onDragBegin()
      ;(event.target as Element).setPointerCapture?.(event.pointerId)
    },
    [svgPoint, onSelect, onDragBegin],
  )

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<SVGSVGElement>): void => {
      if (dragState.current === null) return
      const point = svgPoint(event)
      const { id, offsetX, offsetY } = dragState.current
      onMove(id, Math.max(0, point.x - offsetX), Math.max(0, point.y - offsetY))
    },
    [svgPoint, onMove],
  )

  const endDrag = useCallback((): void => {
    dragState.current = null
    setDragging(false)
  }, [])

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>): void => {
      if (selectedId === null) return
      const step = event.shiftKey ? 1 : 10
      switch (event.key) {
        case 'ArrowLeft':
          event.preventDefault()
          onMoveByKeyboard(selectedId, -step, 0)
          break
        case 'ArrowRight':
          event.preventDefault()
          onMoveByKeyboard(selectedId, step, 0)
          break
        case 'ArrowUp':
          event.preventDefault()
          onMoveByKeyboard(selectedId, 0, -step)
          break
        case 'ArrowDown':
          event.preventDefault()
          onMoveByKeyboard(selectedId, 0, step)
          break
        case 'Delete':
        case 'Backspace':
          event.preventDefault()
          onDelete(selectedId)
          break
        default:
          break
      }
    },
    [selectedId, onMoveByKeyboard, onDelete],
  )

  const wireSegments = state.nets.map((net) => {
    const driver = state.components.find((c) => c.id === net.driver.component)
    if (driver === undefined) return null
    const from = pinPosition(driver, net.driver.pin)
    return net.sinks.map((sink) => {
      const sinkComp = state.components.find((c) => c.id === sink.component)
      if (sinkComp === undefined) return null
      const to = pinPosition(sinkComp, sink.pin)
      const midX = (from.x + to.x) / 2
      const path = `M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`
      const value = netValues[net.id] ?? 'X'
      return { key: `${net.id}_${sink.component}_${sink.pin}`, path, value, netId: net.id }
    })
  })

  return (
    <div
      className="canvas-wrap"
      tabIndex={0}
      role="application"
      aria-label="Circuit canvas"
      onKeyDown={handleKeyDown}
    >
      <svg
        ref={svgRef}
        className="canvas-svg"
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
        onClick={() => onSelect(null)}
      >
        <defs>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke="var(--grid-line)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {wireSegments.flat().map(
          (segment) =>
            segment !== null && (
              <g key={segment.key} className={`wire wire-${segment.value}`}>
                <title>{`net ${segment.netId}: ${segment.value}`}</title>
                <path d={segment.path} />
                <text className="wire-value">{segment.value}</text>
              </g>
            ),
        )}

        {state.components.map((component) => {
          const selected = component.id === selectedId
          if (component.type === 'INPUT') {
            const value = state.inputValues[component.ioName ?? ''] ?? 'X'
            return (
              <g
                key={component.id}
                className={`comp comp-input ${selected ? 'selected' : ''}`}
                transform={`translate(${component.x}, ${component.y})`}
              >
                <title>{`Primary input ${component.ioName}: ${value}. Click the value to toggle 0 → 1 → X.`}</title>
                <rect width={GATE_W} height={GATE_H} rx="8" className="io-box" />
                <text x="10" y="20" className="comp-title">
                  IN · {component.ioName}
                </text>
                <g
                  className="toggle-target"
                  onClick={(event) => {
                    event.stopPropagation()
                    onToggleInput(component.ioName ?? '')
                  }}
                  role="button"
                  tabIndex={-1}
                  aria-label={`Input ${component.ioName} is ${value}. Click to toggle.`}
                >
                  <rect x="14" y="28" width="34" height="20" rx="6" className={`value-box value-${value}`} />
                  <text x="31" y="42" textAnchor="middle" className="value-text">
                    {value}
                  </text>
                </g>
                <g
                  className="pin pin-out"
                  onClick={(event) => {
                    event.stopPropagation()
                    onPinClick({ component: component.id, pin: 'out' })
                  }}
                >
                  <circle cx={GATE_W} cy={GATE_H / 2} r={PIN_R} />
                  <title>{`output pin of ${component.id}`}</title>
                </g>
              </g>
            )
          }
          if (component.type === 'OUTPUT') {
            const value = outputs[component.ioName ?? ''] ?? 'X'
            return (
              <g
                key={component.id}
                className={`comp comp-output ${selected ? 'selected' : ''}`}
                transform={`translate(${component.x}, ${component.y})`}
                onClick={(event) => event.stopPropagation()}
              >
                <title>{`Primary output ${component.ioName}: ${value}`}</title>
                <rect width={GATE_W} height={GATE_H} rx="8" className="io-box" />
                <text x="10" y="20" className="comp-title">
                  OUT · {component.ioName}
                </text>
                <rect x="60" y="28" width="34" height="20" rx="6" className={`value-box value-${value}`} />
                <text x="77" y="42" textAnchor="middle" className="value-text">
                  {value}
                </text>
                <g
                  className="pin pin-in"
                  onClick={(event) => {
                    event.stopPropagation()
                    onPinClick({ component: component.id, pin: 'in' })
                  }}
                >
                  <circle cx={0} cy={GATE_H / 2} r={PIN_R} />
                  <title>{`input pin of ${component.id}`}</title>
                </g>
              </g>
            )
          }

          const pins = isMultiInput(component.type)
            ? inputPins(component)
            : ['a']
          const width = gateWidth(component.type, component)
          const pinNetValues = pins.map(
            (pin) => netValues[netIdFor(state, component.id, pin) ?? ''] ?? 'X',
          )
          const outValue = netValues[netIdFor(state, component.id, 'out') ?? ''] ?? 'X'
          return (
            <g
              key={component.id}
              className={`comp comp-gate ${selected ? 'selected' : ''}`}
              transform={`translate(${component.x}, ${component.y})`}
              onPointerDown={(event) => handlePointerDown(event, component)}
              onClick={(event) => {
                event.stopPropagation()
                onSelect(component.id)
              }}
              role="button"
              aria-label={`${component.type} gate ${component.id}${
                component.label ? `, ${component.label}` : ''
              }${width > 2 ? `, ${width} inputs` : ''}`}
            >
              <title>{`${component.type} ${component.id}. Drag to move. Output: ${outValue}.`}</title>
              <rect width={GATE_W} height={GATE_H} rx="8" className="gate-box" />
              <text x="12" y="22" className="comp-title">
                {component.type}
                {width > 2 ? `·w${width}` : ''}
              </text>
              {component.label !== undefined && (
                <text x="12" y="48" className="comp-label">
                  {component.label}
                </text>
              )}
              <text x={GATE_W - 10} y={GATE_H - 8} textAnchor="end" className={`pin-value value-${outValue}`}>
                {outValue}
              </text>
              {pins.map((pin, index) => (
                <g
                  key={pin}
                  className="pin pin-in"
                  onClick={(event) => {
                    event.stopPropagation()
                    onPinClick({ component: component.id, pin })
                  }}
                  aria-label={`input pin ${pin} of ${component.id}, currently ${pinNetValues[index]}`}
                >
                  <circle
                    cx={0}
                    cy={((index + 1) * GATE_H) / (pins.length + 1)}
                    r={PIN_R}
                  />
                  <title>{`input pin ${pin} of ${component.id}: ${pinNetValues[index]}`}</title>
                </g>
              ))}
              <g
                className="pin pin-out"
                onClick={(event) => {
                  event.stopPropagation()
                  onPinClick({ component: component.id, pin: 'out' })
                }}
                aria-label={`output pin of ${component.id}`}
              >
                <circle cx={GATE_W} cy={GATE_H / 2} r={PIN_R} />
                <title>{`output pin of ${component.id}: ${outValue}`}</title>
              </g>
            </g>
          )
        })}

        {pendingPin !== null && (
          <g className="pending-wire">
            <circle
              cx={
                pinPosition(
                  state.components.find((c) => c.id === pendingPin.component) ?? {
                    id: pendingPin.component,
                    type: 'AND',
                    x: 0,
                    y: 0,
                  },
                  pendingPin.pin,
                ).x
              }
              cy={
                pinPosition(
                  state.components.find((c) => c.id === pendingPin.component) ?? {
                    id: pendingPin.component,
                    type: 'AND',
                    x: 0,
                    y: 0,
                  },
                  pendingPin.pin,
                ).y
              }
              r="10"
            />
          </g>
        )}
      </svg>
      {dragging && <span className="visually-hidden">Dragging component</span>}
    </div>
  )
}
