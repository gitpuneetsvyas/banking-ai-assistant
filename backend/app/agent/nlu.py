from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.core.money import parse_amounts, parse_tenure_months
from app.domain.state import ACTIVE_STATUSES

_YES = re.compile(
    r"^(yes|y|yeah|yep|ok|okay|sure|i agree|i consent|go ahead|please do|use my profile|you may)\b",
    re.IGNORECASE,
)
_NO = re.compile(r"^(no|nope|don't|do not|stop there)\b", re.IGNORECASE)
_CANCEL = re.compile(r"\b(cancel|stop)( the| this)?( application| loan)?\b", re.IGNORECASE)
_CONFIRM = re.compile(
    r"\b(i confirm|confirm submission|please submit|submit it|submit the application|i authorise|i authorize)\b",
    re.IGNORECASE,
)


class Interpretation(BaseModel):
    intent: str
    product_code: str | None = None
    employment_type: str | None = None
    employer_name: str | None = None
    purpose: str | None = None
    tenure_months: int | None = None
    requested_amount_paise: int | None = None
    monthly_income_paise: int | None = None
    account_hint: str | None = None
    balance_kind: str = "available"
    affirmative: bool = False
    negative: bool = False
    cancel: bool = False
    slots: dict = Field(default_factory=dict)


def interpret(text: str, loan: dict | None = None) -> Interpretation:
    cleaned = text.strip()
    expected = (loan or {}).get("expected_field")
    affirmative = bool(_YES.search(cleaned)) or bool(_CONFIRM.search(cleaned))
    negative = bool(_NO.search(cleaned))
    cancel = bool(cleaned) and bool(_CANCEL.search(cleaned)) and cleaned.lower() not in {"no", "nope"}
    if cleaned.lower() in {"cancel", "stop"}:
        cancel = True
    product = _product(cleaned)
    employment = _employment(cleaned)
    data = Interpretation(
        intent="unknown",
        product_code=product,
        employment_type=employment,
        employer_name=_employer(cleaned),
        purpose=_purpose(cleaned),
        tenure_months=parse_tenure_months(cleaned),
        requested_amount_paise=_loan_amount(cleaned),
        monthly_income_paise=_income_amount(cleaned),
        account_hint=_account_hint(cleaned),
        balance_kind="ledger" if re.search(r"\bledger\b", cleaned, re.I) else "available",
        affirmative=affirmative,
        negative=negative,
        cancel=cancel,
    )
    if cancel:
        data.intent = "deny"
        return data
    if expected == "consent" and affirmative:
        data.intent = "confirm"
        return data
    if expected == "consent" and negative:
        data.intent = "deny"
        return data
    if expected == "confirmation" and (affirmative or _CONFIRM.search(cleaned)):
        data.intent = "confirm"
        data.affirmative = True
        return data
    if expected == "confirmation" and negative:
        data.intent = "deny"
        return data
    if re.search(r"\b(balance|how much money|how much do i have)\b", cleaned, re.I):
        data.intent = "balance"
        return data
    if re.search(r"\btransactions?\b", cleaned, re.I):
        data.intent = "transactions"
        return data
    if re.search(r"\b(application status|reference number|application reference|status of my application)\b", cleaned, re.I):
        data.intent = "loan_status"
        return data
    if re.search(r"\bhow (do|can|to) i apply\b", cleaned, re.I):
        data.intent = "knowledge"
        return data
    if _is_application(cleaned):
        data.intent = "loan_application"
        # This POC submits personal loans. An application that does not say "home loan"
        # is a personal loan, so "a ₹5 lakh loan" does not stall on a product question.
        if data.product_code is None:
            data.product_code = "personal"
        return data
    if re.search(
        r"\b(documents?|eligib\w*|prepay\w*|foreclos\w*|fees?|charges?|emis?|instal\w*|interest|polic(?:y|ies)|difference|savings account|current account|repay\w*)\b",
        cleaned,
        re.I,
    ):
        data.intent = "knowledge"
        return data
    if loan and loan.get("workflow_status") in ACTIVE_STATUSES:
        data.intent = "continue"
    return data


