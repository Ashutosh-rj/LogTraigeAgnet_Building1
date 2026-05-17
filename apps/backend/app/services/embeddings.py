from __future__ import annotations

import hashlib
import math
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Embedding
from app.schemas.search import SearchResult

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./:-]+")


class EmbeddingService:
    """
    Hash-projection embedding (SimHash variant). Fast and dependency-free,
    but produces vectors with NO semantic similarity — 'timeout' and 'slow query'
    will NOT be considered related. Replace embed_text() with a real sentence
    encoder (e.g. sentence-transformers all-MiniLM-L6-v2 or Anthropic embeddings)
    before using search in production.
    """

    model_version = "logiq-hash-embedding-v1"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.dimensions = get_settings().embedding_dimensions

    def embed_text(self, text: str) -> list[float]:
        # Each token hashes to one of self.dimensions slots.
        # Collisions (multiple tokens → same slot) are summed, not resolved.
        # At 384 dimensions, texts longer than ~50 unique tokens will experience
        # significant collision-driven accuracy loss.
        vector = [0.0] * self.dimensions
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign * (1.0 + math.log1p(len(token)))
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]

    def collision_rate(self, text: str) -> float:
        """Return the fraction of dimension slots hit more than once.

        Useful for operators to measure accuracy degradation on real payloads:
        a rate above 0.1 (10 % of slots collided) signals meaningful quality loss.
        """
        counts: dict[int, int] = {}
        tokens = TOKEN_PATTERN.findall(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            counts[idx] = counts.get(idx, 0) + 1
        if not counts:
            return 0.0
        collided = sum(1 for c in counts.values() if c > 1)
        # Denominator is the number of unique slots hit, not total dimensions.
        # Using self.dimensions would vastly understate the collision rate for
        # short texts (e.g. 5 collisions in 10 touched slots = 50%, not 5/384).
        unique_slots_hit = len(counts)
        return round(collided / unique_slots_hit, 6) if unique_slots_hit else 0.0

    async def embed_text_real(self, text: str) -> list[float]:
        """Semantic embedding backend — falls back to hash projection when not configured.

        To enable real semantic search, set EMBEDDING_PROVIDER to ``openai`` or
        ``local`` and implement the provider logic here.  Until then this method
        delegates to :meth:`embed_text` so callers never receive a hard crash.

        .. warning::
            The hash-projection fallback produces vectors with **no semantic
            similarity** — 'timeout' and 'slow query' will not be considered
            related.  Do not use in production search without replacing this.
        """
        import structlog as _structlog  # noqa: PLC0415
        _structlog.get_logger().warning(
            "embed_text_real_fallback",
            provider=get_settings().embedding_provider,
            reason="No semantic provider configured; falling back to hash projection.",
        )
        return self.embed_text(text)

    async def upsert(self, owner_type: str, owner_id: str, content: str) -> Embedding:
        vector = self.embed_text(content)
        result = await self.session.execute(
            select(Embedding).where(Embedding.owner_type == owner_type, Embedding.owner_id == owner_id)
        )
        embedding = result.scalar_one_or_none()
        if embedding:
            embedding.vector = vector
            embedding.content = content
        else:
            embedding = Embedding(
                owner_type=owner_type,
                owner_id=owner_id,
                vector=vector,
                content=content,
            )
            self.session.add(embedding)
        await self.session.flush()
        return embedding

    async def search(self, query: str, owner_types: list[str], limit: int) -> list[SearchResult]:
        vector = self.embed_text(query)
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
                # Clamp distance to [0, inf) before applying the score formula.
                # pgvector cosine distance is defined on [0, 2], but floating-point
                # rounding or a future driver bug could yield a negative value,
                # making the denominator zero or negative and producing inf/NaN.
                score=round(1.0 / (1.0 + max(float(distance_value or 0.0), 0.0)), 6),
            )
            for embedding, distance_value in rows
        ]
