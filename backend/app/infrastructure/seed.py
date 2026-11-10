"""Fictional Harbourline customers. These records are demonstration data."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.security import hash_secret
from app.infrastructure.models import Account, Customer, KycProfile, LoanProduct, Transaction

PRIYA_EMAIL = "priya.sharma@example.com"
PRIYA_PASSWORD = "demo-pass-priya"
PRIYA_PIN = "2580"
ARJUN_EMAIL = "arjun.mehta@example.com"
ARJUN_PASSWORD = "demo-pass-arjun"
ARJUN_PIN = "1470"
REVIEWER_EMAIL = "reviewer@harbourline.example"
REVIEWER_PASSWORD = "demo-pass-reviewer"

PRIYA_SAVINGS_NUMBER = "501000004582"
PRIYA_CURRENT_NUMBER = "501000009081"
ARJUN_SAVINGS_NUMBER = "502000002210"
PRIYA_SAVINGS_AVAILABLE = 12_500_000
PRIYA_SAVINGS_LEDGER = 13_000_000
PRIYA_CURRENT_AVAILABLE = 4_250_000
ARJUN_SAVINGS_AVAILABLE = 875_000


def seed(session: Session) -> None:
    existing = session.scalar(select(func.count()).select_from(Customer))
    if existing:
        return
    now = utcnow()
    priya = _customer(
        ref="CUS-1001",
        email=PRIYA_EMAIL,
        first="Priya",
        last="Sharma",
        role="customer",
        password=PRIYA_PASSWORD,
        pin=PRIYA_PIN,
        now=now,
    )
    arjun = _customer(
        ref="CUS-1002",
        email=ARJUN_EMAIL,
        first="Arjun",
        last="Mehta",
        role="customer",
        password=ARJUN_PASSWORD,
        pin=ARJUN_PIN,
        now=now,
    )
    reviewer = _customer(
        ref="EMP-2001",
        email=REVIEWER_EMAIL,
        first="Demo",
        last="Reviewer",
        role="reviewer",
        password=REVIEWER_PASSWORD,
        pin="0000",
        now=now,
    )
    session.add_all([priya, arjun, reviewer])
    session.flush()
    session.add_all(
        [
            KycProfile(
                customer_id=priya.id,
                date_of_birth="1992-04-18",
                email=PRIYA_EMAIL,
                phone="9845012345",
                address_line="42 Residency Road",
                city="Bengaluru",
                state="Karnataka",
                postal_code="560025",
                pan_masked="XXXXX1234A",
                aadhaar_masked="XXXX-XXXX-2188",
                kyc_status="verified",
                verified_at="2026-01-15T00:00:00+00:00",
            ),
            KycProfile(
                customer_id=arjun.id,
                date_of_birth="1988-11-02",
                email=ARJUN_EMAIL,
                phone="9822098765",
                address_line="19 Lake View",
                city="Pune",
                state="Maharashtra",
                postal_code="411001",
                pan_masked="XXXXX5678B",
                aadhaar_masked="XXXX-XXXX-9044",
                kyc_status="verified",
                verified_at="2026-02-01T00:00:00+00:00",
            ),
        ]
    )
    savings = Account(
        customer_id=priya.id,
        account_number=PRIYA_SAVINGS_NUMBER,
        account_type="savings",
        currency="INR",
        available_balance_paise=PRIYA_SAVINGS_AVAILABLE,
        ledger_balance_paise=PRIYA_SAVINGS_LEDGER,
        status="active",
    )
    current = Account(
        customer_id=priya.id,
        account_number=PRIYA_CURRENT_NUMBER,
        account_type="current",
        currency="INR",
        available_balance_paise=PRIYA_CURRENT_AVAILABLE,
        ledger_balance_paise=PRIYA_CURRENT_AVAILABLE,
        status="active",
    )
    arjun_savings = Account(
        customer_id=arjun.id,
        account_number=ARJUN_SAVINGS_NUMBER,
        account_type="savings",
        currency="INR",
        available_balance_paise=ARJUN_SAVINGS_AVAILABLE,
        ledger_balance_paise=ARJUN_SAVINGS_AVAILABLE,
        status="active",
    )
    session.add_all([savings, current, arjun_savings])
    session.flush()
    session.add_all(
        [
            Transaction(
                account_id=savings.id,
                posted_on="2026-10-28",
                description="Salary credit",
                amount_paise=8_000_000,
                direction="credit",
            ),
            Transaction(
                account_id=savings.id,
                posted_on="2026-10-30",
                description="Grocery",
                amount_paise=250_000,
                direction="debit",
            ),
            Transaction(
                account_id=savings.id,
                posted_on="2026-11-01",
                description="Electricity bill",
                amount_paise=150_000,
                direction="debit",
            ),
        ]
    )
    session.add_all(
        [
            LoanProduct(code="personal", name="Personal loan", submittable=True),
            LoanProduct(code="home", name="Home loan", submittable=False),
        ]
    )


def _customer(*, ref, email, first, last, role, password, pin, now) -> Customer:
    password_salt, password_hash = hash_secret(password)
    pin_salt, pin_hash = hash_secret(pin)
    return Customer(
        customer_ref=ref,
        email=email,
        first_name=first,
        last_name=last,
        role=role,
        password_salt=password_salt,
        password_hash=password_hash,
        pin_salt=pin_salt,
        pin_hash=pin_hash,
        created_at=now,
    )
