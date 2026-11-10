from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20))
    password_salt: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    pin_salt: Mapped[str] = mapped_column(String(64))
    pin_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(40))

    __table_args__ = (CheckConstraint("role IN ('customer', 'reviewer')", name="ck_customer_role"),)


class KycProfile(Base):
    __tablename__ = "kyc_profiles"

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    date_of_birth: Mapped[str] = mapped_column(String(10))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    address_line: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(80))
    postal_code: Mapped[str] = mapped_column(String(12))
    pan_masked: Mapped[str] = mapped_column(String(20))
    aadhaar_masked: Mapped[str] = mapped_column(String(20))
    kyc_status: Mapped[str] = mapped_column(String(20))
    verified_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    account_number: Mapped[str] = mapped_column(String(20), unique=True)
    account_type: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    available_balance_paise: Mapped[int] = mapped_column(Integer)
    ledger_balance_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")

    __table_args__ = (
        CheckConstraint("account_type IN ('savings', 'current')", name="ck_account_type"),
        CheckConstraint("available_balance_paise >= 0", name="ck_available_nonneg"),
        CheckConstraint("ledger_balance_paise >= 0", name="ck_ledger_nonneg"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    posted_on: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(200))
    amount_paise: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(10))

    __table_args__ = (
        CheckConstraint("direction IN ('credit', 'debit')", name="ck_direction"),
        CheckConstraint("amount_paise > 0", name="ck_amount_positive"),
    )


class LoanProduct(Base):
    __tablename__ = "loan_products"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    submittable: Mapped[bool] = mapped_column(Boolean, default=False)


class LoanApplication(Base):
    __tablename__ = "loan_applications"
    __table_args__ = (
        Index(
            "uq_one_open_loan",
            "customer_id",
            unique=True,
            sqlite_where=text("status NOT IN ('submitted', 'rejected', 'declined')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(40), default="unspecified")
    status: Mapped[str] = mapped_column(String(40), index=True)
    schema_version: Mapped[str] = mapped_column(String(40))
    payload_json: Mapped[str] = mapped_column(Text)
    expected_field: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_risk_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    submitted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(200))
    storage_path: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    extraction_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("loan_applications.id"), nullable=True)
    purpose: Mapped[str] = mapped_column(String(80))
    granted: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[str] = mapped_column(String(40))


class Checkpoint(Base):
    __tablename__ = "workflow_checkpoints"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    pending_intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pending_balance_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(40))


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class Review(Base):
    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    decision: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(40))

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approve', 'reject', 'request_info')",
            name="ck_review_decision",
        ),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    actor_ref: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(40))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(20))
    product: Mapped[str] = mapped_column(String(40))
    access: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
