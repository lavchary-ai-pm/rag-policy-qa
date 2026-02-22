"""FastAPI backend for RAG Policy Q&A."""

import json
import os
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import phoenix as px
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from phoenix.evals import (
    llm_classify,
    ClassificationTemplate,
    AnthropicModel,
)
from phoenix.client import Client as PhoenixClient
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="NorthStar Labs - AskHR API")

PHOENIX_ENABLED = bool(os.getenv("PHOENIX_API_KEY")) or not os.getenv("DISABLE_PHOENIX")

_cors_origins = ["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"]
if os.getenv("FRONTEND_URL"):
    _cors_origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Server-side context store keyed by span_id (LRU, max 100 entries)
_context_store: OrderedDict[str, str] = OrderedDict()
MAX_CONTEXT_STORE = 100


def _store_context(span_id: str, context: str):
    _context_store[span_id] = context
    if len(_context_store) > MAX_CONTEXT_STORE:
        _context_store.popitem(last=False)


@app.on_event("startup")
def startup():
    from src.pipeline import launch_phoenix, init_tracing
    if PHOENIX_ENABLED:
        if not os.getenv("PHOENIX_API_KEY"):
            launch_phoenix()
        init_tracing()


class AskRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    doc_id: str
    section: str
    subsection: str | None = None
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    latency_ms: int
    span_id: str | None = None


SAMPLE_QUESTIONS = [
    "What is the 401k employer match?",
    "How much parental leave do I get?",
    "Can I use ChatGPT for work?",
    "What happens to my salary if I move cities?",
    "What is the gift acceptance policy?",
]


@app.get("/api/suggestions")
def get_suggestions():
    return {"suggestions": SAMPLE_QUESTIONS}


@app.get("/api/phoenix-url")
def phoenix_url():
    return {"url": "http://localhost:6006"}


@app.post("/api/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    from src.pipeline import ask
    result = ask(req.question, trace=PHOENIX_ENABLED)

    span_id = result["metadata"].get("span_id") or str(uuid.uuid4())

    # Store context server-side for later eval requests
    if result.get("contexts"):
        _store_context(span_id, "\n\n".join(result["contexts"]))

    sources = [
        SourceItem(
            doc_id=s["doc_id"],
            section=s["section"],
            subsection=s.get("subsection"),
            score=round(s["score"], 4),
        )
        for s in result["sources"]
    ]

    return AskResponse(
        answer=result["answer"],
        sources=sources,
        latency_ms=result["metadata"]["latency_ms"],
        span_id=span_id,
    )


FEEDBACK_FILE = Path(__file__).parent / "eval" / "feedback.jsonl"


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    rating: str


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": req.question,
        "answer": req.answer,
        "rating": req.rating,
    }
    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "ok"}


# --- Phoenix Eval Infrastructure ---

_eval_model = None


def get_eval_model():
    """Lazy-init the Phoenix eval model."""
    global _eval_model
    if _eval_model is None:
        _eval_model = AnthropicModel(model="claude-sonnet-4-5-20250929", top_p=None)
    return _eval_model


# --- 3-Level Eval Templates (Industry-standard: 1.0 / 0.5 / 0.0) ---

FAITHFULNESS_TEMPLATE = ClassificationTemplate(
    rails=["factual", "mixed", "hallucinated"],
    template=(
        "You are evaluating whether an AI assistant's answer is grounded in the "
        "provided reference context.\n\n"
        "[BEGIN DATA]\n"
        "************\n"
        "[Question]: {input}\n"
        "************\n"
        "[Reference Context]: {reference}\n"
        "************\n"
        "[Answer]: {output}\n"
        "************\n"
        "[END DATA]\n\n"
        "Evaluate the answer against the reference context:\n"
        "- 'factual': Every claim in the answer is supported by the context. "
        "No information is fabricated or assumed beyond what the context provides.\n"
        "- 'mixed': Some claims are supported by the context, but the answer also "
        "contains claims that are not found in or contradict the context.\n"
        "- 'hallucinated': The answer contains significant claims that are fabricated, "
        "contradicted by, or entirely unsupported by the context.\n\n"
        "First, briefly explain your reasoning in 1-2 sentences. "
        "Then on a new line, provide your classification as one of: factual, mixed, hallucinated."
    ),
)

