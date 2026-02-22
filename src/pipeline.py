"""End-to-end RAG pipeline with Arize Phoenix tracing."""

import os
import phoenix as px
from phoenix.otel import register
from openinference.instrumentation import (
    OITracer,
    TraceConfig,
    get_retriever_attributes,
    get_input_attributes,
)
from openinference.semconv.trace import OpenInferenceSpanKindValues

from src.retriever import HybridRetriever
from src.generator import generate_answer

_retriever = None
_oi_tracer = None
_phoenix_session = None


def init_tracing():
    """Initialize Phoenix tracing. Returns the OITracer.

    Uses Phoenix Cloud if PHOENIX_API_KEY is set, otherwise local Phoenix.
    """
    global _oi_tracer
    if _oi_tracer is not None:
        return _oi_tracer

    phoenix_api_key = os.getenv("PHOENIX_API_KEY")
    phoenix_space = os.getenv("PHOENIX_SPACE", "lavchary")
    if phoenix_api_key:
        # Set env vars so register() auto-detects Phoenix Cloud.
        # IMPORTANT: Do NOT pass endpoint= explicitly - that bypasses
        # the known-provider logic that appends /v1/traces to the URL.
        os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = (
            f"https://app.phoenix.arize.com/s/{phoenix_space}"
        )
        os.environ["PHOENIX_API_KEY"] = phoenix_api_key
        tracer_provider = register(
            project_name="rag-policy-qa",
            batch=True,
        )
    else:
        tracer_provider = register(
            project_name="rag-policy-qa",
            batch=False,
        )

    tracer = tracer_provider.get_tracer(__name__)
    _oi_tracer = OITracer(tracer, TraceConfig())
    return _oi_tracer


def get_retriever() -> HybridRetriever:
    """Lazy-init the retriever."""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def launch_phoenix():
    """Launch Phoenix as a separate process for reliable UI serving."""
    import subprocess
    import socket
    import time

    # Check if Phoenix is already serving on 6006
    def _phoenix_ready():
        try:
            with socket.create_connection(("localhost", 6006), timeout=1):
                return True
        except OSError:
            return False

    if _phoenix_ready():
        print("Phoenix UI already running at: http://localhost:6006")
        return

    subprocess.Popen(
        ["phoenix", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 10s for Phoenix to become ready
    for _ in range(20):
        if _phoenix_ready():
            break
        time.sleep(0.5)

    print("Phoenix UI running at: http://localhost:6006")


def ask(question: str, top_k: int = 5, trace: bool = True) -> dict:
    """Ask a question against the policy knowledge base.

    Returns:
        dict with keys: answer, sources, contexts, metadata
    """
    if trace:
        oi_tracer = init_tracing()
        return _ask_with_tracing(question, top_k, oi_tracer)
    return _ask_no_tracing(question, top_k)


def _ask_no_tracing(question: str, top_k: int) -> dict:
    """RAG pipeline without tracing."""
    retriever = get_retriever()
    chunks = retriever.retrieve(question, top_k=top_k)
    result = generate_answer(question, chunks)
    result["contexts"] = [c["content"] for c in chunks]
    return result


def _ask_with_tracing(question: str, top_k: int, oi_tracer: OITracer) -> dict:
    """RAG pipeline with Phoenix tracing spans."""
    retriever = get_retriever()

    with oi_tracer.start_as_current_span(
        name="rag_pipeline",
        openinference_span_kind=OpenInferenceSpanKindValues.CHAIN,
        attributes=get_input_attributes(question),
    ) as chain_span:
        span_context = chain_span.get_span_context()
        span_id = format(span_context.span_id, '016x')

        # Retrieval span
        with oi_tracer.start_as_current_span(
            name="hybrid_retrieve",
            openinference_span_kind=OpenInferenceSpanKindValues.RETRIEVER,
            attributes=get_input_attributes(question),
        ) as retriever_span:
            chunks = retriever.retrieve(question, top_k=top_k)
            phoenix_docs = [
                {
                    "id": str(c["id"]),
                    "content": c["content"],
                    "metadata": {
                        "doc_id": c["doc_id"],
                        "section": c["section"],
                    },
                    "score": c.get("rrf_score", c.get("score", 0)),
                }
                for c in chunks
            ]
            retriever_span.set_attributes(
                get_retriever_attributes(documents=phoenix_docs)
            )

        # Generation span
        with oi_tracer.start_as_current_span(
            name="generate_answer",
            openinference_span_kind=OpenInferenceSpanKindValues.LLM,
        ) as llm_span:
            llm_span.set_input(value=question)
            result = generate_answer(question, chunks)
            llm_span.set_output(value=result["answer"])
            llm_span.set_attribute("llm.model_name", result["metadata"]["model"])
            llm_span.set_attribute("llm.token_count.prompt", result["metadata"]["input_tokens"])
            llm_span.set_attribute("llm.token_count.completion", result["metadata"]["output_tokens"])
            llm_span.set_attribute("llm.token_count.total", result["metadata"]["input_tokens"] + result["metadata"]["output_tokens"])

        chain_span.set_output(value=result["answer"])

    result["contexts"] = [c["content"] for c in chunks]
    result["metadata"]["span_id"] = span_id
    return result
