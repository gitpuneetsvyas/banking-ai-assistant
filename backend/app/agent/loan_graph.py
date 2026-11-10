from __future__ import annotations

import copy
import re
from datetime import date
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.copy import ask, paused, ready
from app.core.money import parse_amounts
from app.domain.contract import REQUIRED_PERSONAL
from app.domain.state import risk_hash
from app.domain.validation import (
    blocking_issues,
    collect_issues,
    next_missing,
    personal_value,
    range_issue,
    review_issues,
)


class GraphState(TypedDict, total=False):
    loan: dict
    profile: dict | None
    interpretation: dict
    user_message: str
    event: str
    provided_pin: str | None
    confirm_requested: bool
    prior_risk_hash: str
    today: str
    home_turn: bool
    assistant_message: str
    action: str
    route: str
    steps: int


def compile_loan_graph():
    graph = StateGraph(GraphState)
    graph.add_node("merge", _merge)
    graph.add_node("consent", _consent)
    graph.add_node("profile", _profile)
    graph.add_node("advance", _advance)
    graph.add_node("validate", _validate)
    graph.add_node("submit", _submit)
    graph.set_entry_point("merge")
    graph.add_conditional_edges("merge", lambda state: state["route"], {"consent": "consent", "end": END})
    graph.add_conditional_edges("consent", lambda state: state["route"], {"profile": "profile", "end": END})
    graph.add_edge("profile", "advance")
    graph.add_conditional_edges(
        "advance",
        lambda state: state["route"],
        {"validate": "validate", "submit": "submit", "end": END},
    )
    graph.add_edge("validate", END)
    graph.add_edge("submit", END)
    return graph.compile()


def _finish(state: GraphState, loan: dict, message: str, action: str = "ask") -> GraphState:
    return {
        **state,
        "loan": loan,
        "assistant_message": message,
        "action": action,
        "route": "end",
    }


def _merge(state: GraphState) -> GraphState:
    loan = copy.deepcopy(state["loan"])
    if state.get("event") == "document_uploaded":
        return {**state, "loan": loan, "route": "consent", "home_turn": False}
    interp = state.get("interpretation") or {}
    message = (state.get("user_message") or "").strip()
    expected = loan.get("expected_field")
    if interp.get("requested_amount_paise"):
        loan["requested_amount_paise"] = interp["requested_amount_paise"]
    if interp.get("monthly_income_paise"):
        loan["monthly_income_paise"] = interp["monthly_income_paise"]
    if interp.get("tenure_months"):
        loan["tenure_months"] = interp["tenure_months"]
    if interp.get("employment_type"):
        loan["employment_type"] = interp["employment_type"]
    if interp.get("employer_name"):
        loan["employer_name"] = interp["employer_name"]
    if interp.get("purpose"):
        loan["purpose"] = interp["purpose"]
    if interp.get("product_code") == "personal":
        loan["product_code"] = "personal"
    if expected == "product" and (
        interp.get("affirmative") or re.search(r"\bpersonal\b", message, re.I)
    ):
        loan["product_code"] = "personal"
    if message and expected == "monthly_income_paise" and loan.get("monthly_income_paise") is None:
        amounts = parse_amounts(message) or parse_amounts(message, allow_bare=True)
        if len(amounts) == 1:
            loan["monthly_income_paise"] = amounts[0]
    if message and expected == "requested_amount_paise" and not interp.get("requested_amount_paise"):
        amounts = parse_amounts(message) or parse_amounts(message, allow_bare=True)
        if len(amounts) == 1:
            loan["requested_amount_paise"] = amounts[0]
    if message and expected == "tenure_months" and loan.get("tenure_months") is None:
        if re.fullmatch(r"\d{1,3}", message):
            loan["tenure_months"] = int(message)
    if (
        message
        and expected == "purpose"
        and not loan.get("purpose")
        and not interp.get("affirmative")
        and not interp.get("negative")
        and len(message) >= 3
    ):
        loan["purpose"] = message.strip(" .")
    if (
        message
        and expected == "employer_name"
        and not loan.get("employer_name")
        and not interp.get("employment_type")
        and not parse_amounts(message)
        and not interp.get("affirmative")
        and len(message) >= 2
    ):
        loan["employer_name"] = message.strip(" .")
    if message and expected in REQUIRED_PERSONAL and not personal_value(loan, expected):
        personal = dict(loan.get("personal") or {})
        personal[expected] = {"value": message.strip(), "source": "customer_statement", "verified": False}
        loan["personal"] = personal
    home_turn = interp.get("product_code") == "home"
    return {**state, "loan": loan, "route": "consent", "home_turn": home_turn}


def _consent(state: GraphState) -> GraphState:
    loan = copy.deepcopy(state["loan"])
    interp = state.get("interpretation") or {}
    if loan.get("consent"):
        return {**state, "loan": loan, "route": "profile"}
    if interp.get("cancel") or interp.get("negative"):
        loan["workflow_status"] = "declined"
        loan["expected_field"] = None
        return _finish(state, loan, "I've stopped this application. Nothing was submitted.")
    if interp.get("affirmative"):
        loan["consent"] = True
        loan["expected_field"] = None
        return {**state, "loan": loan, "route": "profile"}
    loan["workflow_status"] = "collecting"
    loan["expected_field"] = "consent"
    return _finish(state, loan, ask("consent", loan))


