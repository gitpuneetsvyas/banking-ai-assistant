from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.core.errors import DomainError, Forbidden, NotFound, Unavailable
from app.core.money import format_inr
from app.core.security import verify_secret
from app.domain.contract import assert_submittable
from app.domain.policy import public_requirements
from app.domain.state import public_application, risk_hash
from app.domain.validation import blocking_issues, collect_issues, required_doc_type, review_issues
from app.infrastructure.pdf import render_application
from app.infrastructure.repositories import (
    AccountRepository,
    AuditRepository,
    CustomerRepository,
    LoanRepository,
)
from app.rag.engine import HybridKnowledgeRetriever
from app.services.extraction import extract_fields

TOOL_NAMES = [
    "list_customer_accounts",
    "get_account_balance",
    "get_recent_transactions",
    "search_bank_knowledge",
    "get_customer_profile",
    "get_customer_kyc",
    "get_loan_requirements",
    "extract_document_fields",
    "get_loan_draft",
    "update_loan_draft",
    "validate_loan_application",
    "generate_loan_document",
    "request_human_review",
    "submit_loan_application",
]


@dataclass
class SubmitResult:
    ok: bool
    message: str
    reference: str | None = None
    already: bool = False
    saved: bool = False


class BankingTools:
    """Authorised tool facade. Customer identity comes from the session, never from model text."""

    def __init__(self, session: Session, customer, settings: Settings, retriever: HybridKnowledgeRetriever) -> None:
        self.session = session
        self.customer = customer
        self.settings = settings
        self.retriever = retriever
        self.customers = CustomerRepository(session)
        self.accounts = AccountRepository(session)
        self.loans = LoanRepository(session)
        self.audit_repo = AuditRepository(session)
        self.trace: list[dict] = []
        self.calls = 0

    def list_customer_accounts(self) -> list[dict]:
        self._tick("list_customer_accounts")
        rows = self.accounts.list_for_customer(self.customer.id)
        self._audit("account.list", "ok", {"count": len(rows)})
        return [self._public_account(row) for row in rows]

    def get_account_balance(self, account_hint: str | None = None, kind: str = "available") -> dict:
        self._tick("get_account_balance", kind)
        self._require_accounts("balance")
        matches = self._match(account_hint)
        if account_hint and not matches:
            self._audit("account.balance", "denied", {"hint": account_hint})
            return {
                "type": "not_found",
                "reply": (
                    "I can't find that account on your profile. "
                    "I can only access accounts for the signed-in customer."
                ),
            }
        if len(matches) != 1:
            self._audit("account.balance", "clarify", {"count": len(matches)})
            return {"type": "clarify", "reply": _clarification(matches), "kind": kind}
        account = matches[0]
        return self._balance_payload(account, kind)

    def get_balance_for_account(self, account_id: int, kind: str = "available") -> dict:
        self._tick("get_account_balance", "by-id")
        self._require_accounts("balance")
        account = self.accounts.get(account_id)
        if account is None:
            raise NotFound("Account not found")
        if account.customer_id != self.customer.id:
            self._audit("account.balance", "denied", {"account_id": account_id})
            raise Forbidden("You cannot access another customer's account.")
        payload = self._balance_payload(account, kind)
        payload.pop("reply", None)
        return payload

    def get_recent_transactions(self, account_hint: str | None = None, limit: int = 5) -> dict:
        self._tick("get_recent_transactions")
        self._require_accounts("transactions")
        capped = max(1, min(int(limit or 5), 10))
        matches = self._match(account_hint)
        if account_hint and not matches:
            self._audit("account.transactions", "denied", {"hint": account_hint})
            return {
                "type": "not_found",
                "reply": "I can't find that account on your profile.",
            }
        if len(matches) != 1:
            self._audit("account.transactions", "clarify", {"count": len(matches)})
            return {"type": "clarify", "reply": _clarification(matches)}
        account = matches[0]
        rows = self.accounts.transactions(account.id, capped)
        parts = [
            f"{row.posted_on} {row.direction} {format_inr(row.amount_paise)} {row.description}"
            for row in rows
        ]
        ending = account.account_number[-4:]
        reply = (
            f"Recent transactions on {account.account_type} ending {ending}: "
            + ("; ".join(parts) if parts else "none are posted.")
        )
        self._audit("account.transactions", "ok", {"ending": ending, "count": len(rows)})
        return {"type": "transactions", "reply": reply}

    def search_bank_knowledge(self, query: str) -> list[dict]:
        self._tick("search_bank_knowledge")
        documents = self.retriever.invoke(query[:1000])
        self._audit("knowledge.search", "ok", {"hits": len(documents)})
        return [
            {
                "doc_id": document.metadata.get("doc_id"),
                "title": document.metadata.get("title"),
                "version": document.metadata.get("version"),
                "product": document.metadata.get("product"),
                "text": document.page_content,
            }
            for document in documents
        ]

    def get_customer_profile(self) -> dict:
        self._tick("get_customer_profile")
        profile = self.customers.profile(self.customer.id)
        if profile is None:
            raise NotFound("Verified profile not found")
        self._audit("profile.read", "ok", {"purpose": "loan_prefill"})
        hidden = {"aadhaar_masked", "verified_at"}
        return {key: value for key, value in profile.items() if key not in hidden}

    def get_customer_kyc(self) -> dict:
        self._tick("get_customer_kyc")
        profile = self.customers.profile(self.customer.id)
        if profile is None:
            raise NotFound("KYC profile not found")
        self._audit("kyc.read", "ok", {})
        return {
            "kyc_status": profile["kyc_status"],
            "date_of_birth": profile["date_of_birth"],
            "pan_masked": profile["pan_masked"],
            "verified_at": profile["verified_at"],
        }

    def get_loan_requirements(self) -> dict:
        self._tick("get_loan_requirements")
        self._audit("loan.requirements", "ok", {})
        return public_requirements()

    def extract_document_fields(self, filename: str, data: bytes) -> dict:
        self._tick("extract_document_fields")
        extraction = extract_fields(filename, data)
        self._audit("document.extract", "ok", {"confidence": extraction.confidence})
        return extraction.model_dump()

    def get_loan_draft(self) -> dict | None:
        self._tick("get_loan_draft")
        row = self.loans.get_open(self.customer.id)
        if row is None:
            return None
        return public_application(payload_from(row), row.id)

    def update_loan_draft(self, loan_id: int, payload: dict) -> dict:
        self._tick("update_loan_draft", payload.get("workflow_status") or "")
        row = self._owned(loan_id)
        if row.status == "submitted":
            return public_application(payload_from(row), row.id)
        self.loans.save(row, payload)
        self._audit("loan.draft.update", "ok", {"status": payload.get("workflow_status")})
        return public_application(payload, row.id)

    def validate_loan_application(self, payload: dict) -> dict:
        self._tick("validate_loan_application")
        issues = collect_issues(payload, clock.today())
        self._audit(
            "loan.validate",
            "ok",
            {"errors": len(blocking_issues(issues)), "reviews": len(review_issues(issues))},
        )
        return {
            "errors": [issue.message for issue in blocking_issues(issues)],
            "reviews": [issue.message for issue in review_issues(issues)],
        }

    def generate_loan_document(self, loan_id: int, payload: dict) -> str:
        self._tick("generate_loan_document")
        self._owned(loan_id)
        from app.domain.contract import build_contract

        try:
            contract = build_contract(payload)
        except ValidationError as exc:
            raise DomainError("The application is not complete enough to generate the document.") from exc
        path = self._pdf_path(loan_id)
        render_application(contract, path)
        payload["pdf_ready"] = True
        self._audit("loan.document.generated", "ok", {"loan_id": loan_id})
        return path.name

    def request_human_review(self, loan_id: int, reasons: list[str]) -> None:
        self._tick("request_human_review")
        self._owned(loan_id)
        self._audit("loan.review.requested", "ok", {"reasons": len(reasons)})

    def submit_loan_application(self, loan_id: int, pin: str) -> SubmitResult:
        self._tick("submit_loan_application")
        row = self._owned(loan_id)
        if row.status == "submitted":
            self._audit("loan.submitted", "already_submitted", {"reference": row.reference})
            return SubmitResult(
                True,
                f"This application was already submitted. Reference {row.reference}.",
                row.reference,
                already=True,
                saved=True,
            )
        payload = payload_from(row)
        if not verify_secret(pin, self.customer.pin_salt, self.customer.pin_hash):
            payload["pin_failures"] = int(payload.get("pin_failures") or 0) + 1
            self.loans.save(row, payload)
            self._audit("loan.submitted", "denied", {"reason": "pin"})
            if payload["pin_failures"] >= 5:
                return SubmitResult(False, "Too many PIN attempts. Sign in again before submitting.", saved=True)
            return SubmitResult(False, "That PIN doesn't match. The application was not submitted.", saved=True)
        if row.status != "awaiting_confirmation":
            return SubmitResult(False, "The application is not ready to submit.", saved=False)
        issues = collect_issues(payload, clock.today())
        if blocking_issues(issues):
            return SubmitResult(False, blocking_issues(issues)[0].message, saved=False)
        if review_issues(issues) and not _review_covers(payload):
            return SubmitResult(False, "A reviewer still needs to approve this application.", saved=False)
        payload["customer_confirmed"] = True
        payload["declarations_accepted"] = True
        payload["validation_errors"] = []
        try:
            assert_submittable(payload)
        except (ValueError, ValidationError):
            return SubmitResult(False, "The application failed final validation and was not submitted.", saved=False)
        reference = f"HB-PL-{row.id:04d}"
        updated = self.loans.mark_submitted(row, payload, reference)
        if not updated:
            self.session.refresh(row)
            if row.status == "submitted":
                return SubmitResult(
                    True,
                    f"This application was already submitted. Reference {row.reference}.",
                    row.reference,
                    already=True,
                    saved=True,
                )
            return SubmitResult(False, "The application is not ready to submit.", saved=False)
        self.session.refresh(row)
        final_payload = payload_from(row)
        self._write_pdf(row.id, final_payload)
        self._audit("loan.submitted", "ok", {"reference": reference})
        return SubmitResult(
            True,
            f"Your personal loan application has been submitted. Reference {reference}.",
            reference,
            saved=True,
        )

    def save_uploaded_document(self, loan_id: int, filename: str, data: bytes) -> dict:
        if len(data) > 2_000_000:
            raise DomainError("That file is larger than 2 MB.")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".txt", ".md", ".pdf"}:
            raise DomainError("Upload a text or PDF document. This POC cannot read photographs.")
        row = self._owned(loan_id)
        payload = payload_from(row)
        doc_type = required_doc_type(payload) or "supporting"
        extraction = self.extract_document_fields(filename, data)
        digest = hashlib.sha256(data).hexdigest()
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:80]
        path = self.settings.upload_dir / f"{loan_id}_{digest[:8]}_{safe}"
        path.write_bytes(data)
        document = self.loans.add_document(
            application_id=row.id,
            customer_id=self.customer.id,
            doc_type=doc_type,
            filename=safe,
            storage_path=str(path),
            sha256=digest,
            extraction_json=json.dumps(extraction),
            confidence=int(float(extraction["confidence"]) * 100),
        )
        payload.setdefault("documents", []).append(
            {
                "id": document.id,
                "doc_type": doc_type,
                "filename": safe,
                "extraction": extraction,
            }
        )
        self.loans.save(row, payload)
        self._audit("document.stored", "ok", {"doc_type": doc_type})
        return extraction

    def record_consent(self, loan_id: int) -> None:
        from app.infrastructure.models import Consent
        from app.core.clock import utcnow

        self.session.add(
            Consent(
                customer_id=self.customer.id,
                application_id=loan_id,
                purpose="loan_profile_prefill",
                granted=True,
                created_at=utcnow(),
            )
        )
        self.session.flush()
        self._audit("consent.granted", "ok", {"purpose": "loan_profile_prefill"})

    def decide_review(self, loan_id: int, decision: str, notes: str) -> dict:
        if self.customer.role != "reviewer":
            raise Forbidden("Only a reviewer can record this decision.")
        row = self.loans.get(loan_id)
        if row is None:
            raise NotFound("Application not found")
        if row.customer_id == self.customer.id:
            raise Forbidden("You cannot review your own application.")
        if row.status != "pending_review":
            raise DomainError("This application is not waiting for review.")
        if decision not in {"approve", "reject", "request_info"}:
            raise DomainError("Decision must be approve, reject, or request_info.")
        payload = payload_from(row)
        self.loans.add_review(row.id, self.customer.id, decision, notes)
        if decision == "approve":
            payload["review_status"] = "approved"
            payload["approved_risk_hash"] = risk_hash(payload)
            payload["workflow_status"] = "awaiting_confirmation"
            payload["expected_field"] = "confirmation"
        elif decision == "reject":
            payload["review_status"] = "rejected"
            payload["workflow_status"] = "rejected"
        else:
            payload["review_status"] = "info_requested"
            payload["workflow_status"] = "collecting"
            payload["expected_field"] = "monthly_income_paise"
        payload["review_notes"] = notes
        self.loans.save(row, payload)
        self._audit("loan.review.decided", decision, {"loan_id": loan_id})
        return public_application(payload, row.id)

    def _write_pdf(self, loan_id: int, payload: dict) -> None:
        from app.domain.contract import build_contract

        contract = build_contract(payload)
        render_application(contract, self._pdf_path(loan_id))

    def _pdf_path(self, loan_id: int) -> Path:
        return self.settings.pdf_dir / f"application-{loan_id}.pdf"

    def _owned(self, loan_id: int):
        row = self.loans.get(loan_id)
        if row is None or row.customer_id != self.customer.id:
            raise NotFound("Application not found")
        return row

    def _require_accounts(self, what: str = "balance") -> None:
        if not self.settings.accounts_enabled:
            self._audit(f"account.{what}", "unavailable", {})
            noun = "balance" if what == "balance" else "transactions"
            raise Unavailable(
                f"The account service is unavailable, so I can't give you a {noun}. I won't estimate one."
            )

    def _match(self, hint: str | None):
        rows = self.accounts.list_for_customer(self.customer.id)
        if not hint:
            return rows
        if hint in {"savings", "current"}:
            return [row for row in rows if row.account_type == hint]
        if re.fullmatch(r"\d{4}", hint):
            return [row for row in rows if row.account_number.endswith(hint)]
        return []

    def _balance_payload(self, account, kind: str) -> dict:
        use_ledger = kind == "ledger"
        amount = account.ledger_balance_paise if use_ledger else account.available_balance_paise
        label = "ledger" if use_ledger else "available"
        ending = account.account_number[-4:]
        self._audit("account.balance", "ok", {"ending": ending, "kind": label})
        return {
            "type": "balance",
            "reply": (
                f"Your {label} {account.account_type} account balance is {format_inr(amount)}, "
                f"according to the latest account-service response. Account ending {ending}."
            ),
            "amount_paise": amount,
            "account_ending": ending,
            "account_type": account.account_type,
            "balance_kind": label,
            "currency": account.currency,
        }

    def _public_account(self, account) -> dict:
        return {
            "id": account.id,
            "account_type": account.account_type,
            "account_ending": account.account_number[-4:],
            "currency": account.currency,
            "status": account.status,
        }

    def _tick(self, name: str, detail: str = "") -> None:
        if name not in TOOL_NAMES:
            raise DomainError("Unknown tool.")
        if self.calls >= 12:
            raise DomainError("Tool execution limit reached for this turn.")
        self.calls += 1
        self.trace.append({"name": name, "ok": True, "detail": detail})

    def _audit(self, action: str, outcome: str, metadata: dict) -> None:
        self.audit_repo.add(self.customer.customer_ref, action, action, outcome, metadata)


def payload_from(row) -> dict:
    payload = json.loads(row.payload_json)
    payload["workflow_status"] = row.status
    payload["review_status"] = row.review_status
    payload["review_notes"] = row.review_notes
    payload["approved_risk_hash"] = row.approved_risk_hash
    payload["customer_confirmed"] = row.customer_confirmed
    payload["reference"] = row.reference
    if row.product_code:
        payload["product_code"] = row.product_code
    return payload


def _review_covers(payload: dict) -> bool:
    return payload.get("review_status") == "approved" and payload.get("approved_risk_hash") == risk_hash(payload)


def _clarification(accounts) -> str:
    parts = [f"{row.account_type.capitalize()} ending {row.account_number[-4:]}" for row in accounts]
    if len(parts) == 2:
        return f"You have two accounts: {parts[0]} and {parts[1]}. Which would you like to check?"
    listed = ", ".join(parts)
    return f"You have {len(parts)} accounts: {listed}. Which would you like to check?"
