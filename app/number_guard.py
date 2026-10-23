"""Reject generated text that contains numbers absent from the aggregates JSON.

The LLM narrative may quote only numbers that exist in aggregates.json. A number in the text is
grounded when some value in the JSON equals it at the precision the text was written with: "3,5 %" is
grounded by 3.47, because 3.47 rounds to 3.5 at one decimal. Digit runs inside JSON strings count as
values, so "2025-12-31" grounds 2025, 12 and 31. Booleans never ground a number.

Conventions:
- Percentages are stored in percent units in the JSON (3.47, not 0.0347), as in the `_pct` names.
- The check is strict: a number not in the JSON is rejected even if it looks harmless, so write small
  counts as words or add them to the JSON.
- Section citations such as "§07" or "§11a" are not numbers and are removed before the check.
- A number written with more decimals than `app.max_written_decimals` (config/core.yaml) is rejected, so a
  raw float such as 3.535312230641093 never reaches the reader.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from halolens.config import load_config

# Optional minus (ASCII or U+2212); digits with optional space-grouped thousands (regular, no-break or narrow
# no-break space); optional decimal part after a comma or a dot. The lookbehind rejects matches glued to a
# letter, digit, dot or comma, so labels such as "Q1" give no number.
NUMBER_PATTERN = re.compile(r"(?<![\w.,])([-−]?)(\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](\d+))?")
CITATION_PATTERN = re.compile(r"§\s?\d+[A-Za-z]?")  # a section citation: "§07", "§11a"
THOUSANDS_SEPARATORS = re.compile(r"[   ]")
DIGIT_RUN = re.compile(r"\d+")

HALF_UNIT = 0.5             # a number written with d decimals is within half a unit of its true value
DECIMAL_BASE = 10           # the unit at d decimals is DECIMAL_BASE ** -d
FLOAT_TOLERANCE = 1e-9      # absorbs floating-point error in the comparison


@dataclass(frozen=True)
class WrittenNumber:
    """A number as written in the text: its original spelling, its value and its number of decimals."""

    text: str
    value: float
    decimals: int


class UngroundedNumberError(ValueError):
    """Raised when generated text contains numbers that the aggregates JSON does not support."""

    def __init__(self, numbers: list[str]):
        self.numbers = numbers
        super().__init__(f"Numbers not present in the aggregates JSON: {', '.join(numbers)}")


def max_written_decimals() -> int:
    """Most decimals a written number may carry, from config/core.yaml (`app.max_written_decimals`)."""
    return int(load_config()["app"]["max_written_decimals"])


def extract_numbers(text: str) -> list[WrittenNumber]:
    """Every number written in `text`, in order of appearance; section citations (§07, §11a) are ignored."""
    found = []
    for match in NUMBER_PATTERN.finditer(CITATION_PATTERN.sub(" ", text)):
        sign, integer, fraction = match.groups()
        digits = THOUSANDS_SEPARATORS.sub("", integer)
        value = float(f"{digits}.{fraction}" if fraction else digits)
        if sign:
            value = -value
        found.append(WrittenNumber(text=match.group(0), value=value, decimals=len(fraction or "")))
    return found


def json_values(node: Any) -> list[float]:
    """Every finite numeric value in a JSON-like object: numbers, plus digit runs inside strings."""
    if isinstance(node, bool) or node is None:
        return []
    if isinstance(node, (int, float)):
        return [float(node)] if math.isfinite(node) else []
    if isinstance(node, str):
        return [float(run) for run in DIGIT_RUN.findall(node)]
    if isinstance(node, dict):
        return [value for child in node.values() for value in json_values(child)]
    if isinstance(node, (list, tuple)):
        return [value for child in node for value in json_values(child)]
    return []


def is_grounded(number: WrittenNumber, values: list[float]) -> bool:
    """True when some JSON value rounds to the written number at the written precision."""
    tolerance = HALF_UNIT * DECIMAL_BASE ** -number.decimals + FLOAT_TOLERANCE
    return any(abs(value - number.value) <= tolerance for value in values)


def ungrounded_numbers(text: str, aggregates: Any, max_decimals: int | None = None) -> list[str]:
    """Spellings of the numbers in `text` that the aggregates do not support. Empty when the text is grounded.

    A number with more than `max_decimals` decimals (default: `app.max_written_decimals`) is rejected even when a JSON
    value equals it.
    """
    values = json_values(aggregates)
    limit = max_written_decimals() if max_decimals is None else max_decimals
    return [number.text for number in extract_numbers(text)
            if number.decimals > limit or not is_grounded(number, values)]


def check_grounded(text: str, aggregates: Any) -> None:
    """Raise UngroundedNumberError listing every unsupported number in `text`."""
    rejected = ungrounded_numbers(text, aggregates)
    if rejected:
        raise UngroundedNumberError(rejected)
