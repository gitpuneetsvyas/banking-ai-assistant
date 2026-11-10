from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.core.money import format_inr
from app.domain.contract import REQUIRED_PERSONAL
from app.domain.policy import (
    INCOME_MISMATCH_RATIO,
    MAX_AGE,
    MAX_AMOUNT_PAISE,
    MAX_INCOME_MULTIPLE,
    MAX_TENURE_MONTHS,
    MIN_AGE,
    MIN_AMOUNT_PAISE,
    MIN_MONTHLY_INCOME_PAISE,
    MIN_TENURE_MONTHS,
)


@dataclass(frozen=True)
class Issue:
    field: str
    message: str
    review: bool = False


def age_on(born: date, today: date) -> int:
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


def personal_value(loan: dict, key: str) -> str:
    meta = (loan.get("personal") or {}).get(key) or {}
    return str(meta.get("value") or "").strip()


def required_doc_type(loan: dict) -> str | None:
    if loan.get("employment_type") == "salaried":
        return "salary_slip"
    if loan.get("employment_type") == "self_employed":
        return "income_tax_return"
    return None


def latest_extraction(loan: dict, doc_type: str) -> dict | None:
    matches = [item for item in loan.get("documents") or [] if item.get("doc_type") == doc_type]
    if not matches:
        return None
    return matches[-1].get("extraction") or {}


def names_match(employee: str, first: str, last: str) -> bool:
    folded = re.sub(r"\s+", " ", employee).casefold()
    return first.casefold() in folded and last.casefold() in folded


def employers_match(stated: str, extracted: str) -> bool:
    left = stated.casefold().strip()
    right = extracted.casefold().strip()
    return left in right or right in left


def document_has_income(loan: dict) -> bool:
    doc_type = required_doc_type(loan)
    if not doc_type:
        return False
    extraction = latest_extraction(loan, doc_type)
    return bool(extraction and extraction.get("income_paise"))


def next_missing(loan: dict) -> str | None:
    fields = missing_fields(loan)
    return fields[0] if fields else None


def missing_fields(loan: dict) -> list[str]:
    if not loan.get("consent"):
        return ["consent"]
    missing: list[str] = []
    for key in REQUIRED_PERSONAL:
        if not personal_value(loan, key):
            missing.append(key)
    if loan.get("product_code") != "personal":
        missing.append("product")
    if loan.get("requested_amount_paise") is None:
        missing.append("requested_amount_paise")
    if loan.get("employment_type") not in {"salaried", "self_employed"}:
        missing.append("employment_type")
    elif len(str(loan.get("employer_name") or "").strip()) < 2:
        missing.append("employer_name")
    if loan.get("monthly_income_paise") is None:
        missing.append("monthly_income_paise")
    if loan.get("tenure_months") is None:
        missing.append("tenure_months")
    if len(str(loan.get("purpose") or "").strip()) < 3:
        missing.append("purpose")
    doc_type = required_doc_type(loan)
    if doc_type and not document_has_income(loan):
        missing.append("document")
    return missing


def range_issue(loan: dict) -> Issue | None:
    amount = loan.get("requested_amount_paise")
    income = loan.get("monthly_income_paise")
    tenure = loan.get("tenure_months")
    if amount is not None and not (MIN_AMOUNT_PAISE <= amount <= MAX_AMOUNT_PAISE):
        return Issue(
            "requested_amount_paise",
            "The fictional personal-loan policy allows "
            f"{format_inr(MIN_AMOUNT_PAISE)} to {format_inr(MAX_AMOUNT_PAISE)}. "
            "What amount should I use?",
        )
    if income is not None and income < MIN_MONTHLY_INCOME_PAISE:
        return Issue(
            "monthly_income_paise",
            "The fictional personal-loan policy requires monthly income of at least "
            f"{format_inr(MIN_MONTHLY_INCOME_PAISE)}. What is your monthly income?",
        )
    if (
        amount is not None
        and income is not None
        and income > 0
        and amount > income * MAX_INCOME_MULTIPLE
    ):
        return Issue(
            "requested_amount_paise",
            "That amount is more than "
            f"{MAX_INCOME_MULTIPLE} times monthly income under the fictional "
            "personal-loan policy (DOC-PL-ELIG). What amount should I use?",
        )
    if tenure is not None and not (MIN_TENURE_MONTHS <= tenure <= MAX_TENURE_MONTHS):
        return Issue(
            "tenure_months",
            f"Tenure must be {MIN_TENURE_MONTHS} to {MAX_TENURE_MONTHS} months "
            "under the fictional personal-loan policy. What tenure should I use?",
        )
    purpose = loan.get("purpose")
    if purpose is not None and len(str(purpose).strip()) > 300:
        return Issue("purpose", "Please give the purpose in 300 characters or fewer.")
    return None


