from __future__ import annotations

import json
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EventPublisher:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        settings = get_settings()
        if not settings.kafka_enabled:
            logger.info("kafka_disabled")
            return
        try:
            self._producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
            await self._producer.start()
            logger.info("kafka_started", bootstrap_servers=settings.kafka_bootstrap_servers)
        except Exception as exc:
            self._producer = None
            if settings.is_production:
                raise
            logger.warning("kafka_unavailable", error=str(exc))

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self._producer is None:
            logger.info("event_not_published_without_kafka", topic=topic, event_name=payload.get("event"))
            return
        try:
            await self._producer.send_and_wait(
                topic,
                json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8"),
                key=str(payload.get("resource_id", "")).encode("utf-8"),
            )
        except Exception as exc:
            # A mid-run Kafka failure (broker disconnect, topic error, timeout)
            # must NOT propagate to the caller.  By this point the DB write has
            # already been committed; aborting the HTTP response would leave the
            # client with a misleading error while the data is actually persisted.
            # We log the failure for observability and degrade gracefully.
            # In production, alerting on kafka_publish_error is recommended.
            settings = get_settings()
            if settings.is_production:
                logger.error(
                    "kafka_publish_error",
                    topic=topic,
                    event_name=payload.get("event"),
                    error=str(exc),
                )
            else:
                logger.warning(
                    "kafka_publish_error",
                    topic=topic,
                    event_name=payload.get("event"),
                    error=str(exc),
                )


event_publisher = EventPublisher()

