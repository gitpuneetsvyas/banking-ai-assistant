from __future__ import annotations

import io
import re
from pathlib import Path

from pypdf import PdfReader
from pydantic import BaseModel

from app.core.errors import DomainError

_INCOME = re.compile(
    r"(?:net monthly income|monthly income)\s*[:\-]\s*(?:inr|rs\.?|₹)?\s*([0-9,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_ANNUAL = re.compile(
    r"(?:net annual income|total income)\s*[:\-]\s*(?:inr|rs\.?|₹)?\s*([0-9,]+)",
    re.IGNORECASE,
)
_EMPLOYEE = re.compile(r"employee name\s*[:\-]\s*(.+)", re.IGNORECASE)
_EMPLOYER = re.compile(r"^employer\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)


class Extraction(BaseModel):
    employee_name: str | None = None
    employer_name: str | None = None
    income_paise: int | None = None
    confidence: float
    notes: str


def extract_fields(filename: str, data: bytes) -> Extraction:
    text = read_text(filename, data)
    income = _money(_INCOME, text)
    note = "monthly income line"
    if income is None:
        annual = _money(_ANNUAL, text)
        if annual is not None:
            income = annual // 12
            note = "annual income divided by 12"
    employee = _line(_EMPLOYEE, text)
    employer = _line(_EMPLOYER, text)
    if income and employee and employer and note == "monthly income line":
        confidence = 0.93
    elif income and employee:
        confidence = 0.9
    elif income and note == "monthly income line":
        confidence = 0.8
    elif income:
        confidence = 0.7
    else:
        confidence = 0.2
        note = "no income line found"
    return Extraction(
        employee_name=employee,
        employer_name=employer,
        income_paise=income,
        confidence=confidence,
        notes=note,
    )


def read_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        if not data.startswith(b"%PDF"):
            raise DomainError("That file is not a readable PDF.")
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {".txt", ".md"}:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DomainError("Upload a UTF-8 text file or a PDF. Photographs are not read.") from exc
    raise DomainError("Upload a text or PDF document. This POC cannot read photographs.")


def _money(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    if not match:
        return None
    rupees = float(match.group(1).replace(",", ""))
    return int(round(rupees * 100))


def _line(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()
