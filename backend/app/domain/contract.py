"""Replaceable POC loan contract.

The repository had no existing three-form schema. `poc-loan-v1` is an explicit
stand-in: personal/KYC, employment and loan terms, then review and submission.
A later adapter can map these fields onto a real core-banking payload without
changing the conversation graph.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.policy import (
    MAX_TENURE_MONTHS,
    MIN_TENURE_MONTHS,
    SCHEMA_VERSION,
)

REQUIRED_PERSONAL = (
    "first_name",
    "last_name",
    "date_of_birth",
    "email",
    "phone",
    "address_line",
    "city",
    "state",
    "postal_code",
)


class PersonalKycForm(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    date_of_birth: str = Field(min_length=10, max_length=10)
    email: str = Field(min_length=3)
    phone: str = Field(min_length=8)
    address_line: str = Field(min_length=3)
    city: str = Field(min_length=2)
    state: str = Field(min_length=2)
    postal_code: str = Field(min_length=4)
    pan_masked: str = ""
    kyc_status: Literal["verified"]


class EmploymentLoanForm(BaseModel):
    employment_type: Literal["salaried", "self_employed"]
    employer_name: str = Field(min_length=2, max_length=200)
    monthly_income_paise: int = Field(gt=0)
    loan_product: Literal["personal"]
    requested_amount_paise: int = Field(gt=0)
    tenure_months: int = Field(ge=MIN_TENURE_MONTHS, le=MAX_TENURE_MONTHS)
    purpose: str = Field(min_length=3, max_length=300)
    document_ids: list[int] = Field(min_length=1)


class ReviewSubmitForm(BaseModel):
    declarations_accepted: bool
    customer_confirmed: bool
    review_required: bool
    reviewer_status: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


class LoanApplicationContract(BaseModel):
    schema_version: Literal["poc-loan-v1"] = SCHEMA_VERSION
    personal_kyc: PersonalKycForm
    employment_loan: EmploymentLoanForm
    review_submit: ReviewSubmitForm
    provenance: dict[str, str]


def _value(loan: dict, key: str) -> str:
    meta = (loan.get("personal") or {}).get(key) or {}
    return str(meta.get("value") or "").strip()


def build_contract(loan: dict) -> LoanApplicationContract:
    personal = {key: _value(loan, key) for key in (*REQUIRED_PERSONAL, "pan_masked", "kyc_status")}
    documents = loan.get("documents") or []
    document_ids = [int(item["id"]) for item in documents if item.get("id") is not None]
    provenance = {
        key: str((meta or {}).get("source") or "unknown")
        for key, meta in (loan.get("personal") or {}).items()
    }
    provenance["requested_amount_paise"] = "customer_statement"
    provenance["monthly_income_paise"] = "customer_statement"
    provenance["employment_type"] = "customer_statement"
    provenance["employer_name"] = "customer_statement"
    provenance["tenure_months"] = "customer_statement"
    provenance["purpose"] = "customer_statement"
    if documents:
        provenance["supporting_document"] = str(documents[-1].get("doc_type") or "upload")
    return LoanApplicationContract(
        personal_kyc=PersonalKycForm(**personal),
        employment_loan=EmploymentLoanForm(
            employment_type=loan.get("employment_type"),
            employer_name=str(loan.get("employer_name") or "").strip(),
            monthly_income_paise=loan.get("monthly_income_paise"),
            loan_product="personal",
            requested_amount_paise=loan.get("requested_amount_paise"),
            tenure_months=loan.get("tenure_months"),
            purpose=str(loan.get("purpose") or "").strip(),
            document_ids=document_ids,
        ),
        review_submit=ReviewSubmitForm(
            declarations_accepted=bool(loan.get("declarations_accepted")),
            customer_confirmed=bool(loan.get("customer_confirmed")),
            review_required=bool(loan.get("review_required")),
            reviewer_status=loan.get("review_status"),
            validation_errors=list(loan.get("validation_errors") or []),
            review_reasons=list(loan.get("review_reasons") or []),
        ),
        provenance=provenance,
    )


def assert_submittable(loan: dict) -> LoanApplicationContract:
    contract = build_contract(loan)
    review = contract.review_submit
    if review.validation_errors:
        raise ValueError("Application still has validation errors")
    if not review.customer_confirmed or not review.declarations_accepted:
        raise ValueError("Customer confirmation is required")
    if review.review_required and review.reviewer_status != "approved":
        raise ValueError("A reviewer decision is required")
    return contract
