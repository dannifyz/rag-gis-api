"""Thai-numeral rendering for text that reaches the ONEP reviewer."""

import re

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


# A digit run that is not glued to Latin letters. The reference letters put every figure
# in Thai digits — "หมายเลข ๓๓๑", "พ.ศ. ๒๕๖๔", "ประมาณ ๗๒๐ เมตร" — but leave the digits
# inside Latin identifiers alone, one line even reading "หมายเลข ๕ (MR1)". A decimal
# glued to a Latin prefix (PM2.5) still converts its fractional half; no reference letter
# writes one, and the alternative is a tokeniser for a case that does not arise.
PROSE_DIGITS = re.compile(r"(?<![A-Za-z])\d+(?![A-Za-z])")


def thai_digits_in_prose(text: str) -> str:
    """Convert the figures in free text written by the model, sparing Latin identifiers."""
    return PROSE_DIGITS.sub(lambda match: to_thai_digits(match.group()), text)


def normalize_sara_am(text: str) -> str:
    """
    Put ำ back together where it arrived as นิคหิต + สระอา.

    The model emits the decomposed pair often enough to matter ("ระบายน้ํา" for
    "ระบายน้ำ"): the two render as near-identical glyphs, so it survives review and
    lands in a หนังสือราชการ as a word no Thai search will match.
    """
    return text.replace("ํา", "ำ")
