# Syllabus Notes — Deviations and Clarifications

## "Bit Inherent / Bit Direct Addressing" (Unit 4)

**These are 8051 addressing modes, not 8086 modes.** Several textbooks (especially
those covering the 8051 microcontroller) list "bit inherent" and "bit direct"
addressing alongside the 8086 modes. This is a categorization error:

- The **8086** does not have single-bit addressing modes. Bit manipulation is done
  via logical instructions (AND/OR/XOR with masks), `TEST`, and shift/rotate
  instructions.
- The **8051** has dedicated bit-addressable RAM (20h–2Fh) and bit-oriented
  instructions (SETB, CLR, CPL, JB, JNB).

**Action taken:** We do not implement these as 8086 features. If the syllabus
requires a comparison, a clearly labeled "Compare with 8051" note is available
on request. The real 8086 equivalent is bit manipulation via logical/shift
instructions and `TEST`.

## 8086 "Bit Inherent" equivalent in LogicForge

The `TEST` and `AND`/`OR`/`XOR` instructions with immediate masks serve the same
purpose as 8051 bit operations. The bit-manipulation lab (Unit 5) demonstrates
set/clear/toggle/test using masks.

## 8086 MUL/DIV timing

The real 8086 MUL takes 70–118 cycles and DIV takes 86–162 cycles depending on
operand values. Our v1 does not model these instructions at all (they are in the
"not modeled" list). When they are added, the timing will use the published
lookup tables, not a formula.
