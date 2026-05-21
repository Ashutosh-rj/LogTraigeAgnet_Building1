from dataclasses import dataclass, field
from typing import Any
from anthropic import AsyncAnthropic
from app.core.config import settings

@dataclass
class AgentResult:
    success: bool
    output: dict[str, Any]
    confidence: float
    tokens_used: int
    error: str | None = None
    retry_count: int = 0

# AnthropicClient Singleton for token tracking & unified connection pooling
class AnthropicClient:
    _instance = None

    @classmethod
    def get_client(cls) -> AsyncAnthropic:
        if cls._instance is None:
            cls._instance = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return cls._instance