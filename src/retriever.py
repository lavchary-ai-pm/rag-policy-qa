"""Hybrid retrieval: Supabase pgvector (semantic) + BM25 (keyword) with Reciprocal Rank Fusion."""

import os
from rank_bm25 import BM25Okapi
import voyageai
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

VOYAGE_MODEL = "voyage-3"
RRF_K = 60  # Reciprocal Rank Fusion constant


def get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def get_voyage():
    return voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


class HybridRetriever:
    """Combines semantic search (Supabase pgvector) with keyword search (BM25)."""

    def __init__(self):
        self.supabase = get_supabase()
        self.vo = get_voyage()
        self.bm25 = None
        self.bm25_chunks = []
        self._build_bm25_index()

    def _build_bm25_index(self):
        """Load all chunks from Supabase and build BM25 index."""
        response = (
            self.supabase.table("documents")
            .select("id, content, doc_id, doc_title, section, subsection")
            .execute()
        )
        self.bm25_chunks = response.data
        tokenized = [chunk["content"].lower().split() for chunk in self.bm25_chunks]
        self.bm25 = BM25Okapi(tokenized)
        print(f"BM25 index built with {len(self.bm25_chunks)} chunks")

    def _semantic_search(self, query: str, top_n: int = 10) -> list[dict]:
        """Search Supabase pgvector for semantically similar chunks."""
        query_embedding = self.vo.embed(
            [query], model=VOYAGE_MODEL, input_type="query"
        ).embeddings[0]

        response = self.supabase.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.3,
                "match_count": top_n,
            },
        ).execute()

        results = []
        for row in response.data:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "doc_id": row["doc_id"],
                "doc_title": row["doc_title"],
                "section": row["section"],
                "subsection": row.get("subsection"),
                "score": row["similarity"],
                "source": "semantic",
            })
        return results

    def _keyword_search(self, query: str, top_n: int = 10) -> list[dict]:
        """Search using BM25 keyword matching."""
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        scored_chunks = list(zip(range(len(self.bm25_chunks)), scores))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_chunks[:top_n]

        results = []
        for idx, score in top_results:
            if score <= 0:
                continue
            chunk = self.bm25_chunks[idx]
            results.append({
                "id": chunk["id"],
                "content": chunk["content"],
                "doc_id": chunk["doc_id"],
                "doc_title": chunk["doc_title"],
                "section": chunk["section"],
                "subsection": chunk.get("subsection"),
                "score": float(score),
                "source": "keyword",
            })
        return results

    def _reciprocal_rank_fusion(
        self, semantic_results: list[dict], keyword_results: list[dict]
    ) -> list[dict]:
        """Merge semantic and keyword results using Reciprocal Rank Fusion."""
        rrf_scores: dict[int, float] = {}
        result_map: dict[int, dict] = {}

        for rank, result in enumerate(semantic_results):
            doc_id = result["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (RRF_K + rank + 1)
            result_map[doc_id] = result

        for rank, result in enumerate(keyword_results):
            doc_id = result["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (RRF_K + rank + 1)
            if doc_id not in result_map:
                result_map[doc_id] = result

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        fused = []
        for doc_id in sorted_ids:
            result = result_map[doc_id].copy()
            result["rrf_score"] = rrf_scores[doc_id]
            result["source"] = "hybrid"
            fused.append(result)

        return fused

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid retrieval: semantic + keyword, merged with RRF."""
        semantic_results = self._semantic_search(query, top_n=10)
        keyword_results = self._keyword_search(query, top_n=10)
        fused = self._reciprocal_rank_fusion(semantic_results, keyword_results)
        return fused[:top_k]
