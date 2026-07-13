"""
ingest_rag.py
─────────────
RAG ingestion pipeline — reads markdown files from data/barca_knowledge/,
chunks them into overlapping segments, embeds with OpenAI text-embedding-3-small,
and upserts into the knowledge_chunks table.

Usage:
    python scripts/ingest_rag.py
    python scripts/ingest_rag.py --knowledge-dir data/barca_knowledge --chunk-size 500
"""
import argparse
import asyncio
import sys
import textwrap
from pathlib import Path

import asyncpg
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.config import settings

# ─── Text chunking ────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """
    Simple recursive character-level chunker.
    Splits on paragraph breaks first, then sentences, then words.
    """
    # Normalise newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            # If a single paragraph exceeds chunk_size, split by sentence
            if len(para) > chunk_size:
                sentences = para.replace(". ", ".\n").split("\n")
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current = (current + " " + sent).strip() if current else sent
                    else:
                        if current:
                            chunks.append(current)
                        # Hard-wrap if still too long
                        current = sent
                        if len(current) > chunk_size:
                            for sub in textwrap.wrap(current, chunk_size):
                                chunks.append(sub)
                            current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    # Add overlap: prepend last `overlap` chars of prev chunk to next chunk
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            overlapped.append(tail + " " + chunks[i])
        return overlapped

    return chunks


# ─── Embedding ────────────────────────────────────────────────────────────────
async def embed_batch(
    client: AsyncOpenAI, texts: list[str]
) -> list[list[float]]:
    """Embed a batch of texts (max 2048 inputs per request)."""
    resp = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in resp.data]


# ─── Main ─────────────────────────────────────────────────────────────────────
async def main(knowledge_dir: Path, chunk_size: int, overlap: int, batch_size: int):
    if not knowledge_dir.exists():
        print(f"❌ Knowledge directory not found: {knowledge_dir}")
        sys.exit(1)

    md_files = list(knowledge_dir.glob("**/*.md"))
    if not md_files:
        print(f"❌ No .md files found in {knowledge_dir}")
        sys.exit(1)

    print(f"📚 Found {len(md_files)} knowledge file(s)\n")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    pool   = await asyncpg.create_pool(dsn=settings.database_url)

    # Clear existing chunks (re-ingest = fresh start)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE knowledge_chunks RESTART IDENTITY")
    print("  ✓ Cleared existing knowledge_chunks\n")

    total_chunks = 0

    for md_file in md_files:
        print(f"  Processing {md_file.name} …")
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        print(f"    → {len(chunks)} chunks")

        # Process in batches
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            embeddings = await embed_batch(client, batch)

            async with pool.acquire() as conn:
                for idx, (chunk, embedding) in enumerate(
                    zip(batch, embeddings), start=batch_start
                ):
                    await conn.execute(
                        """
                        INSERT INTO knowledge_chunks
                            (source_file, chunk_index, content, embedding)
                        VALUES ($1, $2, $3, $4::vector)
                        """,
                        md_file.name,
                        idx,
                        chunk,
                        str(embedding),
                    )
            print(f"    → Embedded batch {batch_start}–{batch_start+len(batch)-1}")

        total_chunks += len(chunks)

    await pool.close()
    print(f"\n✅ RAG ingestion complete — {total_chunks} chunks embedded and stored.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest markdown docs into pgvector")
    parser.add_argument(
        "--knowledge-dir",
        default="data/barca_knowledge",
        help="Directory containing .md knowledge files",
    )
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap",    type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Number of chunks to embed per API call")
    args = parser.parse_args()

    asyncio.run(main(
        Path(args.knowledge_dir),
        args.chunk_size,
        args.overlap,
        args.batch_size,
    ))
