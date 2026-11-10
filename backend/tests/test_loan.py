from pathlib import Path

from app.domain.contract import SCHEMA_VERSION, assert_submittable
from app.infrastructure.seed import PRIYA_PIN
from app.core.config import BACKEND_ROOT


def _say(client, headers, message, conversation_id=None):
    response = client.post(
        "/api/chat",
        json={"message": message, "conversation_id": conversation_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_formless_personal_loan_submits_only_after_confirmation(client, priya):
    started = _say(client, priya, "I want to apply for a personal loan of ₹5 lakh.")
    assert "permission" in started["reply"].lower() or "profile" in started["reply"].lower()
    assert started["application"]["requested_amount_paise"] == 50_000_000
    assert started["application"]["monthly_income_paise"] is None
    conversation = started["conversation_id"]

    consented = _say(client, priya, "Yes", conversation)
    assert "Priya Sharma" in consented["reply"]
    assert "42 Residency Road" in consented["reply"]
    assert consented["application"]["monthly_income_paise"] is None
    assert any(item["name"] == "get_customer_profile" for item in consented["tool_trace"])

    _say(client, priya, "Salaried", conversation)
    _say(client, priya, "Northwind Analytics Pvt Ltd", conversation)
    _say(client, priya, "₹80,000", conversation)
    _say(client, priya, "36 months", conversation)
    ready_for_file = _say(client, priya, "Home renovation", conversation)
    assert "upload" in ready_for_file["actions"]
    assert "salary slip" in ready_for_file["reply"].lower()

    sample = Path(BACKEND_ROOT, "samples", "priya_salary_slip.txt")
    uploaded = client.post(
        f"/api/conversations/{conversation}/documents",
        headers=priya,
        files={"file": ("priya_salary_slip.txt", sample.read_bytes(), "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    draft = uploaded.json()
    assert draft["pdf_ready"] is True
    assert "confirm" in draft["actions"]
    assert draft["application"]["status"] == "awaiting_confirmation"
    loan_id = draft["application"]["id"]

    early = client.post(f"/api/loans/{loan_id}/confirm", json={"pin": "0000"}, headers=priya)
    assert early.status_code == 200
    assert "not submitted" in early.json()["reply"].lower()
    assert early.json()["application"]["status"] == "awaiting_confirmation"

    submitted = _say(client, priya, f"I confirm with pin {PRIYA_PIN}", conversation)
    assert submitted["application"]["status"] == "submitted"
    reference = submitted["application"]["reference"]
    assert reference.startswith("HB-PL-")
    assert submitted["application"]["schema_version"] == SCHEMA_VERSION
    pdf = client.get(f"/api/loans/{loan_id}/document", headers=priya)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    from pypdf import PdfReader
    import io

    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Priya" in extracted and "Sharma" in extracted
    assert "5,00,000" in extracted
    assert "did not fill" in extracted.lower()

    again = _say(client, priya, f"I confirm with pin {PRIYA_PIN}", conversation)
    assert reference in again["reply"]
    rows = client.app.state.session_factory()
    try:
        from app.infrastructure.models import LoanApplication

        stored = rows.query(LoanApplication).filter_by(customer_id=1).all()
        assert len([row for row in stored if row.status == "submitted"]) == 1
        payload = __import__("json").loads([row for row in stored if row.status == "submitted"][0].payload_json)
        assert_submittable(payload)
    finally:
        rows.close()


def test_income_conflict_pauses_for_review_and_resumes(client, priya, reviewer):
    started = _say(client, priya, "I want to apply for a personal loan of ₹5 lakh.")
    conversation = started["conversation_id"]
    for message in (
        "Yes",
        "Salaried",
        "Northwind Analytics Pvt Ltd",
        "₹80,000",
        "36 months",
        "Home renovation",
    ):
        _say(client, priya, message, conversation)
    sample = Path(BACKEND_ROOT, "samples", "priya_salary_slip_conflict.txt")
    uploaded = client.post(
        f"/api/conversations/{conversation}/documents",
        headers=priya,
        files={"file": ("conflict.txt", sample.read_bytes(), "text/plain")},
    )
    body = uploaded.json()
    assert body["application"]["status"] == "pending_review"
    assert body["application"]["review_reasons"]
    loan_id = body["application"]["id"]
    blocked = _say(client, priya, f"I confirm with pin {PRIYA_PIN}", conversation)
    assert blocked["application"]["status"] == "pending_review"
    queue = client.get("/api/reviews/pending", headers=reviewer)
    assert queue.status_code == 200
    assert queue.json()["reviews"][0]["id"] == loan_id
    assert client.post("/api/reviews/pending", headers=priya).status_code == 405 or client.get(
        "/api/reviews/pending", headers=priya
    ).status_code == 403
    decision = client.post(
        f"/api/reviews/{loan_id}",
        json={"decision": "approve", "notes": "Income difference accepted for this fictional POC."},
        headers=reviewer,
    )
    assert decision.status_code == 200, decision.text
    resumed = _say(client, priya, "I am ready to review it", conversation)
    assert resumed["application"]["status"] == "awaiting_confirmation"
    submitted = _say(client, priya, f"I confirm with pin {PRIYA_PIN}", conversation)
    assert submitted["application"]["status"] == "submitted"
    assert submitted["application"]["reference"].startswith("HB-PL-")


def test_workflow_survives_a_new_process(tmp_path):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(data_dir=tmp_path, jwt_secret="test-secret")
    with TestClient(create_app(settings)) as first:
        token = first.post(
            "/api/auth/login",
            json={"email": "priya.sharma@example.com", "password": "demo-pass-priya"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        started = first.post(
            "/api/chat",
            json={"message": "I want to apply for a personal loan of ₹5 lakh."},
            headers=headers,
        ).json()
    with TestClient(create_app(settings)) as second:
        token = second.post(
            "/api/auth/login",
            json={"email": "priya.sharma@example.com", "password": "demo-pass-priya"},
        ).json()["access_token"]
        continued = second.post(
            "/api/chat",
            json={"message": "Yes", "conversation_id": started["conversation_id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert continued.status_code == 200, continued.text
    assert "Priya Sharma" in continued.json()["reply"]
    assert continued.json()["application"]["requested_amount_paise"] == 50_000_000


def test_a_document_question_is_not_treated_as_an_application():
    from app.agent.nlu import interpret

    assert interpret("What documents do I need for a loan?").intent == "knowledge"


def test_loan_request_without_the_word_personal_starts_a_personal_draft(client, priya):
    started = _say(client, priya, "I want to apply for a ₹5 lakh loan")
    assert started["application"]["product_code"] == "personal"
    assert started["application"]["requested_amount_paise"] == 50_000_000
    assert "permission" in started["reply"].lower()


def test_out_of_policy_amount_is_not_silently_changed(client, priya):
    started = _say(client, priya, "I want to apply for a personal loan of ₹50 lakh.")
    reply = _say(client, priya, "Yes", started["conversation_id"])
    assert "15,00,000" in reply["reply"]
    assert reply["application"]["status"] != "submitted"


def test_other_customer_cannot_download_the_application(client, priya, arjun):
    started = _say(client, priya, "I want to apply for a personal loan of ₹5 lakh.")
    loan_id = started["application"]["id"]
    denied = client.get(f"/api/loans/{loan_id}/document", headers=arjun)
    assert denied.status_code in {403, 404}
    assert PRIYA_PIN not in denied.text
