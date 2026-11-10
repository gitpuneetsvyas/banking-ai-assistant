"""Executable fictional personal-loan policy.

These figures are POC examples. They are not a real bank's credit policy.
The knowledge documents must state the same figures; tests lock that link.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MIN_AMOUNT_PAISE = 5_000_000  # INR 50,000
MAX_AMOUNT_PAISE = 150_000_000  # INR 15,00,000
MIN_MONTHLY_INCOME_PAISE = 2_500_000  # INR 25,000
MAX_INCOME_MULTIPLE = 24
MIN_TENURE_MONTHS = 12
MAX_TENURE_MONTHS = 60
MIN_AGE = 21
MAX_AGE = 60
INCOME_MISMATCH_RATIO = Decimal("0.10")
ILLUSTRATIVE_ANNUAL_RATE = Decimal("0.125")
ILLUSTRATIVE_RATE_LABEL = "12.5%"
PROCESSING_FEE_RATE = Decimal("0.02")
PROCESSING_FEE_CAP_PAISE = 1_000_000  # INR 10,000
SCHEMA_VERSION = "poc-loan-v1"


def illustrative_emi_paise(principal_paise: int, months: int) -> int:
    """Reducing-balance EMI using the fictional illustrative annual rate."""
    if months <= 0 or principal_paise <= 0:
        raise ValueError("EMI needs a positive principal and tenure")
    monthly = ILLUSTRATIVE_ANNUAL_RATE / Decimal(12)
    factor = (1 + monthly) ** months
    emi = Decimal(principal_paise) * monthly * factor / (factor - 1)
    return int(emi.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def public_requirements() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "product": "personal",
        "fictional": True,
        "source_document": "DOC-PL-ELIG",
        "min_amount_paise": MIN_AMOUNT_PAISE,
        "max_amount_paise": MAX_AMOUNT_PAISE,
        "min_monthly_income_paise": MIN_MONTHLY_INCOME_PAISE,
        "max_income_multiple": MAX_INCOME_MULTIPLE,
        "min_tenure_months": MIN_TENURE_MONTHS,
        "max_tenure_months": MAX_TENURE_MONTHS,
        "min_age": MIN_AGE,
        "max_age": MAX_AGE,
        "income_mismatch_ratio": str(INCOME_MISMATCH_RATIO),
        "illustrative_rate_label": ILLUSTRATIVE_RATE_LABEL,
        "processing_fee_rate": str(PROCESSING_FEE_RATE),
        "processing_fee_cap_paise": PROCESSING_FEE_CAP_PAISE,
        "note": "Fictional POC policy. Not a sanction and not a real bank offer.",
    }
