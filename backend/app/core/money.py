from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP


def format_inr(paise: int) -> str:
    return "₹" + _group(paise)


def format_inr_words(paise: int) -> str:
    """ASCII amount for PDF fonts that do not include the rupee sign."""
    return "INR " + _group(paise)


def _group(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    rupees, frac = divmod(abs(int(paise)), 100)
    text = str(rupees)
    if len(text) > 3:
        head, tail = text[:-3], text[-3:]
        parts: list[str] = []
        while head:
            parts.append(head[-2:])
            head = head[:-2]
        text = ",".join(reversed(parts)) + "," + tail
    if frac:
        return f"{sign}{text}.{frac:02d}"
    return f"{sign}{text}"


def _paise_from_rupees(rupees: Decimal) -> int:
    return int((rupees * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


_LAKH = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|crore|crores)\b",
    re.IGNORECASE,
)
_CURRENCY = re.compile(
    r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d{1,2}))?",
    re.IGNORECASE,
)
_BARE = re.compile(r"\b(\d{4,9})\b")


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < stop and end > begin for begin, stop in spans)


def parse_amounts(text: str, *, allow_bare: bool = False) -> list[int]:
    """Return money amounts in paise, left to right.

    Lakh and crore phrases win over a currency match on the same span so
    "₹5 lakh" is 5 lakh, not 5 rupees.
    """
    found: list[tuple[int, int]] = []
    spans: list[tuple[int, int]] = []
    for match in _LAKH.finditer(text):
        number = Decimal(match.group(1))
        unit = match.group(2).lower()
        multiplier = Decimal(10_000_000) if unit.startswith("crore") else Decimal(100_000)
        found.append((match.start(), _paise_from_rupees(number * multiplier)))
        spans.append((match.start(), match.end()))
    for match in _CURRENCY.finditer(text):
        if _overlaps(match.start(), match.end(), spans):
            continue
        whole = Decimal(match.group(1).replace(",", ""))
        fraction = match.group(2)
        if fraction:
            whole += Decimal(fraction) / (Decimal(10) ** len(fraction))
        found.append((match.start(), _paise_from_rupees(whole)))
        spans.append((match.start(), match.end()))
    if allow_bare:
        for match in _BARE.finditer(text):
            if _overlaps(match.start(), match.end(), spans):
                continue
            found.append((match.start(), int(match.group(1)) * 100))
            spans.append((match.start(), match.end()))
    found.sort()
    return [amount for _, amount in found]


def parse_tenure_months(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*(months?|years?|yrs?)\b", text, re.IGNORECASE)
    if not match:
        return None
    count = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("y"):
        return count * 12
    return count