def collect_issues(loan: dict, today: date) -> list[Issue]:
    issues: list[Issue] = []
    kyc = personal_value(loan, "kyc_status")
    if kyc != "verified":
        issues.append(
            Issue(
                "kyc_status",
                "Your KYC is not verified, so I can't complete this application in chat.",
            )
        )
    for key in REQUIRED_PERSONAL:
        if not personal_value(loan, key):
            label = key.replace("_", " ")
            issues.append(Issue(key, f"I still need your {label}."))
    if loan.get("product_code") != "personal":
        issues.append(Issue("product", "This POC can submit a personal loan. Do you want a personal loan?"))

    bounded = range_issue(loan)
    amount = loan.get("requested_amount_paise")
    income = loan.get("monthly_income_paise")
    tenure = loan.get("tenure_months")
    if amount is None:
        issues.append(Issue("requested_amount_paise", "What personal loan amount would you like?"))
    elif bounded and bounded.field == "requested_amount_paise":
        issues.append(bounded)
    employment = loan.get("employment_type")
    if employment not in {"salaried", "self_employed"}:
        issues.append(
            Issue(
                "employment_type",
                "What is your current employment type: salaried or self-employed?",
            )
        )
    elif len(str(loan.get("employer_name") or "").strip()) < 2:
        issues.append(Issue("employer_name", "What is your employer's name?"))
    if income is None:
        issues.append(Issue("monthly_income_paise", "What is your monthly income?"))
    elif bounded and bounded.field == "monthly_income_paise":
        issues.append(bounded)
    if tenure is None:
        issues.append(
            Issue(
                "tenure_months",
                f"What loan tenure would you like, in months ({MIN_TENURE_MONTHS} to {MAX_TENURE_MONTHS})?",
            )
        )
    elif bounded and bounded.field == "tenure_months":
        issues.append(bounded)
    purpose = str(loan.get("purpose") or "").strip()
    if len(purpose) < 3:
        issues.append(Issue("purpose", "What is the purpose of this loan?"))
    elif len(purpose) > 300:
        issues.append(Issue("purpose", "Please give the purpose in 300 characters or fewer."))

    dob = personal_value(loan, "date_of_birth")
    if dob:
        try:
            born = date.fromisoformat(dob)
        except ValueError:
            issues.append(Issue("date_of_birth", "I couldn't read the date of birth on the verified profile."))
        else:
            age = age_on(born, today)
            if age < MIN_AGE or age > MAX_AGE:
                issues.append(
                    Issue(
                        "date_of_birth",
                        f"The fictional personal-loan policy requires age {MIN_AGE} to {MAX_AGE}.",
                    )
                )

    doc_type = required_doc_type(loan)
    if doc_type:
        extraction = latest_extraction(loan, doc_type)
        if not extraction:
            noun = "salary slip" if doc_type == "salary_slip" else "income tax return"
            issues.append(Issue("document", f"Please upload a {noun} as text or PDF."))
        elif not extraction.get("income_paise"):
            issues.append(
                Issue(
                    "document",
                    "I couldn't find a net monthly income on that file. Upload a text or PDF "
                    "that includes a line such as 'Net monthly income: INR 80000'.",
                )
            )
        else:
            employee = extraction.get("employee_name") or ""
            first = personal_value(loan, "first_name")
            last = personal_value(loan, "last_name")
            if employee and first and last and not names_match(employee, first, last):
                issues.append(
                    Issue(
                        "document",
                        f"The document name '{employee}' does not match the verified KYC name.",
                        review=True,
                    )
                )
            elif not employee:
                issues.append(
                    Issue(
                        "document",
                        "The document did not include an employee name, so a reviewer needs to check it.",
                        review=True,
                    )
                )
            extracted_income = int(extraction["income_paise"])
            if income and abs(income - extracted_income) / income > float(INCOME_MISMATCH_RATIO):
                issues.append(
                    Issue(
                        "monthly_income_paise",
                        "Stated monthly income "
                        f"{format_inr(income)} differs from the document amount "
                        f"{format_inr(extracted_income)} by more than 10%.",
                        review=True,
                    )
                )
            extracted_employer = extraction.get("employer_name") or ""
            stated_employer = str(loan.get("employer_name") or "")
            if extracted_employer and stated_employer and not employers_match(stated_employer, extracted_employer):
                issues.append(
                    Issue(
                        "employer_name",
                        "The employer on the document does not match the employer you stated.",
                        review=True,
                    )
                )
            if float(extraction.get("confidence") or 0) < 0.75:
                issues.append(
                    Issue(
                        "document",
                        "The document extraction is uncertain, so a reviewer needs to check it.",
                        review=True,
                    )
                )
    return issues


def blocking_issues(issues: list[Issue]) -> list[Issue]:
    return [issue for issue in issues if not issue.review]


def review_issues(issues: list[Issue]) -> list[Issue]:
    return [issue for issue in issues if issue.review]
