"""Document ingestion: load markdown policies, chunk by section, embed with Voyage AI, store in Supabase."""

import os
import re
import time
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"
MAX_CHUNK_TOKENS = 800
VOYAGE_MODEL = "voyage-3"
EMBED_BATCH_SIZE = 8
EMBED_DELAY_SECONDS = 25
STORE_BATCH_SIZE = 20


def get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def get_voyage():
    return voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def extract_doc_id(text: str) -> str:
    """Extract document ID like HR-POL-001 from markdown header."""
    match = re.search(r"\*\*Document ID:\*\*\s*([\w-]+)", text)
    return match.group(1) if match else "UNKNOWN"


def extract_doc_title(text: str) -> str:
    """Extract title from first markdown H1."""
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled"


def chunk_document(filepath: Path) -> list[dict]:
    """Split a markdown document into section-aware chunks with metadata."""
    text = filepath.read_text(encoding="utf-8")
    doc_id = extract_doc_id(text)
    doc_title = extract_doc_title(text)

    # Split by ## headers (level 2 sections)
    section_pattern = re.compile(r"(?=^## \d+)", re.MULTILINE)
    raw_sections = section_pattern.split(text)

    chunks = []
    for section_text in raw_sections:
        section_text = section_text.strip()
        if not section_text or not section_text.startswith("## "):
            continue

        section_header = section_text.split("\n", 1)[0].strip("# ").strip()
        estimated_tokens = len(section_text.split()) * 1.3

        if estimated_tokens <= MAX_CHUNK_TOKENS:
            chunks.append({
                "content": section_text,
                "doc_id": doc_id,
                "doc_title": doc_title,
                "section": section_header,
                "subsection": None,
            })
        else:
            # Split further at ### subsection boundaries
            sub_pattern = re.compile(r"(?=^### )", re.MULTILINE)
            subsections = sub_pattern.split(section_text)

            for sub_text in subsections:
                sub_text = sub_text.strip()
                if not sub_text:
                    continue

                if sub_text.startswith("### "):
                    sub_header = sub_text.split("\n", 1)[0].strip("# ").strip()
                else:
                    sub_header = None

                chunks.append({
                    "content": sub_text,
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "section": section_header,
                    "subsection": sub_header,
                })

    return chunks


def load_all_chunks() -> list[dict]:
    """Load and chunk all markdown files from the knowledge base."""
    all_chunks = []
    for filepath in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        doc_chunks = chunk_document(filepath)
        all_chunks.extend(doc_chunks)
        print(f"  {filepath.name}: {len(doc_chunks)} chunks")
    return all_chunks


def embed_chunks(chunks: list[dict], vo: voyageai.Client) -> list[list[float]]:
    """Embed all chunks using Voyage AI in small batches with delays for rate limiting."""
    texts = [c["content"] for c in chunks]
    all_embeddings = []
    total_batches = (len(texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch_num = i // EMBED_BATCH_SIZE + 1
        batch = texts[i : i + EMBED_BATCH_SIZE]
        result = vo.embed(batch, model=VOYAGE_MODEL, input_type="document")
        all_embeddings.extend(result.embeddings)
        print(f"  Embedded batch {batch_num}/{total_batches} ({len(batch)} chunks, {result.total_tokens} tokens)")

        if i + EMBED_BATCH_SIZE < len(texts):
            print(f"  Waiting {EMBED_DELAY_SECONDS}s for rate limit...")
            time.sleep(EMBED_DELAY_SECONDS)

    return all_embeddings


def store_in_supabase(chunks: list[dict], embeddings: list[list[float]], supabase):
    """Insert chunks + embeddings into Supabase documents table."""
    # Clear existing documents
    supabase.table("documents").delete().neq("id", -1).execute()
    print("  Cleared existing documents")

    rows = []
    for i, chunk in enumerate(chunks):
        rows.append({
            "content": chunk["content"],
            "doc_id": chunk["doc_id"],
            "doc_title": chunk["doc_title"],
            "section": chunk["section"],
            "subsection": chunk["subsection"],
            "embedding": embeddings[i],
        })

    # Insert in batches
    for i in range(0, len(rows), STORE_BATCH_SIZE):
        batch = rows[i : i + STORE_BATCH_SIZE]
        supabase.table("documents").insert(batch).execute()
        print(f"  Inserted batch {i // STORE_BATCH_SIZE + 1} ({len(batch)} rows)")


def ingest():
    """Full ingestion pipeline: load, chunk, embed, store."""
    print("Loading and chunking documents...")
    chunks = load_all_chunks()
    print(f"Total chunks: {len(chunks)}\n")

    print("Embedding with Voyage AI...")
    vo = get_voyage()
    embeddings = embed_chunks(chunks, vo)
    print(f"Total embeddings: {len(embeddings)}\n")

    print("Storing in Supabase...")
    supabase = get_supabase()
    store_in_supabase(chunks, embeddings, supabase)
    print(f"Ingestion complete. {len(chunks)} chunks stored.\n")

    return chunks


if __name__ == "__main__":
    ingest()
