"""CLI entry point for RAG Policy Q&A system."""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()


def cmd_ask(question: str):
    """Ask a single question."""
    from src.pipeline import ask

    result = ask(question, trace=False)
    print(f"\nAnswer:\n{result['answer']}\n")
    print("Sources:")
    for src in result["sources"]:
        label = f"  [{src['doc_id']}] {src['section']}"
        if src.get("subsection"):
            label += f" > {src['subsection']}"
        print(f"{label} (score: {src['score']:.4f})")
    print(f"\nLatency: {result['metadata']['latency_ms']}ms")
    print(f"Tokens: {result['metadata']['input_tokens']} in / {result['metadata']['output_tokens']} out")


def cmd_ingest():
    """Run document ingestion pipeline."""
    from src.ingest import ingest

    ingest()


def cmd_evaluate():
    """Run full evaluation suite."""
    from src.evaluate import run_full_evaluation

    run_full_evaluation()


def cmd_phoenix():
    """Launch Phoenix UI and run interactive Q&A with tracing."""
    from src.pipeline import ask, launch_phoenix

    session = launch_phoenix()
    print(f"\nPhoenix UI: {session.url}")
    print("Ask questions (traces will appear in Phoenix). Type 'quit' to exit.\n")

    while True:
        question = input("Q: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        result = ask(question, trace=True)
        print(f"\nA: {result['answer']}\n")
        for src in result["sources"]:
            label = f"  [{src['doc_id']}] {src['section']}"
            if src.get("subsection"):
                label += f" > {src['subsection']}"
            print(label)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="RAG Policy Q&A - NorthStar Labs"
    )
    parser.add_argument("question", nargs="?", help="Question to ask")
    parser.add_argument("--ingest", action="store_true", help="Run document ingestion")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation suite")
    parser.add_argument("--phoenix", action="store_true", help="Launch Phoenix UI with interactive Q&A")

    args = parser.parse_args()

    if args.ingest:
        cmd_ingest()
    elif args.evaluate:
        cmd_evaluate()
    elif args.phoenix:
        cmd_phoenix()
    elif args.question:
        cmd_ask(args.question)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
