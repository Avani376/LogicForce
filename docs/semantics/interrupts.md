# Semantics: Interrupts (Phase 7 — cpu8086 extension)

Status: **CONTRACT for Phase 7** (implemented in `engines/cpu8086/cpu8086/interrupts.py`)
Engine version: 0.7.0 · Amends `cpu8086.md` (subset + flags)

## What v1 models

Software interrupts, maskable INTR, non-maskable NMI, the IF flag, and the
IVT/ISR lifecycle — at instruction-step granularity, fully deterministic.

## Additions to the subset

| Mnemonic | Effect |
|---|---|
| `INT n` (n: 0–255) | push FLAGS, push return index, jump to `IVT[n]`, IF ← 0 |
| `IRET` | pop return index, pop FLAGS, resume |
| `STI` / `CLI` | IF ← 1 / IF ← 0 |

`IF` joins the FLAGS register (initial 0 — interrupts disabled at power-on).
`STI`/`CLI` change no other flag. `IRET` restores ALL flags from the stack.

## IVT

The Interrupt Vector Table is an **explicit part of the run request**:
`{number: label}` pairs, resolved at load time to handler instruction indices
like jump labels. Unknown labels / numbers outside 0–255 / duplicate numbers are
typed `AsmError`-family errors. The IVT is replayable evidence — it is part of
`input_hash`.

## External interrupts (deterministic scheduling)

The run request carries scheduled external interrupts:

```json
{ "scheduled": [ { "source": "nmi", "at_step": 5, "number": 2 } ] }
```

- `at_step` fires *between* instructions: after step k completes and before
  step k+1 begins (step counter counts executed instructions).
- **NMI fires regardless of IF.** **INTR fires only when IF = 1**; an INTR
  arriving while IF = 0 or while another same-source interrupt is in flight is
  held pending and fires at the first boundary where IF = 1 (maskable waiting is
  observable in the trace as a `pending_intr` event, once, at scheduling time).
- Firing pushes FLAGS, pushes the return index, jumps to `IVT[number]`, sets
  IF ← 0, and emits an interrupt trace event. Max nesting depth: 8 — a firing
  beyond the cap is a typed runtime error (stack/depth abuse, never silent).
- Scheduling is part of `input_hash`: same program + same schedule ⇒ byte-identical
  trace (the determinism contract is unchanged).

## Trace records

Interrupt activity appears as trace records with `kind`:

```json
{ "step": 5, "kind": "interrupt", "number": 2, "source": "nmi", "handler": 12 }
{ "step": 9, "kind": "iret", "number": 2, "resumed_at": 6 }
```

Ordinary instruction records keep their existing shape (`kind: "instruction"` is
the default for backward compatibility of existing traces).

## Handler termination and runs

A run ends on HLT of the main flow **or** of a handler, on a breakpoint
(IP-based, so handlers can be debugged), on the step cap (interrupts consume
steps — bounded claims stay honest), or on a typed error. `IRET` without a
matching INT/external firing is a typed runtime error (flag-stack underflow).