def _profile(state: GraphState) -> GraphState:
    loan = copy.deepcopy(state["loan"])
    profile = state.get("profile") or {}
    if profile and not loan.get("personal"):
        personal = {}
        for key, value in profile.items():
            if key in {"customer_ref", "aadhaar_masked", "verified_at"}:
                continue
            personal[key] = {
                "value": value or "",
                "source": "kyc",
                "verified": bool(value) and profile.get("kyc_status") == "verified",
            }
        loan["personal"] = personal
    return {**state, "loan": loan}


def _advance(state: GraphState) -> GraphState:
    loan = copy.deepcopy(state["loan"])
    interp = state.get("interpretation") or {}
    if interp.get("cancel"):
        loan["workflow_status"] = "declined"
        loan["expected_field"] = None
        return _finish(state, loan, "I've cancelled this draft. Nothing was submitted.")
    if loan.get("review_status") == "rejected" or loan.get("workflow_status") == "rejected":
        return _finish(state, loan, "A reviewer rejected this application. Nothing was submitted.")
    if state.get("home_turn") and loan.get("product_code") != "personal":
        loan["expected_field"] = "product"
        return _finish(
            state,
            loan,
            "I can't submit a home loan in this POC. I can still prepare a personal loan. Do you want a personal loan?",
        )
    bounded = range_issue(loan)
    if loan.get("consent") and bounded:
        loan["expected_field"] = bounded.field
        loan["workflow_status"] = "collecting"
        return _finish(state, loan, bounded.message)
    if loan.get("review_status") == "info_requested" and not _changed(state, loan):
        loan["workflow_status"] = "collecting"
        loan["expected_field"] = loan.get("expected_field") or "monthly_income_paise"
        notes = loan.get("review_notes") or "Please correct the flagged details."
        return _finish(state, loan, f"A reviewer needs more information: {notes}")
    if loan.get("workflow_status") == "pending_review" and loan.get("review_status") != "approved":
        return _finish(
            state,
            loan,
            "This application is paused for a reviewer. I'll continue when they record a decision.",
        )
    missing = next_missing(loan)
    if missing:
        loan["expected_field"] = missing
        loan["workflow_status"] = "awaiting_document" if missing == "document" else "collecting"
        return _finish(state, loan, ask(missing, loan))
    if loan.get("workflow_status") == "awaiting_confirmation" or loan.get("expected_field") == "confirmation":
        if _changed(state, loan):
            return {**state, "loan": loan, "route": "validate"}
        if interp.get("negative") and not state.get("confirm_requested"):
            return _finish(
                state,
                loan,
                "I have not submitted the application. The draft is still here if you want to review it.",
            )
        if state.get("provided_pin") and (interp.get("affirmative") or state.get("confirm_requested")):
            return {**state, "loan": loan, "route": "submit"}
        loan["expected_field"] = "confirmation"
        loan["workflow_status"] = "awaiting_confirmation"
        return _finish(state, loan, ready(loan))
    return {**state, "loan": loan, "route": "validate"}


def _validate(state: GraphState) -> GraphState:
    loan = copy.deepcopy(state["loan"])
    today = date.fromisoformat(state["today"])
    issues = collect_issues(loan, today)
    blocking = blocking_issues(issues)
    reviews = review_issues(issues)
    loan["validation_errors"] = [issue.message for issue in blocking]
    loan["review_reasons"] = [issue.message for issue in reviews]
    if blocking:
        loan["expected_field"] = blocking[0].field
        loan["workflow_status"] = "awaiting_document" if blocking[0].field == "document" else "collecting"
        return _finish(state, loan, blocking[0].message)
    covered = (
        loan.get("review_status") == "approved" and loan.get("approved_risk_hash") == risk_hash(loan)
    )
    if reviews and not covered:
        loan["review_required"] = True
        loan["review_status"] = "pending"
        loan["workflow_status"] = "pending_review"
        loan["expected_field"] = None
        loan["approved_risk_hash"] = None
        return _finish(state, loan, paused(loan["review_reasons"]), action="draft_pdf")
    loan["review_required"] = bool(reviews)
    loan["workflow_status"] = "awaiting_confirmation"
    loan["expected_field"] = "confirmation"
    return _finish(state, loan, ready(loan), action="draft_pdf")


def _submit(state: GraphState) -> GraphState:
    loan = copy.deepcopy(state["loan"])
    if not state.get("provided_pin"):
        return _finish(
            state,
            loan,
            "Confirmation needs your transaction PIN. I have not submitted the application.",
        )
    return {**state, "loan": loan, "action": "submit", "route": "end", "assistant_message": ""}


def _changed(state: GraphState, loan: dict) -> bool:
    if state.get("event") == "document_uploaded":
        return True
    prior = state.get("prior_risk_hash")
    return bool(prior) and prior != risk_hash(loan)
