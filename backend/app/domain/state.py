from __future__ import annotations

import hashlib
import json

from app.core.money import format_inr
from app.domain.policy import SCHEMA_VERSION
from app.domain.validation import missing_fields, personal_value

ACTIVE_STATUSES = {
    "collecting",
    "awaiting_document",
    "pending_review",
    "awaiting_confirmation",
}
TERMINAL_STATUSES = {"submitted", "rejected", "declined"}


def new_loan_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "product_code": "unspecified",
        "requested_amount_paise": None,
        "tenure_months": None,
        "purpose": None,
        "employment_type": None,
        "employer_name": None,
        "monthly_income_paise": None,
        "personal": {},
        "consent": False,
        "expected_field": None,
        "documents": [],
        "validation_errors": [],
        "review_reasons": [],
        "review_required": False,
        "review_status": None,
        "review_notes": None,
        "approved_risk_hash": None,
        "customer_confirmed": False,
        "declarations_accepted": False,
        "workflow_status": "collecting",
        "reference": None,
        "pin_failures": 0,
    }


def risk_hash(loan: dict) -> str:
    documents = []
    for item in loan.get("documents") or []:
        extraction = item.get("extraction") or {}
        documents.append(
            {
                "id": item.get("id"),
                "income": extraction.get("income_paise"),
                "employee": extraction.get("employee_name"),
                "employer": extraction.get("employer_name"),
            }
        )
    material = {
        "amount": loan.get("requested_amount_paise"),
        "income": loan.get("monthly_income_paise"),
        "tenure": loan.get("tenure_months"),
        "employment": loan.get("employment_type"),
        "employer": loan.get("employer_name"),
        "purpose": loan.get("purpose"),
        "documents": documents,
    }
    raw = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def public_application(loan: dict, loan_id: int | None) -> dict:
    personal = {
        key: personal_value(loan, key)
        for key in (loan.get("personal") or {})
    }
    provenance = {
        key: str((meta or {}).get("source") or "unknown")
        for key, meta in (loan.get("personal") or {}).items()
    }
    amount = loan.get("requested_amount_paise")
    income = loan.get("monthly_income_paise")
    return {
        "id": loan_id,
        "schema_version": SCHEMA_VERSION,
        "status": loan.get("workflow_status"),
        "reference": loan.get("reference"),
        "product_code": loan.get("product_code"),
        "requested_amount": format_inr(amount) if amount is not None else None,
        "requested_amount_paise": amount,
        "tenure_months": loan.get("tenure_months"),
        "purpose": loan.get("purpose"),
        "employment_type": loan.get("employment_type"),
        "employer_name": loan.get("employer_name"),
        "monthly_income": format_inr(income) if income is not None else None,
        "monthly_income_paise": income,
        "personal": personal,
        "provenance": provenance,
        "missing_fields": missing_fields(loan),
        "validation_errors": list(loan.get("validation_errors") or []),
        "review_reasons": list(loan.get("review_reasons") or []),
        "review_status": loan.get("review_status"),
        "review_notes": loan.get("review_notes"),
        "expected_field": loan.get("expected_field"),
        "customer_confirmed": bool(loan.get("customer_confirmed")),
        "documents": [
            {
                "id": item.get("id"),
                "doc_type": item.get("doc_type"),
                "filename": item.get("filename"),
                "confidence": (item.get("extraction") or {}).get("confidence"),
            }
            for item in loan.get("documents") or []
        ],
    }
