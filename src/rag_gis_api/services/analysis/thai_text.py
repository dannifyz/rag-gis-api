"""Thai-numeral rendering for text that reaches the ONEP reviewer."""

# Every สผ. letter in the reference set numbers everything in Thai digits -
# "จำนวน ๙๒ แห่ง", "พ.ศ. ๒๕๖๔", "ประมาณ ๗๒๐ เมตร" - so every figure printed into the
# report body goes through here. Arabic digits in a หนังสือราชการ read as an unproofed
# draft. Figures handed to the LLM as context stay Arabic (see format_payload).
THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


def to_thai_digits(text: str) -> str:
    return text.translate(THAI_DIGITS)


def format_count(value: int) -> str:
    """A whole count as it reads after "จำนวน": ๙๒, ๑,๒๓๔."""
    return to_thai_digits(f"{value:,}")


def format_measure(value: float) -> str:
    """
    A measurement for prose: thousands separators, at most 2 decimals, Thai digits.

    Plain `:g` flips to scientific notation around 1e6 - routine for a GIS area in
    square metres - which would reach the reader as broken text mid-sentence.
    """
    rounded = round(value, 2)

    if rounded == int(rounded):
        return to_thai_digits(f"{int(rounded):,}")

    return to_thai_digits(f"{rounded:,.2f}".rstrip("0").rstrip("."))
