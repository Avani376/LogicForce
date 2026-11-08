# Syllabus-to-Module Traceability Matrix

Status legend: Not started / In progress / Done / Partial (reason)

## Unit 1: Digital Fundamentals → `engines/numsys/`, `engines/boolean/`

| Syllabus item | Module | Engine | UI view | Test file | Status |
|---|---|---|---|---|---|
| Decimal, binary, octal, hex conversion | numsys | `convert_base`, `base_to_base` | numsys converter panel | `tests/numsys/test_convert.py` | Done |
| Step-by-step conversion working | numsys | `convert_with_steps` | numsys worked-steps panel | `tests/numsys/test_steps.py` | Done |
| Invalid digit typed errors | numsys | `validate_digits` | error display | `tests/numsys/test_convert.py` | Done |
| 1's complement | numsys | `ones_complement` | numsys complement panel | `tests/numsys/test_complement.py` | Done |
| 2's complement | numsys | `twos_complement` | numsys complement panel | `tests/numsys/test_complement.py` | Done |
| Complement add/sub with flags | numsys | `complement_add` | numsys arithmetic panel | `tests/numsys/test_complement.py` | Done |
| BCD encode/decode + validity | numsys | `bcd_encode`, `bcd_decode` | numsys codes panel | `tests/numsys/test_codes.py` | Done |
| Excess-3 encode/decode | numsys | `excess3_encode`, `excess3_decode` | numsys codes panel | `tests/numsys/test_codes.py` | Done |
| Gray encode/decode | numsys | `gray_encode`, `gray_decode` | numsys codes panel | `tests/numsys/test_codes.py` | Done |
| ASCII lookup | numsys | `ascii_lookup` | numsys codes panel | `tests/numsys/test_codes.py` | Done |
| Boolean theorems (12 theorems) | boolean | `verify_theorem` | theorem panel | `tests/boolean/test_theorems.py` | Done |
| SOP/POS canonical forms | boolean | `to_sop`, `to_pos` | expression panel | `tests/boolean/test_forms.py` | Done |
| NAND-only conversion | boolean | `to_nand_only` | circuit transform | `tests/boolean/test_nand.py` | Done |
| NOR-only conversion | boolean | `to_nor_only` | circuit transform | `tests/boolean/test_nor.py` | Done |

## Unit 2: Combinational Circuits → `engines/boolean/`, `engines/logic/`

| Syllabus item | Module | Engine | UI view | Test file | Status |
|---|---|---|---|---|---|
| K-map 2/3/4-variable | boolean | `kmap_simplify` | K-map grid UI | `tests/boolean/test_kmap.py` | Done |
| Quine-McCluskey cross-check | boolean | `quine_mccluskey` | K-map verification | `tests/boolean/test_qm.py` | Done |
| Don't-care conditions | boolean | K-map X handling | K-map UI | `tests/boolean/test_kmap.py` | Done |
| Code converters (circuits) | logic | golden circuits | circuit editor | `tests/golden/` | Done (Phase 1) |
| 4-bit adder/subtractor | logic | circuit editor | circuit editor | `tests/golden/` | Done (Phase 1) |
| Mux/demux/encoder/decoder | logic | circuit editor | circuit editor | `tests/golden/` | Done (Phase 1) |
| Parity generator/checker | logic | circuit editor | circuit editor | `tests/golden/` | Done (Phase 1) |

## Unit 3: Sequential Circuits → `engines/sequential/`

| Syllabus item | Module | Engine | UI view | Test file | Status |
|---|---|---|---|---|---|
| Flip-flops (SR/JK/T/D) | sequential | `simulate_sequential` | waveform viewer | `tests/sequential/` | Done (Phase 2) |
| Truth/excitation tables | sequential | `flipflops.py` | tables panel | `tests/sequential/test_flipflops.py` | Done |
| Shift registers | sequential | composable from DFFs | circuit editor | `tests/golden/` | Done |
| Counters (ring, Johnson, mod-N) | sequential | `simulate_sequential` | waveform viewer | `tests/golden/` | Done |
| Sequence detectors | sequential | FSM model | circuit editor | `tests/cpu8086/` | Partial (FSM model done, dedicated UI pending) |

