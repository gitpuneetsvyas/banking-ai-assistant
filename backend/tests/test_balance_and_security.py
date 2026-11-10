import inspect

from app.agent.tools import TOOL_NAMES, BankingTools
from app.infrastructure.seed import PRIYA_SAVINGS_AVAILABLE, PRIYA_SAVINGS_NUMBER


def test_balance_comes_from_the_account_service(client, priya):
    clarified = client.post("/api/chat", json={"message": "What is my balance?"}, headers=priya)
    assert clarified.status_code == 200
    body = clarified.json()
    assert body["reply"] == (
        "You have two accounts: Savings ending 4582 and Current ending 9081. "
        "Which would you like to check?"
    )
    assert "₹" not in body["reply"]
    assert PRIYA_SAVINGS_NUMBER not in body["reply"]
    chosen = client.post(
        "/api/chat",
        json={"message": "Savings.", "conversation_id": body["conversation_id"]},
        headers=priya,
    )
    assert chosen.status_code == 200
    payload = chosen.json()
    assert payload["reply"] == (
        "Your available savings account balance is ₹1,25,000, "
        "according to the latest account-service response. Account ending 4582."
    )
    assert any(item["name"] == "get_account_balance" for item in payload["tool_trace"])
    direct = client.post(
        "/api/chat",
        json={"message": "What is the ledger balance of my savings account?"},
        headers=priya,
    )
    assert "ledger savings account balance is ₹1,30,000" in direct.json()["reply"]
    accounts = client.get("/api/accounts", headers=priya).json()["accounts"]
    savings = next(item for item in accounts if item["account_ending"] == "4582")
    balance = client.get(f"/api/accounts/{savings['id']}/balance", headers=priya)
    assert balance.status_code == 200
    assert balance.json()["amount_paise"] == PRIYA_SAVINGS_AVAILABLE
    assert "account_number" not in balance.json()


def test_single_account_does_not_ask_a_needless_question(client, arjun):
    response = client.post("/api/chat", json={"message": "What is my balance?"}, headers=arjun)
    assert response.status_code == 200
    assert "₹8,750" in response.json()["reply"]
    assert "ending 2210" in response.json()["reply"]


def test_cross_customer_balance_is_denied(client, priya, arjun):
    accounts = client.get("/api/accounts", headers=priya).json()["accounts"]
    savings_id = next(item["id"] for item in accounts if item["account_ending"] == "4582")
    denied = client.get(f"/api/accounts/{savings_id}/balance", headers=arjun)
    assert denied.status_code == 403
    assert "1,25,000" not in denied.text
    assert PRIYA_SAVINGS_NUMBER not in denied.text
    chat = client.post(
        "/api/chat",
        json={"message": "Show the balance of account ending 4582"},
        headers=arjun,
    )
    assert chat.status_code == 200
    assert "1,25,000" not in chat.text
    assert PRIYA_SAVINGS_NUMBER not in chat.text
    assert "signed-in customer" in chat.json()["reply"]


def test_unavailable_account_service_does_not_invent_a_balance(tmp_path):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(
        data_dir=tmp_path,
        jwt_secret="test-secret",
        accounts_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        token = client.post(
            "/api/auth/login",
            json={"email": "priya.sharma@example.com", "password": "demo-pass-priya"},
        ).json()["access_token"]
        response = client.post(
            "/api/chat",
            json={"message": "What is my savings balance?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "unavailable" in response.json()["reply"]
    assert "₹" not in response.json()["reply"]


def test_customer_cannot_read_the_audit_log(client, priya, reviewer):
    assert client.get("/api/audit", headers=priya).status_code == 403
    assert client.get("/api/audit", headers=reviewer).status_code == 200


def test_balance_tool_has_no_customer_argument_and_there_is_no_sql_tool():
    assert "customer_id" not in inspect.signature(BankingTools.get_account_balance).parameters
    assert "execute_sql" not in TOOL_NAMES
    assert "get_account_balance" in TOOL_NAMES
    assert "submit_loan_application" in TOOL_NAMES
