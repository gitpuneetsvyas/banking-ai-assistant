from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.core.money import format_inr_words
from app.domain.contract import LoanApplicationContract


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_application(contract: LoanApplicationContract, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story: list = []
    review = contract.review_submit
    banner = "SUBMITTED" if review.customer_confirmed else "DRAFT — NOT SUBMITTED"
    story.append(Paragraph("Harbourline Bank", styles["Title"]))
    story.append(Paragraph("Fictional personal-loan application", styles["Heading2"]))
    story.append(Paragraph(banner, styles["Heading3"]))
    story.append(
        Paragraph(
            "Generated from schema poc-loan-v1. The customer did not fill in a form. "
            "Figures are fictional POC data.",
            styles["Italic"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    _section(story, styles, "Form 1 — Personal and KYC", contract.personal_kyc.model_dump())
    employment = contract.employment_loan.model_dump()
    employment["requested_amount"] = format_inr_words(contract.employment_loan.requested_amount_paise)
    employment["monthly_income"] = format_inr_words(contract.employment_loan.monthly_income_paise)
    _section(story, styles, "Form 2 — Employment and loan", employment)
    _section(story, styles, "Form 3 — Review and submission", review.model_dump())
    story.append(Paragraph("Provenance", styles["Heading2"]))
    for key, source in contract.provenance.items():
        story.append(Paragraph(f"{_escape(key)}: {_escape(source)}", styles["BodyText"]))
    if review.review_reasons:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Items a reviewer must check", styles["Heading2"]))
        for reason in review.review_reasons:
            story.append(Paragraph(_escape(reason), styles["BodyText"]))
    declaration = (
        "Declaration accepted."
        if review.declarations_accepted
        else "Declaration not yet accepted. Nothing has been submitted."
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_escape(declaration), styles["BodyText"]))
    document = SimpleDocTemplate(str(path), pagesize=A4, title="Harbourline loan application")
    document.build(story)


def _section(story: list, styles, title: str, fields: dict) -> None:
    story.append(Paragraph(_escape(title), styles["Heading2"]))
    for key, value in fields.items():
        story.append(Paragraph(f"<b>{_escape(key)}</b>: {_escape(value)}", styles["BodyText"]))
    story.append(Spacer(1, 3 * mm))
