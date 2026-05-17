from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ViewerUser
from app.db.session import get_session
from app.schemas.search import SearchRequest, SearchResponse
from app.services.embeddings import EmbeddingService

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def semantic_search(
    payload: SearchRequest,
    user: ViewerUser,
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    _ = user
    results = await EmbeddingService(session).search(payload.query, payload.owner_types, payload.limit)
    return SearchResponse(results=results)

