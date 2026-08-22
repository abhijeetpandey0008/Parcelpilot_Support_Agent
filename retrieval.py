"""
Simple, dependency-light retrieval over the document chunks.
The data pack is six short PDFs -- a full vector DB would be overkill,
so this uses TF-IDF + cosine similarity, which is transparent, fast,
and needs no external embedding calls.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_loader import Chunk, load_document_chunks, AUTHORITY_RANK


class DocumentIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([c.text for c in chunks])

    def search(self, query: str, account_id: str | None, top_k: int = 5) -> list[dict]:
        """Search all chunks, but only surface a contract chunk if it
        belongs to the requesting account (enforced here, not just by prompt)."""
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix)[0]

        results = []
        for chunk, score in zip(self.chunks, scores):
            if chunk.doc_type == "contract" and chunk.account_id != account_id:
                continue  # access control: never surface another account's contract
            if score <= 0:
                continue
            results.append((score, chunk))

        results.sort(key=lambda pair: pair[0], reverse=True)
        top = results[:top_k]

        return [
            {
                "source": r[1].title,
                "section": r[1].section,
                "doc_type": r[1].doc_type,
                "status": r[1].status,
                "authority_rank": AUTHORITY_RANK.get(r[1].doc_type, 9),
                "relevance": round(float(r[0]), 3),
                "text": r[1].text,
            }
            for r in top
        ]


_index: DocumentIndex | None = None


def get_index() -> DocumentIndex:
    global _index
    if _index is None:
        _index = DocumentIndex(load_document_chunks())
    return _index