def loan_for_situation(situation: str) -> dict | None:
    if situation == "none":
        return None
    loan = {
        "consent": situation != "consent",
        "expected_field": {"consent": "consent", "confirmation": "confirmation", "collecting": "employment_type"}.get(
            situation
        ),
        "workflow_status": "awaiting_confirmation" if situation == "confirmation" else "collecting",
        "product_code": "personal",
    }
    return loan


def _is_application(text: str) -> bool:
    # A question about a loan is not an application, even when it contains "I need".
    if re.search(r"\b(what|which|who|when|where|why|how)\b", text, re.I):
        return False
    has_loan = re.search(r"\bloan\b", text, re.I)
    has_start = re.search(
        r"\b(apply for|loan application|i want|i need|i would like|start a loan|help me (get|with) a loan)\b",
        text,
        re.I,
    )
    return bool(has_loan and has_start)


def _product(text: str) -> str | None:
    home = re.search(r"\bhome loan\b", text, re.I)
    personal = re.search(r"\bpersonal loan\b", text, re.I)
    if home and not personal:
        return "home"
    if personal:
        return "personal"
    return None


def _employment(text: str) -> str | None:
    if re.search(r"\bself[-\s]?employed\b", text, re.I):
        return "self_employed"
    if re.search(r"\bsalaried\b", text, re.I):
        return "salaried"
    return None


def _employer(text: str) -> str | None:
    match = re.search(
        r"\b(?:employer(?: name)?(?: is|:)|(?:employed|working|salaried) (?:at|with|by))\s+(.+)$",
        text,
        re.I,
    )
    if not match:
        return None
    value = re.split(r"\b(income|purpose|tenure|monthly)\b", match.group(1), maxsplit=1, flags=re.I)[0]
    return value.strip(" .,;") or None


def _purpose(text: str) -> str | None:
    match = re.search(r"\bpurpose(?: is| of|:)?\s+(.+)$", text, re.I)
    if not match:
        return None
    return match.group(1).strip(" .,;") or None


def _loan_amount(text: str) -> int | None:
    match = re.search(r"\bloan of\b(.{0,48})", text, re.I)
    if match:
        amounts = parse_amounts(match.group(0), allow_bare=True)
        if amounts:
            return amounts[0]
    if re.search(r"\b(lakh|lakhs|lac|crore|crores)\b", text, re.I) and re.search(r"\bloan\b", text, re.I):
        amounts = parse_amounts(text)
        if amounts:
            return amounts[0]
    if re.search(r"\b(loan amount|amount is|amount of)\b", text, re.I):
        amounts = parse_amounts(text, allow_bare=True)
        if amounts:
            return amounts[0]
    return None


def _income_amount(text: str) -> int | None:
    if not re.search(r"\b(income|salary|per month|a month)\b", text, re.I):
        return None
    amounts = parse_amounts(text, allow_bare=True)
    return amounts[-1] if amounts else None


def _account_hint(text: str) -> str | None:
    if re.search(r"\bsavings?\b", text, re.I):
        return "savings"
    if re.search(r"\bcurrent\b", text, re.I):
        return "current"
    match = re.search(r"\bending\s+(\d{4})\b", text, re.I)
    if match:
        return match.group(1)
    return None


def extract_pin(message: str, expected: str | None) -> str | None:
    labelled = re.search(r"\b(?:pin|txn pin|transaction pin)\D{0,8}(\d{4})\b", message, re.I)
    if labelled:
        return labelled.group(1)
    trailing = re.search(r"\b(?:confirm|submit)\b.*\b(\d{4})\b", message, re.I)
    if trailing:
        return trailing.group(1)
    if expected == "confirmation" and re.fullmatch(r"\d{4}", message.strip()):
        return message.strip()
    return None
