from __future__ import annotations

import re
from dataclasses import dataclass, field

from langchain_core.documents import Document

from app.core.money import format_inr, parse_amounts, parse_tenure_months
from app.domain.policy import illustrative_emi_paise
from app.rag.engine import INJECTION, HybridKnowledgeRetriever, tokenize

CLARIFY = (
    "Do you mean a personal loan or a home loan? "
    "I'll answer from the approved page for that product."
)
ABSTAIN = (
    "I don't have an approved Harbourline page that answers that, "
    "so I can't state a rate, fee, or policy for it."
)


@dataclass
class KnowledgeAnswer:
    text: str
    citations: list[dict] = field(default_factory=list)
    abstained: bool = False
    clarified: bool = False

    @property
    def doc_ids(self) -> list[str]:
        return [item["doc_id"] for item in self.citations]


def numbers_are_grounded(draft: str, evidence: str) -> bool:
    if INJECTION.search(draft):
        return False
    compact = evidence.replace(",", "")
    for match in re.findall(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?%?|\d+(?:\.\d+)?%?", draft):
        token = match.replace(",", "")
        if match not in evidence and token not in compact and token not in evidence:
            return False
    return True


def answer_question(
    query: str,
    retriever: HybridKnowledgeRetriever,
    *,
    paraphraser=None,
    loan: dict | None = None,
) -> KnowledgeAnswer:
    documents = retriever.invoke(query)
    if not documents:
        return KnowledgeAnswer(text=ABSTAIN, abstained=True)
    if _needs_clarification(query, documents):
        return KnowledgeAnswer(text=CLARIFY, clarified=True)
    citations = [_citation(document) for document in documents]
    evidence = "\n\n".join(document.page_content for document in documents)
    quoted = _quote(documents)
    illustration = _emi_illustration(query, evidence, loan)
    if illustration:
        quoted = f"{quoted}\n\n{illustration}"
        evidence = f"{evidence}\n{illustration}"
    if paraphraser is not None:
        try:
            draft = paraphraser(query, evidence)
        except Exception:
            draft = ""
        if draft and numbers_are_grounded(draft, evidence):
            text = (
                "I can answer this only from approved Harbourline pages. "
                "Rates and fees are fictional POC examples.\n\n"
                f"{draft.strip()}\n\nSources: {_source_line(citations)}"
            )
            return KnowledgeAnswer(text=text, citations=citations)
    return KnowledgeAnswer(text=quoted, citations=citations)


def _needs_clarification(query: str, documents: list[Document]) -> bool:
    tokens = set(tokenize(query, drop_generic=True))
    if "personal" in tokens or "home" in tokens:
        return False
    products = {document.metadata.get("product") for document in documents}
    return "personal_loan" in products and "home_loan" in products


def _citation(document: Document) -> dict:
    return {
        "doc_id": document.metadata.get("doc_id"),
        "title": document.metadata.get("title"),
        "version": document.metadata.get("version"),
    }


def _source_line(citations: list[dict]) -> str:
    return "; ".join(f"{item['doc_id']} v{item['version']}" for item in citations)


def _quote(documents: list[Document]) -> str:
    parts = []
    citations = []
    for document in documents:
        citation = _citation(document)
        citations.append(citation)
        parts.append(
            f"[{citation['doc_id']} v{citation['version']} — {citation['title']}]\n{document.page_content.strip()}"
        )
    return (
        "I can answer this only from approved Harbourline pages. "
        "Rates and fees below are fictional POC examples.\n\n" + "\n\n".join(parts)
    )


def _emi_illustration(query: str, evidence: str, loan: dict | None) -> str | None:
    if "emi" not in set(tokenize(query, drop_generic=True)):
        return None
    if "12.5%" not in evidence:
        return None
    amounts = parse_amounts(query)
    tenure = parse_tenure_months(query)
    if not amounts and loan and loan.get("requested_amount_paise") and loan.get("tenure_months"):
        amounts = [loan["requested_amount_paise"]]
        tenure = loan["tenure_months"]
        source = "the amount and tenure already on your draft"
    elif amounts and tenure:
        source = "the amount and tenure in your question"
    else:
        return None
    emi = illustrative_emi_paise(amounts[0], tenure)
    return (
        f"Illustrative calculation from DOC-PL-EMI using the fictional 12.5% rate and {source}: "
        f"{format_inr(emi)} per month. This is not a sanction."
    )
