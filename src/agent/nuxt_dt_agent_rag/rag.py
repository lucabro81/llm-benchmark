"""BM25-based RAG tool for Vue.js DataTable documentation.

Identical to nuxt_form_agent_rag/rag.py but accepts rag_docs_path
as a constructor parameter so it can be pointed to any docs directory
(e.g. the shared rag_docs from the nuxt-dt-rag fixture).
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
    """Smolagents tool that searches Vue.js DataTable examples via BM25."""

    name = "query_rag"
    description = (
        "Search for Vue.js DataTable examples and patterns in the documentation. "
        "Returns 1–2 complete code examples most relevant to your query. "
        "Good queries: 'basic DataTable columns Column type', "
        "'currency formatter Intl.NumberFormat cell renderer', "
        "'status badge Record statusClasses conditional', "
        "'action columns createColumns handlers Button onClick', "
        "'DataTable wrapper defineProps createColumns'."
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

        corpus = [
            _tokenize(doc["name"] + " " + doc["content"])
            for doc in self.documents
        ]
        # BM25Plus avoids negative IDF scores on small corpora (unlike BM25Okapi).
        self._bm25 = BM25Plus(corpus)

    def forward(self, query: str) -> str:
        if not self.documents:
            return "No RAG documents available."

        tokens = _tokenize(query) if query.strip() else ["datatable"]
        scores = self._bm25.get_scores(tokens)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        top_idx, top_score = ranked[0]

        results = [self.documents[top_idx]]

        if len(ranked) > 1:
            second_idx, second_score = ranked[1]
            if top_score > 0 and second_score >= top_score * 0.5:
                results.append(self.documents[second_idx])

        parts = []
        for doc in results:
            parts.append(f"--- {doc['name']} ---\n{doc['content']}")
        return "\n\n".join(parts)
