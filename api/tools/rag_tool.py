"""
barca_knowledge tool — RAG pipeline via pgvector cosine similarity search.

Embeds the user's query with text-embedding-3-small, then retrieves the
top-K most relevant knowledge chunks from the knowledge_chunks table.
"""
import json
from openai import AsyncOpenAI
from agents import function_tool
from api.db.connection import get_pool
from api.config import settings

_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _openai_client


@function_tool
async def barca_knowledge(query: str) -> str:
    """
    Semantic search over the FC Barcelona knowledge base.
    Use this tool for qualitative, narrative, or historical questions such as:
    - Club history, founding, trophies, and milestones
    - La Masia academy philosophy, notable graduates
    - Legendary player biographies (Messi, Cruyff, Xavi, Iniesta, Ronaldinho...)
    - Coaching philosophies (Tiki-taka, Cruyffian principles, positional play)
    - Camp Nou, stadium culture, supporter traditions
    - Rivalry with Real Madrid (El Clásico history)
    - Club motto: Més que un club

    This tool retrieves relevant passages from curated documents.
    Always use this for open-ended, knowledge-based questions about the club.
    """
    client = _get_client()

    # Embed the query
    resp = await client.embeddings.create(
        model=settings.embedding_model,
        input=query.strip(),
    )
    embedding = resp.data[0].embedding

    # pgvector similarity search
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                source_file,
                chunk_index,
                content,
                1 - (embedding <=> $1::vector) AS similarity
            FROM knowledge_chunks
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(embedding),
            settings.rag_top_k,
        )

    if not rows:
        return "No relevant knowledge found in the knowledge base."

    # Format retrieved chunks for the agent
    chunks: list[str] = []
    for row in rows:
        source = row["source_file"] or "unknown"
        chunks.append(
            f"[Source: {source} | chunk {row['chunk_index']} | "
            f"similarity: {row['similarity']:.3f}]\n{row['content']}"
        )

    return "\n\n" + ("─" * 60) + "\n\n".join(chunks)
