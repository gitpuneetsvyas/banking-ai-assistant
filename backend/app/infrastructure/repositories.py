from __future__ import annotations

import json

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import NotFound
from app.domain.policy import SCHEMA_VERSION
from app.domain.state import new_loan_state
from app.infrastructure.models import (
    Account,
    AuditEvent,
    Checkpoint,
    Consent,
    Customer,
    Document,
    KnowledgeChunk,
    KycProfile,
    LoanApplication,
    Message,
    Review,
    Transaction,
)


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> Customer | None:
        return self.session.scalar(select(Customer).where(Customer.email == email.casefold()))

    def get(self, customer_id: int) -> Customer | None:
        return self.session.get(Customer, customer_id)

    def profile(self, customer_id: int) -> dict | None:
        customer = self.get(customer_id)
        kyc = self.session.get(KycProfile, customer_id)
        if customer is None or kyc is None:
            return None
        return {
            "customer_ref": customer.customer_ref,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "date_of_birth": kyc.date_of_birth,
            "email": kyc.email,
            "phone": kyc.phone,
            "address_line": kyc.address_line,
            "city": kyc.city,
            "state": kyc.state,
            "postal_code": kyc.postal_code,
            "pan_masked": kyc.pan_masked,
            "aadhaar_masked": kyc.aadhaar_masked,
            "kyc_status": kyc.kyc_status,
            "verified_at": kyc.verified_at,
        }


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_customer(self, customer_id: int) -> list[Account]:
        rows = self.session.scalars(
            select(Account).where(Account.customer_id == customer_id, Account.status == "active")
        ).all()
        return sorted(rows, key=lambda row: (0 if row.account_type == "savings" else 1, row.account_number))

    def get(self, account_id: int) -> Account | None:
        return self.session.get(Account, account_id)

    def transactions(self, account_id: int, limit: int) -> list[Transaction]:
        return list(
            self.session.scalars(
                select(Transaction)
                .where(Transaction.account_id == account_id)
                .order_by(Transaction.posted_on.desc(), Transaction.id.desc())
                .limit(limit)
            ).all()
        )


class LoanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_open(self, customer_id: int) -> LoanApplication | None:
        return self.session.scalar(
            select(LoanApplication).where(
                LoanApplication.customer_id == customer_id,
                LoanApplication.status.notin_(("submitted", "rejected", "declined")),
            )
        )

    def get(self, loan_id: int) -> LoanApplication | None:
        return self.session.get(LoanApplication, loan_id)

    def latest(self, customer_id: int) -> LoanApplication | None:
        return self.session.scalar(
            select(LoanApplication)
            .where(LoanApplication.customer_id == customer_id)
            .order_by(LoanApplication.id.desc())
        )

    def create(self, customer_id: int, product_code: str = "unspecified") -> LoanApplication:
        now = utcnow()
        payload = new_loan_state()
        payload["product_code"] = product_code
        row = LoanApplication(
            customer_id=customer_id,
            product_code=product_code,
            status="collecting",
            schema_version=SCHEMA_VERSION,
            payload_json=json.dumps(payload),
            expected_field=None,
            review_required=False,
            customer_confirmed=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def save(self, row: LoanApplication, payload: dict) -> LoanApplication:
        now = utcnow()
        row.payload_json = json.dumps(payload)
        row.status = payload.get("workflow_status") or row.status
        row.product_code = payload.get("product_code") or row.product_code
        row.expected_field = payload.get("expected_field")
        row.review_status = payload.get("review_status")
        row.review_notes = payload.get("review_notes")
        row.review_required = bool(payload.get("review_required"))
        row.approved_risk_hash = payload.get("approved_risk_hash")
        row.customer_confirmed = bool(payload.get("customer_confirmed"))
        row.reference = payload.get("reference")
        row.updated_at = now
        if row.status == "submitted" and not row.submitted_at:
            row.submitted_at = now
        self.session.flush()
        return row

    def mark_submitted(self, row: LoanApplication, payload: dict, reference: str) -> bool:
        now = utcnow()
        payload = dict(payload)
        payload["workflow_status"] = "submitted"
        payload["reference"] = reference
        payload["customer_confirmed"] = True
        payload["declarations_accepted"] = True
        payload["expected_field"] = None
        self.session.execute(
            update(LoanApplication)
            .where(
                LoanApplication.id == row.id,
                LoanApplication.customer_id == row.customer_id,
                LoanApplication.status == "awaiting_confirmation",
            )
            .values(
                status="submitted",
                reference=reference,
                customer_confirmed=True,
                payload_json=json.dumps(payload),
                expected_field=None,
                submitted_at=now,
                updated_at=now,
            )
        )
        self.session.flush()
        self.session.expire(row)
        self.session.refresh(row)
        return row.status == "submitted" and row.reference == reference

    def add_document(self, **fields) -> Document:
        row = Document(created_at=utcnow(), **fields)
        self.session.add(row)
        self.session.flush()
        return row

    def list_pending(self) -> list[LoanApplication]:
        return list(
            self.session.scalars(
                select(LoanApplication)
                .where(LoanApplication.status == "pending_review")
                .order_by(LoanApplication.id)
            ).all()
        )

    def add_review(self, application_id: int, reviewer_id: int, decision: str, notes: str) -> Review:
        row = Review(
            application_id=application_id,
            reviewer_id=reviewer_id,
            decision=decision,
            notes=notes,
            created_at=utcnow(),
        )
        self.session.add(row)
        self.session.flush()
        return row


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, actor_ref: str, action: str, resource: str, outcome: str, metadata: dict | None = None) -> None:
        self.session.add(
            AuditEvent(
                created_at=utcnow(),
                actor_ref=actor_ref,
                action=action,
                resource=resource,
                outcome=outcome,
                metadata_json=json.dumps(metadata or {}),
            )
        )
        self.session.flush()

    def recent(self, limit: int = 100) -> list[AuditEvent]:
        return list(
            self.session.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()
        )


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def owner(self, conversation_id: str) -> int | None:
        row = self.session.get(Checkpoint, conversation_id)
        return None if row is None else row.customer_id

    def ensure(self, conversation_id: str, customer_id: int) -> Checkpoint:
        row = self.session.get(Checkpoint, conversation_id)
        if row is None:
            row = Checkpoint(
                conversation_id=conversation_id,
                customer_id=customer_id,
                updated_at=utcnow(),
            )
            self.session.add(row)
            self.session.flush()
        return row

    def save_pending(self, conversation_id: str, customer_id: int, intent: str | None, kind: str | None) -> None:
        row = self.ensure(conversation_id, customer_id)
        row.pending_intent = intent
        row.pending_balance_kind = kind
        row.updated_at = utcnow()
        self.session.flush()

    def add_message(
        self,
        conversation_id: str,
        customer_id: int,
        role: str,
        content: str,
        intent: str | None = None,
        citations: list | None = None,
    ) -> None:
        self.session.add(
            Message(
                conversation_id=conversation_id,
                customer_id=customer_id,
                role=role,
                content=content,
                intent=intent,
                citations_json=json.dumps(citations or []),
                created_at=utcnow(),
            )
        )
        self.session.flush()

    def list_messages(self, conversation_id: str) -> list[Message]:
        return list(
            self.session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            ).all()
        )

    def latest_id(self, customer_id: int) -> str | None:
        row = self.session.scalar(
            select(Checkpoint)
            .where(Checkpoint.customer_id == customer_id)
            .order_by(Checkpoint.updated_at.desc())
        )
        return None if row is None else row.conversation_id


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_all(self, rows: list[dict]) -> None:
        self.session.execute(delete(KnowledgeChunk))
        for row in rows:
            self.session.add(KnowledgeChunk(**row))
        self.session.flush()


def require(row, message: str = "Not found"):
    if row is None:
        raise NotFound(message)
    return row
