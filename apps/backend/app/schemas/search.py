from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    owner_types: list[str] = Field(default_factory=lambda: ["incident", "log", "triage"])
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    owner_type: str
    owner_id: str
    content: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]

