from __future__ import annotations

import hashlib
import math
import re
import asyncio
import time
from typing import Final, List

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.metrics import embedding_latency_seconds
from app.db.models import Embedding
from app.schemas.search import SearchResult

logger = structlog.get_logger(__name__)

TOKEN_PATTERN: Final = re.compile(r"[a-zA-Z0-9_./:-]+")

# Cache for local sentence transformer model to avoid reloading
_local_st_model = None

def _get_sentence_transformer(model_name: str):
    global _local_st_model
    if _local_st_model is None:
        from sentence_transformers import SentenceTransformer
        _local_st_model = SentenceTransformer(model_name)
    return _local_st_model


class EmbeddingService:
    """
    Enterprise-grade embedding service.

    Supports:
    - OpenAI embeddings
    - VoyageAI embeddings
    - SentenceTransformers (local fallback)
    - Hash fallback embeddings (for dev only)
    - pgvector semantic search
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        settings = get_settings()

        self.provider = settings.embedding_provider.lower()
        self.dimensions = settings.embedding_dimensions
        self.embedding_model = settings.embedding_model
        self.timeout_seconds = settings.llm_timeout_seconds

        self.openai_api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        self.voyageai_api_key = settings.voyageai_api_key.get_secret_value() if settings.voyageai_api_key else None
        self.sentence_transformer_model = settings.sentence_transformer_model

        self.model_version = f"logiq-{self.provider}-embedding-v1"

    # =========================================================
    # HASH EMBEDDING (DEV FALLBACK)
    # =========================================================
    def embed_text_hash(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += (1.0 + math.log1p(len(token))) * sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [round(v / norm, 8) for v in vector]

    # =========================================================
    # SENTENCE TRANSFORMERS
    # =========================================================
    async def embed_sentence_transformers(self, texts: list[str]) -> list[list[float]]:
        start_time = time.time()
        try:
            def _embed():
                model = _get_sentence_transformer(self.sentence_transformer_model)
                embeddings = model.encode(texts, convert_to_numpy=True)
                return embeddings.tolist()
            
            result = await asyncio.to_thread(_embed)
            return result
        finally:
            embedding_latency_seconds.labels(provider="sentence_transformers").observe(time.time() - start_time)

    # =========================================================
    # VOYAGE AI
    # =========================================================
    async def embed_voyageai(self, texts: list[str]) -> list[list[float]]:
        start_time = time.time()
        try:
            headers = {
                "Authorization": f"Bearer {self.voyageai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "voyage-3",
                "input": texts,
            }
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post("https://api.voyageai.com/v1/embeddings", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
        finally:
            embedding_latency_seconds.labels(provider="voyageai").observe(time.time() - start_time)

    # =========================================================
    # OPENAI EMBEDDINGS
    # =========================================================
    async def embed_openai(self, texts: list[str]) -> list[list[float]]:
        start_time = time.time()
        try:
            if not self.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY not configured")

            safe_texts = [self._truncate_text(t) for t in texts]
            headers = {"Authorization": f"Bearer {self.openai_api_key}"}
            payload = {"model": "text-embedding-3-small", "input": safe_texts}

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post("https://api.openai.com/v1/embeddings", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                # Ensure ordered results
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_data]
        finally:
            embedding_latency_seconds.labels(provider="openai").observe(time.time() - start_time)

    # =========================================================
    # MAIN EMBEDDING ENTRYPOINT
    # =========================================================
    async def embed_texts_real(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
            
        try:
            if self.provider == "openai":
                return await self.embed_openai(texts)
            elif self.provider == "voyageai":
                return await self.embed_voyageai(texts)
            elif self.provider == "sentence_transformers":
                return await self.embed_sentence_transformers(texts)

            logger.warning("semantic_embedding_fallback", provider=self.provider, reason="Using hash embeddings.")
            return [self.embed_text_hash(t) for t in texts]

        except Exception as exc:
            logger.exception("embedding_generation_failed", provider=self.provider, error=str(exc))
            logger.warning("falling_back_to_hash_embedding")
            return [self.embed_text_hash(t) for t in texts]

    # =========================================================
    # UPSERT
    # =========================================================
    async def upsert(self, owner_type: str, owner_id: str, content: str) -> Embedding:
        vectors = await self.embed_texts_real([content])
        vector = vectors[0]

        result = await self.session.execute(
            select(Embedding).where(Embedding.owner_type == owner_type, Embedding.owner_id == owner_id)
        )
        embedding = result.scalar_one_or_none()

        if embedding:
            embedding.vector = vector
            embedding.content = content
        else:
            embedding = Embedding(owner_type=owner_type, owner_id=owner_id, vector=vector, content=content)
            self.session.add(embedding)

        await self.session.flush()
        return embedding

    async def batch_upsert(self, items: list[dict]) -> None:
        """
        items: list of dicts with 'owner_type', 'owner_id', 'content'
        """
        if not items:
            return
            
        contents = [item["content"] for item in items]
        vectors = await self.embed_texts_real(contents)

        for item, vector in zip(items, vectors):
            result = await self.session.execute(
                select(Embedding).where(
                    Embedding.owner_type == item["owner_type"], 
                    Embedding.owner_id == item["owner_id"]
                )
            )
            embedding = result.scalar_one_or_none()
            if embedding:
                embedding.vector = vector
                embedding.content = item["content"]
            else:
                embedding = Embedding(
                    owner_type=item["owner_type"], 
                    owner_id=item["owner_id"], 
                    vector=vector, 
                    content=item["content"]
                )
                self.session.add(embedding)

        await self.session.flush()

    # =========================================================
    # SEARCH
    # =========================================================
    async def search(self, query: str, owner_types: list[str], limit: int) -> list[SearchResult]:
        vectors = await self.embed_texts_real([query])
        vector = vectors[0]

        distance = Embedding.vector.cosine_distance(vector).label("distance")

        result = await self.session.execute(
            select(Embedding, distance)
            .where(Embedding.owner_type.in_(owner_types))
            .order_by(distance.asc())
            .limit(limit)
        )
        rows = result.all()

        return [
            SearchResult(
                owner_type=embedding.owner_type,
                owner_id=embedding.owner_id,
                content=embedding.content,
                score=round(1.0 / (1.0 + max(float(distance_value or 0.0), 0.0)), 6),
            )
            for embedding, distance_value in rows
        ]

    # =========================================================
    # UTILITIES
    # =========================================================
    def _truncate_text(self, text: str) -> str:
        max_chars = 8192 * 4
        return text[:max_chars]
