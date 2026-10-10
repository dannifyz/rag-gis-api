"""Thai-numeral rendering for text that reaches the ONEP reviewer."""

import re

# สผ. letters number everything in Thai digits, so every figure printed into the report
# body goes through here. Figures handed to the LLM as context stay Arabic (see format_payload).
THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


def to_thai_digits(text: str) -> str:
    return text.translate(THAI_DIGITS)


def format_count(value: int) -> str:
    """A whole count as it reads after "จำนวน": ๙๒, ๑,๒๓๔."""
    return to_thai_digits(f"{value:,}")


def format_measure(value: float) -> str:
    """
    A measurement for prose: thousands separators, at most 2 decimals, Thai digits.

    Avoids `:g`, which flips to scientific notation around 1e6 (routine for a GIS area).
    """
    rounded = round(value, 2)

    if rounded == int(rounded):
        return to_thai_digits(f"{int(rounded):,}")

    return to_thai_digits(f"{rounded:,.2f}".rstrip("0").rstrip("."))


# A digit run not glued to Latin letters: figures convert to Thai digits, but digits
# inside Latin identifiers (MR1) stay. PM2.5 still converts its fractional half — no
# reference letter writes one, and handling it would need a tokeniser.
PROSE_DIGITS = re.compile(r"(?<![A-Za-z])\d+(?![A-Za-z])")


def thai_digits_in_prose(text: str) -> str:
    """Convert the figures in free text written by the model, sparing Latin identifiers."""
    return PROSE_DIGITS.sub(lambda match: to_thai_digits(match.group()), text)


def normalize_sara_am(text: str) -> str:
    """
    Put ำ back together where it arrived as นิคหิต + สระอา.

    The model emits the decomposed pair often ("ระบายน้ํา"); it renders near-identically,
    survives review, and lands as a word no Thai search matches.
    """
    return text.replace("ํา", "ำ")
