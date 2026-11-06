"""Number system conversions, complements, and codes with step traces.

Every function returns ``NumSysResult`` with ``result``, ``steps``, ``method``,
and ``scope_label`` per the addendum's shared result shape. Pure, deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    rule: str
    input: str
    output: str
    note: str = ""


@dataclass(frozen=True)
class NumSysResult:
    result: str
    steps: tuple[Step, ...]
    method: str
    scope_label: str = "EXHAUSTIVE"
    assumptions: tuple[str, ...] = ()


def _validate_digits(value: str, base: int) -> None:
    digits = "0123456789ABCDEF"[:base]
    for ch in value.upper():
        if ch != "." and ch not in digits:
            raise ValueError(f"invalid digit {ch!r} for base {base}")


def int_to_base(value: int, base: int) -> str:
    if base < 2 or base > 16:
        raise ValueError(f"base must be in [2, 16], got {base}")
    if value == 0:
        return "0"
    digits = "0123456789ABCDEF"
    negative = value < 0
    value = abs(value)
    result = []
    while value > 0:
        result.append(digits[value % base])
        value //= base
    return ("-" if negative else "") + "".join(reversed(result))


def convert_with_steps(value: str, from_base: int, to_base: int) -> NumSysResult:
    """Convert between bases 2–16 with step-by-step working."""
    _validate_digits(value.replace("-", "").replace(".", ""), from_base)
    decimal = int(value, from_base)
    steps: list[Step] = []

    if from_base != 10:
        steps.append(
            Step(
                f"Parse {value} as base-{from_base}",
                value,
                str(decimal),
                f"positional expansion: {value} base {from_base} = {decimal} base 10",
            )
        )
    if to_base != 10:
        result = int_to_base(decimal, to_base)
        temp = abs(decimal)
        div_steps: list[str] = []
        while temp > 0:
            div_steps.append(f"{temp} ÷ {to_base} = {temp // to_base} r {temp % to_base}")
            temp //= to_base
        if div_steps:
            steps.append(
                Step(
                    f"Repeated division by {to_base}",
                    str(decimal),
                    result,
                    "; ".join(div_steps[:6]) + ("..." if len(div_steps) > 6 else ""),
                )
            )
        return NumSysResult(result=result, steps=tuple(steps), method="repeated division", scope_label="EXHAUSTIVE")
    return NumSysResult(result=str(decimal), steps=tuple(steps), method="identity", scope_label="EXHAUSTIVE")


def ones_complement(value: str, width: int) -> NumSysResult:
    """1's complement: flip all bits in a fixed-width binary string."""
    if width not in (4, 8, 16):
        raise ValueError(f"width must be 4, 8, or 16, got {width}")
    value = value.strip()
    _validate_digits(value, 2)
    if len(value) != width:
        value = value.zfill(width)
    flipped = "".join("1" if b == "0" else "0" for b in value)
    return NumSysResult(
        result=flipped,
        steps=(Step("1's complement: flip all bits", value, flipped, f"each 0→1, each 1→0 in {width}-bit field"),),
        method="bitwise NOT",
    )


def twos_complement(value: str, width: int) -> NumSysResult:
    """2's complement: 1's complement + 1."""
    ones = ones_complement(value, width)
    flipped = ones.result
    carry = 1
    result_list = list(flipped)
    for i in range(width - 1, -1, -1):
        if carry:
            if result_list[i] == "1":
                result_list[i] = "0"
            else:
                result_list[i] = "1"
                carry = 0
    if carry:
        result_list.insert(0, "1")
    result = "".join(result_list)
    steps = list(ones.steps) + [
        Step("2's complement: add 1 to 1's complement", flipped, result, f"{flipped} + 1 = {result}")
    ]
    decimal = int(value, 2) if not value.startswith("1") or int(value, 2) == 0 else int(value, 2) - (1 << width)
    return NumSysResult(
        result=result,
        steps=tuple(steps),
        method="1's complement + 1",
        assumptions=(f"signed range for {width} bits: -{1 << (width - 1)} to +{(1 << (width - 1)) - 1}",),
    )


