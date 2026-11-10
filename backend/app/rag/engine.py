from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

INJECTION = re.compile(
    r"ignore (all|any|previous|above) instructions|you are now|system prompt|"
    r"reveal all (customers|accounts|balances)|bypass (authorisation|authorization|validation)",
    re.IGNORECASE,
)

STOP = {
    "what", "is", "the", "a", "an", "for", "of", "my", "to", "and", "are", "do", "does",
    "can", "i", "you", "your", "please", "about", "me", "this", "that", "with", "on",
    "in", "it", "be", "or", "if", "how", "which", "who", "when", "where", "why",
    "between", "am", "was", "were", "have", "has", "from", "at", "by", "not",
}
SYNONYMS = {
    "documents": "document",
    "docs": "document",
    "required": "require",
    "requirement": "require",
    "requirements": "require",
    "prepay": "prepayment",
    "prepaying": "prepayment",
    "prepaid": "prepayment",
    "foreclose": "prepayment",
    "foreclosure": "prepayment",
    "foreclosing": "prepayment",
    "fees": "fee",
    "charges": "fee",
    "charge": "fee",
    "eligible": "eligibility",
    "emis": "emi",
    "instalment": "emi",
    "installment": "emi",
    "instalments": "emi",
    "installments": "emi",
    "loans": "loan",
    "accounts": "account",
}
GENERIC = {"loan", "account", "bank", "customer", "harbourline", "poc", "fictional", "example"}


def sanitize_text(text: str) -> tuple[str, int]:
    kept: list[str] = []
    dropped = 0
    for line in text.splitlines():
        if INJECTION.search(line):
            dropped += 1
            continue
        kept.append(line)
    return "\n".join(kept).strip(), dropped


def tokenize(text: str, *, drop_generic: bool) -> list[str]:
    tokens: list[str] = []
    for raw in re.findall(r"[a-z0-9]+", text.lower()):
        if raw in STOP or raw.isdigit():
            continue
        word = SYNONYMS.get(raw, raw)
        if word in STOP:
            continue
        if drop_generic and word in GENERIC:
            continue
        tokens.append(word)
    return tokens


def embed(text: str, dims: int = 256) -> list[float]:
    vector = [0.0] * dims
    tokens = tokenize(text, drop_generic=False)
    grams = tokens + [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
    for token in grams:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "little") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def parse_markdown(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, front, body = text.split("---", 2)
    meta: dict[str, str] = {}
    for line in front.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def load_chunks(directory: Path) -> tuple[list[dict], int]:
    chunks: list[dict] = []
    dropped = 0
    if not directory.exists():
        return chunks, dropped
    for path in sorted(directory.glob("*.md")):
        meta, body = parse_markdown(path.read_text(encoding="utf-8"))
        if meta.get("fictional") != "true" or meta.get("status") != "approved" or meta.get("access") != "public":
            continue
        clean, removed = sanitize_text(body)
        dropped += removed
        if not clean or INJECTION.search(clean):
            continue
        sections = [part.strip() for part in re.split(r"\n(?=#+\s)", clean) if part.strip()]
        for index, section in enumerate(sections or [clean]):
            chunk_text = f"{meta.get('title', path.stem)}\n{section}"
            chunks.append(
                {
                    "doc_id": meta.get("id", path.stem),
                    "title": meta.get("title", path.stem),
                    "version": meta.get("version", "0"),
                    "product": meta.get("product", "general"),
                    "access": "public",
                    "status": "approved",
                    "text": chunk_text,
                    "embedding": embed(chunk_text),
                    "content_hash": hashlib.sha256(chunk_text.encode()).hexdigest(),
                    "chunk_index": index,
                }
            )
    return chunks, dropped


class HybridKnowledgeRetriever(BaseRetriever):
    """Hybrid lexical coverage and hashed-vector retrieval over approved pages.

    The hashed embedding is a local stand-in so the POC does not download a
    model. The port stays the same for a later MiniLM or Qwen embedding.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    chunks: list[dict] = Field(default_factory=list)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        del run_manager
        return [self._as_document(hit) for hit in self.rank(query)]

    def rank(self, query: str) -> list[dict]:
        query_tokens = tokenize(query, drop_generic=True)
        if not query_tokens:
            return []
        wants_personal = "personal" in query_tokens
        wants_home = "home" in query_tokens
        procedure = bool(re.search(r"\b(process|steps|how do i apply|how can i apply)\b", query, re.I))
        query_vector = embed(query)
        ranked: list[dict] = []
        unique_query = list(dict.fromkeys(query_tokens))
        for chunk in self.chunks:
            if chunk["status"] != "approved" or chunk["access"] != "public":
                continue
            if wants_personal and not wants_home and chunk["product"] == "home_loan":
                continue
            if wants_home and not wants_personal and chunk["product"] == "personal_loan":
                continue
            chunk_tokens = set(tokenize(chunk["text"], drop_generic=True))
            overlap = [token for token in unique_query if token in chunk_tokens]
            coverage = len(overlap) / len(unique_query)
            if coverage < 0.5:
                continue
            bonus = 0.0
            if wants_personal and chunk["product"] == "personal_loan":
                bonus += 0.05
            if wants_home and chunk["product"] == "home_loan":
                bonus += 0.05
            if procedure and chunk["doc_id"] == "DOC-PL-PROCESS":
                bonus += 0.10
            cosine = _cosine(query_vector, chunk["embedding"])
            score = coverage + bonus + 0.001 * max(cosine, 0)
            ranked.append({**chunk, "coverage": coverage, "score": score, "cosine": cosine})
        if not ranked:
            return []
        best = max(item["score"] for item in ranked)
        selected = [item for item in ranked if item["score"] >= best - 0.01]
        selected.sort(key=lambda item: item["score"], reverse=True)
        return selected[:3]

    @staticmethod
    def _as_document(hit: dict) -> Document:
        metadata = {
            "doc_id": hit["doc_id"],
            "title": hit["title"],
            "version": hit["version"],
            "product": hit["product"],
            "score": hit.get("score", 0),
        }
        return Document(page_content=hit["text"], metadata=metadata)


def persist_chunks(chunks: list[dict]) -> list[dict]:
    rows = []
    for chunk in chunks:
        rows.append(
            {
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "version": chunk["version"],
                "product": chunk["product"],
                "access": chunk["access"],
                "status": chunk["status"],
                "chunk_text": chunk["text"],
                "embedding_json": json.dumps(chunk["embedding"]),
                "content_hash": chunk["content_hash"],
            }
        )
    return rows
