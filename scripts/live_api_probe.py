"""Senior-tester live API probe: every endpoint + edge cases, PASS/FAIL per check.

Run: .venv/Scripts/python scripts/live_api_probe.py [port]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import urllib.error
import urllib.request

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else '8071'}"
results: list[tuple[str, str, str]] = []


def call(method: str, path: str, body: object | None = None):
    req = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(name: str, ok: bool, note: str = "") -> None:
    results.append(("PASS" if ok else "FAIL", name, note))


# Golden half-adder — the exact committed fixture, loaded as the circuit doc.
with open(Path(__file__).resolve().parent.parent / "tests" / "golden" / "fixtures" / "half_adder.json", encoding="utf-8") as fh:
    half_adder = json.load(fh)["circuit"]

# circuits
st, b = call("POST", "/api/circuits/simulate", {"circuit": half_adder, "inputs": {"a": "1", "b": "1"}})
check("simulate a=1,b=1 -> carry 1", st == 200 and b["outputs"].get("carry_out") == "1", str(b.get("outputs")))
st, b = call("POST", "/api/circuits/truth-table", {"circuit": half_adder})
check("truth-table 4 rows EXHAUSTIVE", st == 200 and len(b["rows"]) == 4 and "EXHAUSTIVE" in b["scope"], str(b.get("scope")))
st, b = call("POST", "/api/circuits/simulate", {"schema_version": 1})
check("circuit missing nets -> 422 schema", st == 422, str(st))

# sequential + fsm (golden fixture — the same doc the integration suite uses)
with open(Path(__file__).resolve().parent.parent / "tests" / "golden" / "fixtures_seq" / "seq_divide_by_2.json", encoding="utf-8") as fh:
    seq_fixture = json.load(fh)
st, b = call("POST", "/api/sequential/simulate", {"circuit": seq_fixture["circuit"], "cycles": 2, "inputs_per_cycle": seq_fixture["inputs_per_cycle"][:2]})
check("sequential simulate runs", st == 200 and "BOUNDED" in b["scope"], str(st))
fsm = {
    "fsm_schema_version": 1,
    "inputs": ["x"],
    "outputs": ["z"],
    "states": ["S0", "S1"],
    "initial": "S0",
    "transitions": [
        {"from": "S0", "when": {"x": "0"}, "to": "S0", "outputs": {"z": "0"}},
        {"from": "S0", "when": {"x": "1"}, "to": "S1", "outputs": {"z": "1"}},
        {"from": "S1", "when": {"x": "0"}, "to": "S0", "outputs": {"z": "0"}},
        {"from": "S1", "when": {"x": "1"}, "to": "S1", "outputs": {"z": "1"}},
    ],
}
st, b = call("POST", "/api/fsm/simulate", {"fsm": fsm, "input_sequence": [{"x": "1"}, {"x": "0"}]})
check("fsm simulate", st == 200 and b["final_state"] == "S0", str(st))
st, b = call("POST", "/api/fsm/reachable", {"fsm": fsm})
check("fsm reachable", st == 200, str(st))

# verify
st, b = call("POST", "/api/verify", {
    "kind": "fsm_invariant",
    "model": fsm,
    "property": {
        "property_schema_version": 1,
        "id": "P1",
        "kind": "fsm_invariant",
        "statement": "z is deterministic",
        "expression": "z",
    },
})
check("verify endpoint responds", st in (200, 400), str(st))

# 8086
st, b = call("POST", "/api/8086/assemble", {"source": "MOV AX, 5\nADD AX, 3\nHLT"})
check("assemble", st == 200 and b["instruction_count"] == 3, str(st))
st, b = call("POST", "/api/8086/run", {"source": "MOV AX, 5\nADD AX, 3\nHLT", "max_steps": 10})
check("run AX=8", st == 200 and b["registers"]["AX"] == 8, str(b.get("registers", {}).get("AX")))
st, b = call("POST", "/api/8086/run", {"source": "MOV AL, 12\nMOV BL, 10\nMUL BL\nHLT", "max_steps": 10})
check("run MUL AX=120", st == 200 and b["registers"]["AX"] == 120, str(b.get("registers", {}).get("AX")))
st, b = call("POST", "/api/8086/run", {"source": "MOV AL, 0xAB\nMOV DI, 0x400\nMOV CX, 4\nREP STOSB\nHLT", "max_steps": 10})
check("run REP STOSB", st == 200, str(st))
st, b = call("POST", "/api/8086/run", {"source": "MOV AX, 5\nMOV BX, 0\nDIV BX\nHLT", "max_steps": 10})
check("divide-by-zero -> 400 typed", st == 400 and b["detail"]["code"] == "CPU_RUNTIME_ERROR", str(st))
st, b = call("POST", "/api/8086/step", {"source": "MOV AX, 9\nHLT"})
check("step", st == 200, str(st))

# 8086 pic
st, b = call("POST", "/api/8086/pic", {"base_vector": 8, "events": [{"at_step": 2, "op": "request", "line": 2}]})
check("pic flow delivery", st == 200 and b["deliveries"][0]["vector"] == 10, str(b.get("deliveries")))
st, b = call("POST", "/api/8086/pic", {"base_vector": 12, "events": []})
check("pic bad base -> 400", st == 400 and b["detail"]["category"] == "BAD_VECTOR_BASE", str(st))
st, b = call("POST", "/api/8086/pic", {"base_vector": 8, "events": [{"at_step": 1, "op": "poll", "line": 0}]})
check("pic bad op -> 400", st == 400 and b["detail"]["category"] == "BAD_EVENT", str(st))

# explain
st, b = call("POST", "/api/explain", {"kind": "cpu_trace", "explanation_schema_version": 1, "evidence": {"trace": [{"kind": "instruction", "step": 1, "ip": 0, "instruction": "HLT", "halted": True}], "stop_reason": "hlt"}})
check("explain cpu_trace", st == 200 and b.get("summary"), str(st))

# curriculum
st, b = call("GET", "/api/curriculum/lessons")
check("lessons 6", st == 200 and len(b["lessons"]) == 6, str(st))
st, b = call("GET", "/api/curriculum/exercises")
check("exercises 7, no answers leaked", st == 200 and len(b["exercises"]) == 7 and all("data" not in e for e in b["exercises"]), str(st))
st, b = call("GET", "/api/curriculum/exercises/nope")
check("exercise 404", st == 404, str(st))
st, b = call("POST", "/api/curriculum/grade", {"exercise_id": "num-convert-hex2dec", "submission": "0x2F"})
check("grade correct", st == 200 and b["passed"] is True, str(st))
st, b = call("POST", "/api/curriculum/grade", {"exercise_id": "num-convert-hex2dec", "submission": "99"})
check("grade wrong -> 200 passed=False", st == 200 and b["passed"] is False, str(st))
st, b = call("POST", "/api/curriculum/grade", {"exercise_id": "nope", "submission": "1"})
check("grade unknown -> 404", st == 404, str(st))
st, b = call("POST", "/api/curriculum/grade", {"exercise_id": "bool-equiv-demorgan", "submission": "A &"})
check("grade bad submission -> 400", st == 400 and b["detail"]["category"] == "BAD_SUBMISSION", str(st))

# assistant — every intent + errors
st, b = call("POST", "/api/assistant/ask", {"question": "test me"})
check("assistant exercise", st == 200 and b["kind"] == "exercise", str(st))
st, b = call("POST", "/api/assistant/ask", {"question": "what is a flip-flop?"})
check("assistant lesson", st == 200 and b["kind"] == "lesson", str(st))
ctx = {"trace": [{"kind": "instruction", "step": 1, "ip": 0, "instruction": "HLT", "halted": True}], "stop_reason": "hlt"}
st, b = call("POST", "/api/assistant/ask", {"question": "why did it stop?", "context": ctx})
check("assistant explain grounded", st == 200 and b["grounding"] == "engine_output", str(b.get("grounding")))
st, b = call("POST", "/api/assistant/ask", {"question": "why did it fail?"})
check("assistant no-context refuses", st == 200 and b["grounding"] == "guidance", str(b.get("grounding")))
st, b = call("POST", "/api/assistant/ask", {"question": "tell me about the PIC"})
check("assistant guide pic", st == 200 and b["kind"] == "guide", str(st))
st, b = call("POST", "/api/assistant/ask", {"question": "hello"})
check("assistant meta", st == 200 and b["kind"] == "meta", str(st))
st, b = call("POST", "/api/assistant/ask", {"question": "   "})
check("assistant empty -> 400", st == 400 and b["detail"]["category"] == "EMPTY_QUESTION", str(st))
st, b = call("POST", "/api/assistant/ask", {"question": "why?", "context": [1]})
check("assistant non-object context -> 422 schema", st == 422, str(st))

# infra
st, b = call("GET", "/api/nonexistent")
check("unknown route -> 404", st == 404, str(st))

fails = [r for r in results if r[0] == "FAIL"]
for status, name, note in results:
    print(f"{status}  {name}" + (f"   [{note}]" if status == "FAIL" else ""))
print(f"\n{len(results) - len(fails)}/{len(results)} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