def complement_add(a: str, b: str, width: int, use_twos: bool = True) -> NumSysResult:
    """Add two binary numbers using complement arithmetic with carry/overflow."""
    if use_twos:
        comp_a = twos_complement(a, width)
        comp_b = twos_complement(b, width)
    else:
        comp_a = ones_complement(a, width)
        comp_b = ones_complement(b, width)
    int_a = int(a, 2) if not a.startswith("1") or int(a, 2) == 0 else int(a, 2) - (1 << width)
    int_b = int(b, 2) if not b.startswith("1") or int(b, 2) == 0 else int(b, 2) - (1 << width)
    total = int_a + int_b
    result = total & ((1 << width) - 1)
    result_bin = format(result, f"0{width}b")
    overflow = (int_a < 0) == (int_b < 0) and (result < 0) != (int_a < 0)
    carry_out = (total >> width) & 1
    method = "2's complement addition" if use_twos else "1's complement addition"
    steps: list[Step] = [
        Step(f"{method}: {a} + {b}", f"{a} + {b}", result_bin, f"decimal: {int_a} + {int_b} = {total}")
    ]
    if not use_twos and carry_out:
        steps.append(
            Step(
                "1's complement: end-around carry",
                result_bin,
                format(result + 1, f"0{width}b"),
                f"carry {carry_out} wrapped around",
            )
        )
        result_bin = format(result + 1, f"0{width}b")
    return NumSysResult(
        result=result_bin,
        steps=tuple(steps),
        method=method,
        assumptions=(f"carry_out={carry_out}, overflow={overflow}",),
    )


def bcd_encode(decimal: str) -> NumSysResult:
    """Encode each decimal digit as 4-bit BCD."""
    for ch in decimal:
        if not ch.isdigit():
            raise ValueError(f"BCD requires decimal digits, got {ch!r}")
    nibbles = [format(int(ch), "04b") for ch in decimal]
    invalid = [n for n in nibbles if int(n, 2) > 9]
    if invalid:
        raise ValueError(f"invalid BCD nibble {invalid[0]} (1010-1111 are invalid)")
    result = " ".join(nibbles)
    return NumSysResult(
        result=result,
        steps=tuple(Step(f"BCD: digit {ch} → {nib}", ch, nib) for ch, nib in zip(decimal, nibbles)),
        method="BCD 8421 encoding",
    )


def bcd_decode(bcd: str) -> NumSysResult:
    nibbles = bcd.split()
    digits = []
    steps = []
    for nib in nibbles:
        value = int(nib, 2)
        if value > 9:
            raise ValueError(f"invalid BCD nibble {nib} ({value} > 9)")
        digits.append(str(value))
        steps.append(Step(f"BCD decode: {nib} → {value}", nib, str(value)))
    return NumSysResult(result="".join(digits), steps=tuple(steps), method="BCD 8421 decoding")


def excess3_encode(decimal: str) -> NumSysResult:
    for ch in decimal:
        if not ch.isdigit():
            raise ValueError(f"Excess-3 requires decimal digits, got {ch!r}")
    nibbles = [format(int(ch) + 3, "04b") for ch in decimal]
    result = " ".join(nibbles)
    return NumSysResult(
        result=result,
        steps=tuple(Step(f"Excess-3: {ch} + 3 = {int(ch) + 3} → {nib}", ch, nib) for ch, nib in zip(decimal, nibbles)),
        method="Excess-3 (BCD + 3)",
    )


def excess3_decode(code: str) -> NumSysResult:
    nibbles = code.split()
    digits = []
    steps = []
    for nib in nibbles:
        value = int(nib, 2) - 3
        if not 0 <= value <= 9:
            raise ValueError(f"invalid Excess-3 nibble {nib} (decoded {value})")
        digits.append(str(value))
        steps.append(Step(f"Excess-3 decode: {nib} - 3 = {value}", nib, str(value)))
    return NumSysResult(result="".join(digits), steps=tuple(steps), method="Excess-3 decoding")


def gray_encode(binary: str) -> NumSysResult:
    _validate_digits(binary, 2)
    value = int(binary, 2)
    gray = value ^ (value >> 1)
    result = format(gray, f"0{len(binary)}b")
    steps = [Step(f"Gray encode: G = B ^ (B >> 1)", binary, result, f"{binary} XOR ({binary} >> 1) = {result}")]
    return NumSysResult(result=result, steps=tuple(steps), method="Gray encode: G = B ^ (B >> 1)")


def gray_decode(gray: str) -> NumSysResult:
    _validate_digits(gray, 2)
    binary_value = int(gray, 2)
    binary_value ^= binary_value >> 1
    result = format(binary_value, f"0{len(gray)}b")
    steps = []
    accumulator = 0
    for i in range(len(gray)):
        bit = int(gray[0]) if i == 0 else accumulator ^ int(gray[i])
        accumulator = (accumulator << 1) | bit
        steps.append(Step(f"Gray decode bit {i}: {gray[: i + 1]} → {result[: i + 1]}", gray[i], result[: i + 1]))
    return NumSysResult(result=result, steps=tuple(steps), method="Gray decode: B[i] = B[i-1] ^ G[i]")


def ascii_lookup(char: str) -> NumSysResult:
    code = ord(char)
    return NumSysResult(
        result=f"0x{code:02X} ({code})",
        steps=[
            Step(
                f"ASCII: {char!r} → {code}",
                char,
                f"0x{code:02X}",
                f"decimal={code}, hex=0x{code:02X}, binary={code:08b}",
            )
        ],
        method="ASCII (7-bit)",
    )
