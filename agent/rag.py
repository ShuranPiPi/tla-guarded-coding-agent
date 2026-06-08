"""Error-pattern retrieval used during Python repair.

When OpenAI embeddings and FAISS are available, retrieval uses vector search.
In Gemini-only or dependency-light environments it falls back to deterministic
keyword matching over the same curated knowledge base.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import List

KB_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "error_patterns.json"


def _load_patterns() -> List[dict]:
    with KB_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _to_document(entry: dict):
    from langchain_core.documents import Document

    text = f"Error: {entry['error']}\nCause: {entry['cause']}\nFix: {entry['fix']}"
    return Document(page_content=text, metadata=entry)


@lru_cache(maxsize=1)
def _vector_store():
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    docs = [_to_document(e) for e in _load_patterns()]
    embeddings = OpenAIEmbeddings(
        model=os.environ.get("AGENT_EMBED_MODEL", "text-embedding-3-small")
    )
    return FAISS.from_documents(docs, embeddings)


def retrieve_fixes(query: str, k: int = 3) -> List[dict]:
    """Return up to k error-pattern entries similar to `query`."""
    if not query.strip():
        return []
    if os.environ.get("OPENAI_API_KEY"):
        try:
            store = _vector_store()
            return [hit.metadata for hit in store.similarity_search(query, k=k)]
        except Exception:
            # Embeddings are a repair-quality optimization, not a workflow blocker.
            pass
    return _keyword_search(query, k=k)


def _keyword_search(query: str, k: int) -> List[dict]:
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]+", query.lower()))
    scored = []
    for entry in _load_patterns():
        haystack = f"{entry['error']} {entry['cause']} {entry['fix']}".lower()
        score = sum(1 for word in words if word in haystack)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored:
        return [entry for _, entry in scored[:k]]
    return _load_patterns()[:k]


def format_for_prompt(hits: List[dict]) -> str:
    if not hits:
        return "(no retrieved patterns)"
    lines = []
    for i, hit in enumerate(hits, 1):
        lines.append(f"[{i}] {hit['error']}\n    cause: {hit['cause']}\n    fix:   {hit['fix']}")
    return "\n".join(lines)
