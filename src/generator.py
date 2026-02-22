"""Answer generation using Claude with source citations."""

import os
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are an HR policy assistant for NorthStar Labs. Your role is to answer employee questions about company policies accurately and helpfully.

RULES:
1. Answer based ONLY on the provided policy excerpts. Do not use outside knowledge.
2. Cite the document ID and section number for every claim (e.g., "per HR-POL-001 Section 4.2").
3. If the answer is not in the provided context, say: "I don't have enough information in the available policies to answer this question. Please contact the People team for assistance."
4. If the answer spans multiple policies, cite all relevant sources.
5. Be precise with numbers, dates, and thresholds - these are compliance-sensitive.
6. Keep answers concise but complete."""

LOW_CONFIDENCE_DISCLAIMER = (
    "Note: I found limited relevant policy information for this question. "
    "Please verify this answer with the People team or refer to the source documents directly."
)


def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into context for the prompt."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk['doc_id']}] {chunk['doc_title']} - {chunk['section']}"
        if chunk.get("subsection"):
            source += f" > {chunk['subsection']}"
        context_parts.append(f"--- Source {i}: {source} ---\n{chunk['content']}")
    return "\n\n".join(context_parts)


def generate_answer(
    query: str, chunks: list[dict], min_confidence_score: float = 0.01
) -> dict:
    """Generate an answer using Claude based on retrieved chunks."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    context = build_context(chunks)

    # Check confidence based on retrieval scores
    avg_score = 0
    if chunks:
        scores = [c.get("rrf_score", c.get("score", 0)) for c in chunks]
        avg_score = sum(scores) / len(scores)

    low_confidence = avg_score < min_confidence_score

    user_message = f"Question: {query}\n\nPolicy excerpts:\n\n{context}"
    if low_confidence:
        user_message += f"\n\nIMPORTANT: The retrieval confidence is low. Preface your answer with this disclaimer: \"{LOW_CONFIDENCE_DISCLAIMER}\""

    start_time = time.time()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    latency_ms = (time.time() - start_time) * 1000

    answer_text = response.content[0].text

    sources = []
    for chunk in chunks:
        sources.append({
            "doc_id": chunk["doc_id"],
            "section": chunk["section"],
            "subsection": chunk.get("subsection"),
            "score": chunk.get("rrf_score", chunk.get("score", 0)),
        })

    return {
        "answer": answer_text,
        "sources": sources,
        "metadata": {
            "model": MODEL,
            "latency_ms": round(latency_ms),
            "low_confidence": low_confidence,
            "avg_retrieval_score": round(avg_score, 4),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
