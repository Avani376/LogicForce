# Semantics: Hardware–Software Co-Simulation v1

Status: **CONTRACT for Phase 8** (implemented in `engines/cosim/cosim_engine`)
Engine version: 0.8.0 · Document schema version: **1**

## What v1 models

A **shared event scheduler** linking a schema-v1 combinational circuit and an
8086 program through **I/O ports**: the CPU's `OUT` writes drive circuit primary
inputs; the CPU's `IN` reads sample circuit primary outputs. One trace links
both worlds.

## Co-simulation document (schema 1)

```json
{
  "cosim_schema_version": 1,
  "name": "io_demo",
  "circuit": { …schema-v1 circuit… },
  "program": "MOV AL, 1\nOUT 0x40, AL\n…",
  "ports": [
    { "port": 64, "signal": "a", "direction": "input" },
    { "port": 65, "signal": "y", "direction": "output" }
  ],
  "cycles": 16
}
```

- `circuit`: a **valid** schema-v1 combinational circuit (validated before the run).
- `program`: 8086 assembly (the declared cpu8086 subset **plus `IN`/`OUT`**, below).
- `ports`: mappings; `input` direction = CPU→circuit (the named signal must be a
  circuit primary INPUT); `output` direction = circuit→CPU (named signal must be a
  circuit primary OUTPUT). Port numbers 0–0xFFFF, unique. Signal names must exist.
- `cycles`: 1–4096 (hard cap — refusal, never truncation).

## IN/OUT additions to the 8086 subset

| Mnemonic | Effect |
|---|---|
| `IN AL, p` (p: imm 0–255 or DX) | AL ← mapped circuit output sample (word via AX: 2 consecutive ports) |
| `OUT p, AL` (or `OUT DX, AL`) | mapped circuit input ← AL |

`IN`/`OUT` change no flags. If a port has no mapping, the read returns **X**
(honest: an unconnected port is unknown) and the write is recorded as
unmapped-but-ignored.

## Event ordering (normative — the shared scheduler)

Each co-simulation **cycle k** (0-indexed), in this exact order:

1. **Apply port writes** recorded during cycle k−1: each write lands on the
   mapped circuit primary input (value normalized; X allowed).
2. **Settle the circuit** with the current input vector (v1 propagation rules;
   one topological pass — the circuit is combinational).
3. **Execute one CPU instruction** (IP-indexed, cpu8086 semantics):
   - `IN` reads the circuit outputs **as settled in step 2**;
   - `OUT` is recorded for application in cycle k+1;
   - `HLT` ends the run (verdict `HALTED`).
4. **Record** the cycle: port writes made, port reads made, circuit outputs.

Rules: OUT writes are **never visible to IN in the same cycle** (one-cycle port
latency — deterministic and documented); circuit inputs not written by any port
keep their previous value (power-on X). The same document ⇒ byte-identical trace.

## Verdicts and scope

- `COMPLETED` — CPU executed HLT within the cycle budget.
- `BOUNDED(N cycles)` — cycle cap reached first; scope label states it.
- `INCOMPLETE` — circuit/program validation failed; reason mandatory.

## Out of scope for v1

Interrupt-driven I/O inside co-simulation (co-sim runs the bare CPU flow — the
interrupt machinery exists separately), async edge-triggered signals, per-gate
timing, word-wide ports beyond consecutive-port pairs (documented: `IN AX, p`
reads ports p and p+1).
