"""BM25-based RAG tool for the veevalidate-zod-form-nuxt-rag agent fixture.

Indexes all files in rag_docs/ and retrieves the top-1 (or top-2 if close)
most relevant document for any free-text query.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from rank_bm25 import BM25Plus
from smolagents import Tool


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alphanumeric chars."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


class QueryRagTool(Tool):
    """Smolagents tool that searches Vue.js form examples via BM25."""

    name = "query_rag"
    description = (
        "Search for Vue.js form examples and patterns in the documentation. "
        "Returns 1–2 complete code examples most relevant to your query. "
        "Good queries: 'basic form Form FormFields FormActions', "
        "'checkbox reveals conditional field v-if', "
        "'radio group options array', "
        "'zod schema optional superRefine conditional validation', "
        "'textarea full form all component types'."
    )
    inputs: Dict[str, Any] = {
        "query": {"type": "string", "description": "Keywords describing the pattern you need."},
    }
    output_type = "string"

    def __init__(self, rag_docs_path: Path):
        super().__init__()
        if not rag_docs_path.exists():
            raise FileNotFoundError(f"rag_docs directory not found: {rag_docs_path}")

        self.documents: List[Dict[str, str]] = []
        for path in sorted(rag_docs_path.iterdir()):
            if path.is_file():
                self.documents.append({"name": path.name, "content": path.read_text()})

        # Build BM25 index over tokenized document content + filename
        corpus = [
            _tokenize(doc["name"] + " " + doc["content"])
            for doc in self.documents
        ]
        # BM25Plus avoids negative IDF scores on small corpora (unlike BM25Okapi).
        self._bm25 = BM25Plus(corpus)

    def forward(self, query: str) -> str:
        if not self.documents:
            return "No RAG documents available."

        tokens = _tokenize(query) if query.strip() else ["form"]
        scores = self._bm25.get_scores(tokens)

        # Sort by score descending
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        top_idx, top_score = ranked[0]

        results = [self.documents[top_idx]]

        # Include second result if its score is ≥50% of the top score
        if len(ranked) > 1:
            second_idx, second_score = ranked[1]
            if top_score > 0 and second_score >= top_score * 0.5:
                results.append(self.documents[second_idx])

        parts = []
        for doc in results:
            parts.append(f"--- {doc['name']} ---\n{doc['content']}")
        return "\n\n".join(parts)