QA_CORRECTNESS_TEMPLATE = ClassificationTemplate(
    rails=["correct", "partially_correct", "incorrect"],
    template=(
        "You are evaluating whether an AI assistant's answer matches the expected "
        "ground truth answer.\n\n"
        "[BEGIN DATA]\n"
        "************\n"
        "[Question]: {input}\n"
        "************\n"
        "[Expected Answer]: {reference}\n"
        "************\n"
        "[Actual Answer]: {output}\n"
        "************\n"
        "[END DATA]\n\n"
        "Compare the actual answer to the expected answer:\n"
        "- 'correct': The answer captures all key facts and conclusions from the "
        "expected answer. Minor wording differences are acceptable.\n"
        "- 'partially_correct': The answer captures some key facts from the expected "
        "answer but misses important details, conditions, or nuances.\n"
        "- 'incorrect': The answer contradicts the expected answer, misses the main "
        "point entirely, or provides substantially wrong information.\n\n"
        "First, briefly explain your reasoning in 1-2 sentences. "
        "Then on a new line, provide your classification as one of: correct, partially_correct, incorrect."
    ),
)

COMPLETENESS_TEMPLATE = ClassificationTemplate(
    rails=["complete", "partial", "incomplete"],
    template=(
        "You are evaluating whether an AI assistant's answer fully addresses all parts "
        "of the user's question, given the available context.\n\n"
        "[BEGIN DATA]\n"
        "************\n"
        "[Question]: {input}\n"
        "************\n"
        "[Available Context]: {reference}\n"
        "************\n"
        "[Answer]: {output}\n"
        "************\n"
        "[END DATA]\n\n"
        "Evaluate how completely the answer addresses the question:\n"
        "- 'complete': The answer addresses every aspect and sub-question using the "
        "information available in the context. Nothing answerable is left out.\n"
        "- 'partial': The answer addresses the main question but misses some aspects, "
        "sub-questions, or important conditions that ARE present in the context.\n"
        "- 'incomplete': The answer misses the core question or leaves out most of the "
        "relevant information available in the context.\n\n"
        "First, briefly explain your reasoning in 1-2 sentences. "
        "Then on a new line, provide your classification as one of: complete, partial, incomplete."
    ),
)

# Score mappings for 3-level evals
FAITHFULNESS_SCORES = {"factual": 1.0, "mixed": 0.5, "hallucinated": 0.0}
QA_CORRECTNESS_SCORES = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}
COMPLETENESS_SCORES = {"complete": 1.0, "partial": 0.5, "incomplete": 0.0}


def run_hallucination_eval(question: str, rag_answer: str, context: str) -> dict:
    """Run faithfulness eval: is the answer grounded in context?"""
    model = get_eval_model()
    df = pd.DataFrame([{"input": question, "reference": context, "output": rag_answer}])
    result = llm_classify(
        data=df, model=model,
        template=FAITHFULNESS_TEMPLATE,
        rails=FAITHFULNESS_TEMPLATE.rails,
        provide_explanation=True, run_sync=True, concurrency=1,
    )
    label = result["label"].iloc[0] or "error"
    return {
        "label": label,
        "score": FAITHFULNESS_SCORES.get(label),
        "explanation": result["explanation"].iloc[0] or "",
    }


def run_qa_correctness_eval(question: str, rag_answer: str, ground_truth: str) -> dict:
    """Run QA correctness eval: does the answer match ground truth?"""
    model = get_eval_model()
    df = pd.DataFrame([{"input": question, "reference": ground_truth, "output": rag_answer}])
    result = llm_classify(
        data=df, model=model,
        template=QA_CORRECTNESS_TEMPLATE,
        rails=QA_CORRECTNESS_TEMPLATE.rails,
        provide_explanation=True, run_sync=True, concurrency=1,
    )
    label = result["label"].iloc[0] or "error"
    return {
        "label": label,
        "score": QA_CORRECTNESS_SCORES.get(label),
        "explanation": result["explanation"].iloc[0] or "",
    }


