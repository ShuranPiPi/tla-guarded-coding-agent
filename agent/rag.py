"""Tiny RAG retriever over a curated error-pattern knowledge base.

At startup we embed each `{error, cause, fix}` entry in
``knowledge_base/error_patterns.json`` with OpenAI embeddings and build an
in-memory FAISS index. At repair time we query with the latest traceback and
return the top-k `(error, cause, fix)` tuples to be pasted into the repair
prompt.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

KB_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "error_patterns.json"


def _load_patterns() -> List[dict]:
    with KB_PATH.open() as f:
        return json.load(f)


def _to_document(entry: dict) -> Document:
    # Pack everything into page_content so retrieval matches on the full text.
    text = f"Error: {entry['error']}\nCause: {entry['cause']}\nFix: {entry['fix']}"
    return Document(page_content=text, metadata=entry)


@lru_cache(maxsize=1)
def _vector_store() -> FAISS:
    docs = [_to_document(e) for e in _load_patterns()]
    embeddings = OpenAIEmbeddings(
        model=os.environ.get("AGENT_EMBED_MODEL", "text-embedding-3-small")
    )
    return FAISS.from_documents(docs, embeddings)


def retrieve_fixes(query: str, k: int = 3) -> List[dict]:
    """Return up to k error-pattern entries most similar to `query`."""
    if not query.strip():
        return []
    store = _vector_store()
    hits = store.similarity_search(query, k=k)
    return [h.metadata for h in hits]


def format_for_prompt(hits: List[dict]) -> str:
    if not hits:
        return "(no retrieved patterns)"
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(f"[{i}] {h['error']}\n    cause: {h['cause']}\n    fix:   {h['fix']}")
    return "\n".join(lines)
