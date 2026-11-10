from __future__ import annotations

from app.core.money import format_inr
from app.domain.validation import personal_value

CONSENT = (
    "I can help you prepare the application. With your permission, I'll use the verified "
    "information already available in your banking profile and ask only for what is missing. "
    "May I use that profile?"
)


def ask(field: str, loan: dict) -> str:
    if field == "consent":
        return CONSENT
    if field == "employment_type":
        name = f"{personal_value(loan, 'first_name')} {personal_value(loan, 'last_name')}".strip()
        address = ", ".join(
            part
            for part in (
                personal_value(loan, "address_line"),
                personal_value(loan, "city"),
            )
            if part
        )
        return (
            f"I have retrieved {name} and the registered address {address}. "
            "What is your current employment type: salaried or self-employed?"
        )
    if field == "employer_name":
        return "What is your employer's name?"
    if field == "monthly_income_paise":
        return "What is your monthly income?"
    if field == "tenure_months":
        return "What loan tenure would you like, in months (12 to 60 under the fictional personal-loan policy)?"
    if field == "purpose":
        return "What is the purpose of this loan?"
    if field == "product":
        amount = loan.get("requested_amount_paise")
        amount_bit = f" of {format_inr(amount)}" if amount else ""
        return (
            f"This assistant can submit a personal loan{amount_bit}. Home loans can be explained "
            "from approved pages, but not submitted here. Do you want a personal loan?"
        )
    if field == "requested_amount_paise":
        return "What personal loan amount would you like?"
    if field == "document":
        if loan.get("documents"):
            return (
                "I couldn't find a net monthly income on that file. Upload a text or PDF that "
                "includes a line such as 'Net monthly income: INR 80000'."
            )
        if loan.get("employment_type") == "self_employed":
            return "Please upload an income tax return as text or PDF so I can verify your income."
        return (
            "Thank you. I need to verify your income using the required supporting document. "
            "You can upload a salary slip as text or PDF."
        )
    if field == "confirmation":
        return ready(loan)
    label = field.replace("_", " ")
    return f"I don't have your {label} on the verified profile. What is it?"


def ready(loan: dict) -> str:
    amount = format_inr(loan["requested_amount_paise"])
    return (
        "Your personal loan application draft is ready. "
        f"It requests {amount} over {loan['tenure_months']} months for {loan['purpose']}. "
        "Please review the completed document. It is read-only and was filled from your verified "
        "profile, your answers, and the uploaded evidence. If you want to submit it, confirm and "
        "enter your transaction PIN. I will not submit it before that."
    )


def paused(reasons: list[str]) -> str:
    detail = " ".join(reasons)
    return (
        "I prepared a draft, but I can't send it for submission yet. "
        f"A reviewer needs to check this: {detail} I have paused the application."
    )
