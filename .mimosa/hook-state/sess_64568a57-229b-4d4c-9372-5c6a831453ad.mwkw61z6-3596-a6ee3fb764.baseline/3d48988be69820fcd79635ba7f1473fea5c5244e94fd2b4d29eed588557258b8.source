"""Phase 4 engine-validation probes: boundary and edge cases beyond the unit suite.

Run: .venv/Scripts/python scripts/engine_validation.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "engines/logic")
sys.path.insert(0, "engines/cpu8086")
sys.path.insert(0, "engines/pic8259")

from cpu8086.machine import assemble_and_load  # noqa: E402
from cpu8086.machine import _to_signed  # noqa: E402
from logic_engine import parse_circuit, simulate  # noqa: E402
from pic8259 import Pic8259  # noqa: E402

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, note: str = "") -> None:
    results.append(("PASS" if ok else "FAIL", name, note))


# --- 8086 arithmetic boundaries -------------------------------------------------
def run(src: str):
    machine = assemble_and_load(src)
    machine.run()
    return machine


try:
    run("MOV AX, 0x8000\nMOV DX, 0xFFFF\nMOV BX, 0xFFFF\nIDIV BX\nHLT")
    check("IDIV -32768/-1 overflow is typed error", False, "no error raised")
except Exception as exc:  # noqa: BLE001
    check("IDIV -32768/-1 overflow is typed error", "overflow" in str(exc).lower(), type(exc).__name__)

try:
    run("MOV AX, 0\nMOV DX, 1\nMOV BX, 1\nDIV BX\nHLT")
    check("DIV quotient 0x10000 overflows word", False, "no error raised")
except Exception as exc:  # noqa: BLE001
    check("DIV exact 0x10000 quotient overflow", "overflow" in str(exc).lower(), type(exc).__name__)

m = run("MOV AX, 0xFFFF\nADD AX, 1\nHLT")
check(
    "ADD 0xFFFF+1 wraps, CF=1",
    m.registers.get("AX") == 0 and m.registers.flags["CF"] == 1 and m.registers.flags["ZF"] == 1,
    str(m.registers.flags),
)

m = run("MOV AX, 0x7FFF\nADD AX, 1\nHLT")
check(
    "ADD 0x7FFF+1 signed overflow OF=1",
    m.registers.get("AX") == 0x8000 and m.registers.flags["OF"] == 1,
    str(m.registers.flags),
)

m = run("MOV AL, 0x80\nMOV BL, 0x80\nIMUL BL\nHLT")  # -128 * -128 = 16384 > byte half
check(
    "IMUL -128*-128 overflows byte half",
    m.registers.get("AX") == 16384 and m.registers.flags["CF"] == 1,
    f"AX={m.registers.get('AX')}",
)

# --- 8086 string ops with DF and CX=0 -------------------------------------------
m = run("MOV WORD [0x210], 0xBEEF\nMOV SI, 0x211\nMOV DI, 0x401\nMOV CX, 0\nSTD\nREP MOVSW\nHLT")
check(
    "REP MOVSW with CX=0 is a no-op under STD",
    m.registers.get("SI") == 0x211 and m.memory.read_word(0, 0x401) == 0,
    f"SI={m.registers.get('SI')}",
)

m = run("MOV WORD [0x210], 0xBEEF\nMOV SI, 0x210\nMOV DI, 0x410\nMOV CX, 1\nSTD\nREP MOVSW\nHLT")
check(
    "STD MOVSW copies word backwards",
    m.memory.read_word(0, 0x410) == 0xBEEF and m.registers.get("DI") == 0x40E,
    f"DI={m.registers.get('DI')}",
)

# --- PIC edge cases --------------------------------------------------------------
pic = Pic8259()
pic.write_icw1(0x13)
pic.write_icw2(8)
pic.write_icw4(0x01)
pic.request(2)
pic.acknowledge()
pic.request(6)
try:
    pic.write_ocw2(0xA0)  # rotate on non-specific EOI: clears IR2, floor<-2
    # IR6 rank under floor 2: (6-2-1)%8=3 ; nothing in service -> should deliver
    check("rotate-EOI then pending IR6 delivers", pic.int_vector() == 14, str(pic.int_vector()))
except Exception as exc:  # noqa: BLE001
    check("rotate-EOI then pending IR6 delivers", False, repr(exc))

pic2 = Pic8259()
pic2.write_icw1(0x13)
pic2.write_icw2(16)
pic2.write_icw4(0x01)
pic2.request(0)
pic2.acknowledge()
pic2.request(7)  # lowest priority, blocked by IR0 in service
blocked = pic2.int_vector() is None
pic2.write_ocw1(1 << 0)  # mask IR0 while in service — SMM off: masked best-in-service
check("masking the in-service line does not service lower in normal mode", blocked, "")

# --- logic engine: X propagation through XOR --------------------------------------
doc = {
    "schema_version": 1,
    "components": [
        {"id": "A", "type": "INPUT", "params": {"name": "a"}},
        {"id": "B", "type": "INPUT", "params": {"name": "b"}},
        {"id": "G", "type": "XOR"},
        {"id": "O", "type": "OUTPUT", "params": {"name": "o"}},
    ],
    "nets": [
        {"id": "n1", "driver": {"component": "A", "pin": "out"}, "sinks": [{"component": "G", "pin": "a"}]},
        {"id": "n2", "driver": {"component": "B", "pin": "out"}, "sinks": [{"component": "G", "pin": "b"}]},
        {"id": "n3", "driver": {"component": "G", "pin": "out"}, "sinks": [{"component": "O", "pin": "in"}]},
    ],
}
try:
    graph = parse_circuit(doc)
    sim = simulate(graph, {"a": "X", "b": "0"})
    check("XOR with X input propagates X", sim.outputs.get("o") == "X", str(sim.outputs))
except Exception as exc:  # noqa: BLE001
    check("XOR with X input propagates X", False, repr(exc))

fails = [r for r in results if r[0] == "FAIL"]
for status, name, note in results:
    print(f"{status}  {name}" + (f"   [{note}]" if status == "FAIL" else ""))
print(f"\n{len(results) - len(fails)}/{len(results)} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
