# LogicForge — Video Walkthrough Script (~90 seconds)

This is the official recording script for a demo video. Every scene shows real,
working features — record it straight through with no cuts needed. Suggested
tooling: any screen recorder at 1920×1080, 30 fps, with the API
(`uvicorn logicforge_api.main:app --port 8000`) and web app
(`cd apps/web && npm run dev`) running.

| # | Time | Scene | Action on screen | What the viewer sees |
|---|---|---|---|---|
| 1 | 0:00–0:08 | Hook | Land on the Circuit tab | Sparky the mascot waves in with the welcome bubble: "every number comes from a real deterministic engine" |
| 2 | 0:08–0:20 | Build | Drag an INPUT, an AND, an OUTPUT; wire them; toggle inputs | Live output probe flips 0/1; validation panel stays green |
| 3 | 0:20–0:30 | Truth table | Press **Truth Table** | The heatmap tab reveals rows with a staggered animation — EXHAUSTIVE(2^n) scope chip visible |
| 4 | 0:30–0:40 | Verify | Open **Verify**, add `out == in1 AND in2`, run | Verdict PASS with scope label; Sparky does a happy bounce |
| 5 | 0:40–0:50 | Fault & repair | Fault-inject a stuck-at, re-run, then repair-search | FAIL → counterexample → repair candidates, each re-verified |
| 6 | 0:50–1:00 | 8086 | Open **8086 CPU**, press ▶ Run on the sum loop | Registers animate, trace scrolls, Sparky cheers at the clean HLT |
| 7 | 1:00–1:10 | PIC | In the PIC section, resolve a flow | Deliveries appear: "step 3: IR2 → vector 10" |
| 8 | 1:10–1:20 | Learn + AI | Open **Learn**, submit an answer; then click Sparky → "what is a K-map?" | Engine-graded PASS + Sparky celebration; grounded answer citing the catalog |
| 9 | 1:20–1:30 | Visuals | Open **Visuals** | Pipeline pulse travels Specify→Re-Verify; event bars grow; truth-table heatmap and waveforms draw on |
| 10 | 1:30–1:35 | Close | Zoom on the footer | "Deterministic engines. Honest claims. Cute mascot." |

## Narration beats (short)

1. "This is LogicForge — an engineering workspace where every result is computed by a deterministic engine."
2. "Build a circuit, and the truth table is exhaustive — with a scope label, not a guess."
3. "Verification failures come with replayable counterexamples; repairs are only accepted after re-verification."
4. "The 8086 core runs the full educational instruction set, interrupts included — vector delivery from the 8259 PIC is exact."
5. "Sparky, the mascot, guides you — and its answers are grounded: engine output or the lesson catalog, never invented."
6. "Everything you just saw is open source, tested by 897 tests, and runs in Docker."

## Honest notes

- The video is a **script**, not a committed binary — record it from this file so the
  demo can never drift from the real product.
- If a feature is ever changed or removed, update this script in the same commit.
