from datetime import date
from pathlib import Path

from app.core.money import format_inr, parse_amounts
from app.domain.policy import (
    ILLUSTRATIVE_RATE_LABEL,
    MAX_AMOUNT_PAISE,
    MIN_MONTHLY_INCOME_PAISE,
    illustrative_emi_paise,
)
from app.domain.validation import collect_issues, review_issues
from app.core.config import BACKEND_ROOT


def test_indian_grouping_and_lakh_parsing():
    assert format_inr(12_500_000) == "₹1,25,000"
    assert format_inr(4_250_000) == "₹42,500"
    assert format_inr(875_000) == "₹8,750"
    assert parse_amounts("a personal loan of ₹5 lakh") == [50_000_000]
    assert parse_amounts("₹80,000") == [8_000_000]
    assert parse_amounts("₹1,25,000") == [12_500_000]


def test_policy_figures_are_the_ones_in_the_approved_page():
    text = Path(BACKEND_ROOT, "knowledge", "personal-loan-eligibility.md").read_text(encoding="utf-8")
    assert "INR 25000" in text
    assert "INR 50000" in text
    assert "INR 1500000" in text
    assert ILLUSTRATIVE_RATE_LABEL in text
    assert "8.5%" not in text
    assert MIN_MONTHLY_INCOME_PAISE == 2_500_000
    assert MAX_AMOUNT_PAISE == 150_000_000


def test_income_mismatch_is_a_review_not_a_silent_accept():
    loan = {
        "consent": True,
        "product_code": "personal",
        "requested_amount_paise": 50_000_000,
        "tenure_months": 36,
        "purpose": "Home renovation",
        "employment_type": "salaried",
        "employer_name": "Northwind Analytics Pvt Ltd",
        "monthly_income_paise": 8_000_000,
        "personal": {
            "first_name": {"value": "Priya", "source": "kyc"},
            "last_name": {"value": "Sharma", "source": "kyc"},
            "date_of_birth": {"value": "1992-04-18", "source": "kyc"},
            "email": {"value": "priya.sharma@example.com", "source": "kyc"},
            "phone": {"value": "9845012345", "source": "kyc"},
            "address_line": {"value": "42 Residency Road", "source": "kyc"},
            "city": {"value": "Bengaluru", "source": "kyc"},
            "state": {"value": "Karnataka", "source": "kyc"},
            "postal_code": {"value": "560025", "source": "kyc"},
            "kyc_status": {"value": "verified", "source": "kyc"},
        },
        "documents": [
            {
                "id": 1,
                "doc_type": "salary_slip",
                "extraction": {
                    "employee_name": "Priya Sharma",
                    "employer_name": "Northwind Analytics Pvt Ltd",
                    "income_paise": 5_000_000,
                    "confidence": 0.93,
                },
            }
        ],
    }
    issues = collect_issues(loan, date(2026, 11, 9))
    assert any("differs" in issue.message for issue in review_issues(issues))
    assert illustrative_emi_paise(50_000_000, 36) > 0