## Unit 4: Introduction to 8086 → `engines/cpu8086/`

| Syllabus item | Module | Engine | UI view | Test file | Status |
|---|---|---|---|---|---|
| Register organization | cpu8086 | `Registers` | registers panel | `tests/cpu8086/test_flags_registers.py` | Done |
| Flags (CF/PF/AF/ZF/SF/OF/IF) | cpu8086 | flag functions | flags panel | `tests/cpu8086/test_flags_registers.py` | Done |
| Memory segmentation | cpu8086 | `Memory`, `physical` | memory panel | `tests/cpu8086/test_flags_registers.py` | Done |
| Addressing modes | cpu8086 | assembler + executor | 8086 panel | `tests/cpu8086/` | Done (Phase 6) |
| Instruction subset | cpu8086 | executor | 8086 panel | `tests/cpu8086/` | Done (Phase 6) |
| Interrupts (INT/IRET/STI/CLI) | cpu8086 | interrupt controller | interrupt trace | `tests/cpu8086/test_interrupts.py` | Done (Phase 7) |

## Unit 5: 8086 Instruction Types → `engines/cpu8086/`

| Syllabus item | Module | Engine | UI view | Test file | Status |
|---|---|---|---|---|---|
| Data transfer (MOV/PUSH/POP) | cpu8086 | executor | 8086 panel | `tests/cpu8086/` | Done |
| Arithmetic (ADD/SUB/INC/DEC/NEG/CMP) | cpu8086 | executor | 8086 panel | `tests/cpu8086/` | Done |
| Logical (AND/OR/XOR/NOT/TEST) | cpu8086 | executor | 8086 panel | `tests/cpu8086/` | Done |
| Branch (JMP/Jcc/LOOP) | cpu8086 | executor | 8086 panel | `tests/cpu8086/` | Done |
| Subroutine (CALL/RET) | cpu8086 | executor | 8086 panel | `tests/cpu8086/` | Done |
| MUL/IMUL/DIV/IDIV | cpu8086 | executor | 8086 panel | `tests/cpu8086/test_mul_div.py` | Done (Phase C8) |
| Shifts/rotates | cpu8086 | executor | 8086 panel | `tests/cpu8086/test_timing.py` | Done (Phase C6) |
| String ops (MOVS/STOS/LODS/SCAS/CMPS + REP) | cpu8086 | executor | 8086 panel | `tests/cpu8086/test_string_ops.py` | Done (Phase C9) |

## Unit 6: Interrupts and 8259 → `engines/cpu8086/`, `engines/pic8259/`

| Syllabus item | Module | Engine | UI view | Test file | Status |
|---|---|---|---|---|---|
| IVT + interrupt response | cpu8086 | interrupt controller | interrupt trace | `tests/cpu8086/test_interrupts.py` | Done (Phase 7) |
| INTR vs NMI | cpu8086 | interrupt controller | interrupt trace | `tests/cpu8086/test_interrupts.py` | Done (Phase 7) |
| 8259 PIC | pic8259 | `Pic8259`, `resolve_pic_flow` | `/api/8086/pic` | `tests/pic8259/` | Done (Phase C7) |

## Cross-cutting

| Syllabus item | Module | Status |
|---|---|---|
| Verification engine | verify_engine | Done (Phase 3) |
| Fault injection + repair | fault_engine + repair_engine | Done (Phase 4) |
| Optimization | optimize_engine | Done (Phase 5) |
| Co-simulation | cosim_engine | Done (Phase 8) |
| Evidence-grounded explanations | verify_engine/explain | Done (Phase 9) |
| Docker deployment | Dockerfiles + compose | Done (Phase 10) |
| Curriculum layer (lessons/exercises) | curriculum | Not started |
| AI in Digital Systems module | curriculum | Not started |