def run_completeness_eval(question: str, rag_answer: str, context: str) -> dict:
    """Run completeness eval: does the answer address all parts of the question?"""
    model = get_eval_model()
    df = pd.DataFrame([{"input": question, "reference": context, "output": rag_answer}])
    result = llm_classify(
        data=df, model=model,
        template=COMPLETENESS_TEMPLATE,
        rails=COMPLETENESS_TEMPLATE.rails,
        provide_explanation=True, run_sync=True, concurrency=1,
    )
    label = result["label"].iloc[0] or "error"
    return {
        "label": label,
        "score": COMPLETENESS_SCORES.get(label),
        "explanation": result["explanation"].iloc[0] or "",
    }


def log_evals_to_phoenix(span_id: str, hallucination: dict, qa_correctness: dict | None = None, completeness: dict | None = None):
    """Log eval results to Phoenix via the span annotations API."""
    annotations = [
        {
            "name": "Faithfulness",
            "annotator_kind": "LLM",
            "span_id": span_id,
            "result": {
                "label": hallucination["label"],
                "score": hallucination.get("score", FAITHFULNESS_SCORES.get(hallucination["label"], 0.0)),
                "explanation": hallucination["explanation"],
            },
        },
    ]

    if qa_correctness:
        annotations.append({
            "name": "QA Correctness",
            "annotator_kind": "LLM",
            "span_id": span_id,
            "result": {
                "label": qa_correctness["label"],
                "score": qa_correctness.get("score", QA_CORRECTNESS_SCORES.get(qa_correctness["label"], 0.0)),
                "explanation": qa_correctness["explanation"],
            },
        })

    if completeness:
        annotations.append({
            "name": "Completeness",
            "annotator_kind": "LLM",
            "span_id": span_id,
            "result": {
                "label": completeness["label"],
                "score": completeness.get("score", COMPLETENESS_SCORES.get(completeness["label"], 0.0)),
                "explanation": completeness["explanation"],
            },
        })

    if not PHOENIX_ENABLED:
        return
    try:
        phoenix_api_key = os.getenv("PHOENIX_API_KEY")
        phoenix_space = os.getenv("PHOENIX_SPACE", "lavchary")
        if phoenix_api_key:
            client = PhoenixClient(
                base_url=f"https://app.phoenix.arize.com/s/{phoenix_space}",
                headers={"Authorization": f"Bearer {phoenix_api_key}"},
            )
        else:
            client = PhoenixClient()
        client.spans.log_span_annotations(span_annotations=annotations)
    except Exception:
        pass


# --- Chat Eval Endpoint (on-demand per Q&A) ---

class ChatEvalRequest(BaseModel):
    question: str
    answer: str
    span_id: str


@app.post("/api/eval-chat")
def eval_chat(req: ChatEvalRequest):
    context = _context_store.get(req.span_id, "")
    hallucination = run_hallucination_eval(req.question, req.answer, context)
    completeness = run_completeness_eval(req.question, req.answer, context)
    log_evals_to_phoenix(req.span_id, hallucination=hallucination, completeness=completeness)
    return {"status": "ok", "evals": {"hallucination": hallucination, "completeness": completeness}}


# --- Eval Tab Endpoint (test cases with ground truth) ---

class EvalRunRequest(BaseModel):
    question: str
    ground_truth: str


@app.post("/api/eval-run")
def eval_run(req: EvalRunRequest):
    from src.pipeline import ask
    result = ask(req.question, trace=PHOENIX_ENABLED)

    span_id = result["metadata"].get("span_id")

    sources = [
        {
            "doc_id": s["doc_id"],
            "section": s["section"],
            "subsection": s.get("subsection"),
            "score": round(s["score"], 4),
        }
        for s in result["sources"]
    ]

    context = "\n\n".join(result.get("contexts", []))
    hallucination = run_hallucination_eval(req.question, result["answer"], context)
    qa_correctness = run_qa_correctness_eval(req.question, result["answer"], req.ground_truth)
    completeness = run_completeness_eval(req.question, result["answer"], context)
    evals = {"hallucination": hallucination, "qa_correctness": qa_correctness, "completeness": completeness}

    if span_id:
        log_evals_to_phoenix(span_id, hallucination=hallucination, qa_correctness=qa_correctness, completeness=completeness)

    return {
        "answer": result["answer"],
        "ground_truth": req.ground_truth,
        "sources": sources,
        "latency_ms": result["metadata"]["latency_ms"],
        "evals": evals,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
