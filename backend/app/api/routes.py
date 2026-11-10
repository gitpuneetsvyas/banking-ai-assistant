from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.orchestrator import Orchestrator
from app.agent.tools import BankingTools, payload_from
from app.core.errors import DomainError, Forbidden, NotFound, Unauthorised
from app.domain.state import public_application
from app.core.security import issue_token, parse_token, verify_secret
from app.infrastructure.models import Customer
from app.infrastructure.repositories import AuditRepository, CustomerRepository, LoanRepository
from datetime import timedelta

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatRequest(BaseModel):
    message: str = ""
    conversation_id: str | None = None


class ConfirmRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=8)
    conversation_id: str | None = None


class ReviewRequest(BaseModel):
    decision: str
    notes: str = ""


def get_session(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(request: Request, session: Session = Depends(get_session)) -> Customer:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise Unauthorised("Sign in required")
    token = header.split(" ", 1)[1].strip()
    data = parse_token(token, request.app.state.settings.jwt_secret)
    user = CustomerRepository(session).get(int(data["sub"]))
    if user is None:
        raise Unauthorised("Sign in required")
    request.app.state.limiter.check(f"user:{user.id}", request.app.state.settings.rate_limit_per_minute)
    return user


def _orchestrator(request: Request, session: Session, user: Customer) -> Orchestrator:
    return Orchestrator(session, user, request.app.state.settings, request.app.state.retriever)


@router.get("/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "bank": settings.bank_name,
        "fictional": True,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    host = request.client.host if request.client else "unknown"
    request.app.state.limiter.check(f"login:{host}", request.app.state.settings.login_limit_per_minute)
    user = CustomerRepository(session).get_by_email(body.email.strip().casefold())
    if user is None or not verify_secret(body.password, user.password_salt, user.password_hash):
        AuditRepository(session).add("anonymous", "auth.login", "auth", "denied", {})
        raise Unauthorised("Invalid email or password.")
    settings = request.app.state.settings
    token = issue_token(user.id, settings.jwt_secret, timedelta(minutes=settings.jwt_ttl_minutes))
    AuditRepository(session).add(user.customer_ref, "auth.login", "auth", "ok", {})
    return {
        "access_token": token,
        "token_type": "bearer",
        "customer_ref": user.customer_ref,
        "display_name": f"{user.first_name} {user.last_name}",
        "role": user.role,
    }


@router.get("/me")
def me(user: Customer = Depends(get_current_user)) -> dict:
    return {
        "customer_ref": user.customer_ref,
        "display_name": f"{user.first_name} {user.last_name}",
        "role": user.role,
        "email": user.email,
    }


@router.post("/chat")
def chat(
    body: ChatRequest,
    request: Request,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    result = _orchestrator(request, session, user).handle(body.conversation_id, body.message)
    return result.model_dump()


@router.get("/conversations/latest")
def latest_conversation(
    request: Request,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    from app.infrastructure.repositories import ConversationRepository

    repo = ConversationRepository(session)
    conversation_id = repo.latest_id(user.id)
    if conversation_id is None:
        return {"conversation_id": None, "messages": []}
    return _conversation_payload(repo, conversation_id, user.id)


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    from app.infrastructure.repositories import ConversationRepository

    repo = ConversationRepository(session)
    owner = repo.owner(conversation_id)
    if owner is None:
        raise NotFound("Conversation not found")
    if owner != user.id and user.role != "reviewer":
        raise Forbidden("That conversation belongs to another customer.")
    return _conversation_payload(repo, conversation_id, owner)


@router.post("/conversations/{conversation_id}/documents")
def upload_document(
    conversation_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    data = file.file.read()
    result = _orchestrator(request, session, user).attach_document(
        conversation_id, file.filename or "upload.txt", data
    )
    return result.model_dump()


@router.get("/accounts")
def list_accounts(
    request: Request,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    tools = BankingTools(session, user, request.app.state.settings, request.app.state.retriever)
    return {"accounts": tools.list_customer_accounts()}


@router.get("/accounts/{account_id}/balance")
def account_balance(
    account_id: int,
    request: Request,
    kind: str = "available",
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    tools = BankingTools(session, user, request.app.state.settings, request.app.state.retriever)
    return tools.get_balance_for_account(account_id, kind if kind == "ledger" else "available")


@router.get("/loans/current")
def current_loan(
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = LoanRepository(session).get_open(user.id) or LoanRepository(session).latest(user.id)
    if row is None or (user.role == "customer" and row.customer_id != user.id):
        return {"application": None}
    return {"application": public_application(payload_from(row), row.id)}


@router.get("/loans/{loan_id}/document")
def loan_document(
    loan_id: int,
    request: Request,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    row = LoanRepository(session).get(loan_id)
    if row is None:
        raise NotFound("Application not found")
    if user.role != "reviewer" and row.customer_id != user.id:
        raise Forbidden("You cannot access another customer's application.")
    path = request.app.state.settings.pdf_dir / f"application-{loan_id}.pdf"
    if not path.exists():
        raise NotFound("The application document has not been generated yet.")
    filename = f"{row.reference or 'loan-draft'}.pdf"
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.post("/loans/{loan_id}/confirm")
def confirm_loan(
    loan_id: int,
    body: ConfirmRequest,
    request: Request,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = LoanRepository(session).get(loan_id)
    if row is None or row.customer_id != user.id:
        raise NotFound("Application not found")
    open_row = LoanRepository(session).get_open(user.id)
    if open_row is None or open_row.id != loan_id:
        if row.status == "submitted" and row.reference:
            return {
                "conversation_id": body.conversation_id,
                "reply": f"This application was already submitted. Reference {row.reference}.",
                "intent": "loan_application",
                "citations": [],
                "tool_trace": [],
                "application": public_application(payload_from(row), row.id),
                "pdf_ready": (request.app.state.settings.pdf_dir / f"application-{loan_id}.pdf").exists(),
                "actions": [],
            }
        raise DomainError("The application is not ready to submit.")
    result = _orchestrator(request, session, user).handle(
        body.conversation_id,
        "",
        event="confirm",
        pin=body.pin,
    )
    return result.model_dump()


@router.get("/reviews/pending")
def pending_reviews(
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    if user.role != "reviewer":
        raise Forbidden("Only a reviewer can view the queue.")
    items = []
    for row in LoanRepository(session).list_pending():
        customer = session.get(Customer, row.customer_id)
        payload = payload_from(row)
        items.append(
            {
                "id": row.id,
                "customer_name": f"{customer.first_name} {customer.last_name}",
                "customer_ref": customer.customer_ref,
                "status": row.status,
                "review_reasons": payload.get("review_reasons") or [],
                "requested_amount_paise": payload.get("requested_amount_paise"),
                "monthly_income_paise": payload.get("monthly_income_paise"),
            }
        )
    return {"reviews": items}


@router.post("/reviews/{loan_id}")
def decide_review(
    loan_id: int,
    body: ReviewRequest,
    request: Request,
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    tools = BankingTools(session, user, request.app.state.settings, request.app.state.retriever)
    return {"application": tools.decide_review(loan_id, body.decision, body.notes)}


@router.get("/audit")
def audit(
    user: Customer = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    if user.role != "reviewer":
        raise Forbidden("Only a reviewer can read the audit log.")
    events = []
    for row in AuditRepository(session).recent(100):
        events.append(
            {
                "created_at": row.created_at,
                "actor_ref": row.actor_ref,
                "action": row.action,
                "outcome": row.outcome,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
        )
    return {"events": events}


def _conversation_payload(repo, conversation_id: str, customer_id: int) -> dict:
    messages = []
    for row in repo.list_messages(conversation_id):
        if row.customer_id != customer_id:
            continue
        messages.append(
            {
                "role": row.role,
                "content": row.content,
                "intent": row.intent,
                "citations": json.loads(row.citations_json or "[]"),
            }
        )
    return {"conversation_id": conversation_id, "messages": messages}
