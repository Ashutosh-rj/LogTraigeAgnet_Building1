from __future__ import annotations

from app.services.embeddings import EmbeddingService


def test_embedding_is_deterministic_and_normalized() -> None:
    service = EmbeddingService(session=None)  # type: ignore[arg-type]

    first = service.embed_text("database timeout checkout")
    second = service.embed_text("database timeout checkout")

    assert first == second
    assert len(first) == 384
    assert 0.99 <= sum(value * value for value in first) <= 1.01


def test_empty_embedding_has_expected_dimension() -> None:
    service = EmbeddingService(session=None)  # type: ignore[arg-type]

    assert service.embed_text("") == [0.0] * 384

