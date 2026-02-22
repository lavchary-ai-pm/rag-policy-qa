"""RAG evaluation using Ragas metrics with Anthropic Claude."""

import json
import os
import time
from pathlib import Path

import voyageai
from anthropic import Anthropic
from dotenv import load_dotenv
from ragas import evaluate
from ragas.dataset_schema import EvaluationDataset
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms import llm_factory
from ragas.metrics._faithfulness import Faithfulness
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.metrics._context_precision import ContextPrecision
from ragas.metrics._context_recall import ContextRecall

from src.pipeline import ask

load_dotenv()

EVAL_DIR = Path(__file__).parent.parent / "eval"
TEST_QUESTIONS_PATH = EVAL_DIR / "test_questions.json"
EVAL_MODEL = "claude-sonnet-4-5-20250929"
VOYAGE_MODEL = "voyage-3"


class VoyageEmbeddings(BaseRagasEmbeddings):
    """Voyage AI embedding wrapper for Ragas."""

    def __init__(self):
        self.client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    def embed_query(self, text: str) -> list[float]:
        result = self.client.embed([text], model=VOYAGE_MODEL, input_type="query")
        return result.embeddings[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), 8):
            batch = texts[i:i + 8]
            result = self.client.embed(batch, model=VOYAGE_MODEL, input_type="document")
            all_embeddings.extend(result.embeddings)
            if i + 8 < len(texts):
                time.sleep(25)
        return all_embeddings

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)


def load_test_questions() -> list[dict]:
    """Load test questions from JSON file."""
    with open(TEST_QUESTIONS_PATH) as f:
        return json.load(f)


QUERY_DELAY_SECONDS = 25


def run_pipeline_on_questions(questions: list[dict]) -> list[dict]:
    """Run the RAG pipeline on all test questions, collecting results."""
    results = []
    for i, q in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] {q['question'][:60]}...")
        result = ask(q["question"], trace=False)
        results.append({
            "user_input": q["question"],
            "response": result["answer"],
            "retrieved_contexts": result["contexts"],
            "reference": q["ground_truth"],
            "difficulty": q["difficulty"],
            "source_docs": q["source_docs"],
        })
        if i < len(questions):
            print(f"    Waiting {QUERY_DELAY_SECONDS}s for rate limit...")
            time.sleep(QUERY_DELAY_SECONDS)
    return results


def run_evaluation(results: list[dict]) -> dict:
    """Run Ragas evaluation on pipeline results."""
    dataset = EvaluationDataset.from_list(results)

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    llm = llm_factory(
        model=EVAL_MODEL,
        provider="anthropic",
        client=client,
    )
    embeddings = VoyageEmbeddings()

    metrics = [
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm, embeddings=embeddings),
        ContextPrecision(llm=llm),
        ContextRecall(llm=llm),
    ]

    eval_result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        show_progress=True,
    )

    return eval_result


def print_results(eval_result, results: list[dict]):
    """Print evaluation results summary."""
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    # Overall scores
    print("\nOverall Metrics:")
    for metric_name, score in eval_result.scores.items():
        avg = sum(score) / len(score) if score else 0
        print(f"  {metric_name}: {avg:.3f}")

    # Per-difficulty breakdown
    df = eval_result.to_pandas()
    print("\nPer-Difficulty Breakdown:")
    for difficulty in ["simple", "cross-document", "conditional"]:
        mask = [r["difficulty"] == difficulty for r in results]
        subset = df[mask]
        if len(subset) > 0:
            print(f"\n  {difficulty.upper()} ({len(subset)} questions):")
            for col in df.columns:
                if col not in ["user_input", "response", "retrieved_contexts", "reference"]:
                    values = subset[col].dropna()
                    if len(values) > 0:
                        print(f"    {col}: {values.mean():.3f}")

    print("\n" + "=" * 60)

    # Build summary for UI
    summary = {"overall": {}, "by_difficulty": {}}
    for metric_name, score in eval_result.scores.items():
        summary["overall"][metric_name] = round(sum(score) / len(score), 3) if score else 0

    for difficulty in ["simple", "cross-document", "conditional"]:
        mask = [r["difficulty"] == difficulty for r in results]
        subset = df[mask]
        if len(subset) > 0:
            diff_scores = {}
            for col in df.columns:
                if col not in ["user_input", "response", "retrieved_contexts", "reference"]:
                    values = subset[col].dropna()
                    if len(values) > 0:
                        diff_scores[col] = round(values.mean(), 3)
            summary["by_difficulty"][difficulty] = {
                "count": len(subset),
                "scores": diff_scores,
            }

    # Save detailed results
    output_path = EVAL_DIR / "eval_results.json"
    detail_records = json.loads(df.to_json(orient="records"))
    for i, rec in enumerate(detail_records):
        rec["difficulty"] = results[i]["difficulty"]
    output = {
        "summary": summary,
        "questions": detail_records,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Detailed results saved to: {output_path}")


def run_full_evaluation():
    """End-to-end evaluation: load questions, run pipeline, evaluate."""
    print("Loading test questions...")
    questions = load_test_questions()
    print(f"Loaded {len(questions)} questions\n")

    print("Running RAG pipeline on all questions...")
    results = run_pipeline_on_questions(questions)
    print(f"\nPipeline complete. Running Ragas evaluation...\n")

    eval_result = run_evaluation(results)
    print_results(eval_result, results)
    return eval_result


if __name__ == "__main__":
    run_full_evaluation()
