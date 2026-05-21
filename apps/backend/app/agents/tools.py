import structlog
import time
import asyncio
from typing import Literal, Any
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.core.metrics import tool_calls_total, tool_latency_seconds
from app.agents.base import AgentResult
from app.db.models import Incident, User, TriageReport, LogEntry
from app.services.events import event_publisher

logger = structlog.get_logger(__name__)

from app.schemas.triage import RootCause

class LogSearchInput(BaseModel):
    incident_id: str
    level_filter: list[str] = Field(default_factory=list)
    limit: int = 200

class DbLookupInput(BaseModel):
    table: Literal["incidents", "users"]
    id: str

class ReportEmitInput(BaseModel):
    incident_id: str
    summary: str
    root_causes: list[RootCause]
    recommendations: list[str]
    confidence: float

class ToolRegistry:
    def __init__(self, log_repo, db_session=None):
        self.log_repo = log_repo
        self.db_session = db_session # Not really used since session is passed

        self.schemas = {
            "log_search": LogSearchInput,
            "db_lookup": DbLookupInput,
            "report_emit": ReportEmitInput,
        }

    async def call(self, tool_name: str, raw_args: dict[str, Any], session) -> AgentResult:
        start_time = time.time()
        status = "success"
        output = {}
        error = None

        try:
            if tool_name not in self.schemas:
                raise ValueError(f"Unknown tool: {tool_name}")

            # Validate Inputs
            try:
                validated_args = self.schemas[tool_name](**raw_args)
            except ValidationError as e:
                logger.warning("tool_misuse", tool_name=tool_name, error=str(e), args=raw_args)
                raise e

            # Execute Logic with Timeout
            async def execute_tool():
                if tool_name == "log_search":
                    # Use actual log repository method
                    query = select(LogEntry).where(LogEntry.incident_id == validated_args.incident_id)
                    if validated_args.level_filter:
                        query = query.where(LogEntry.level.in_(validated_args.level_filter))
                    query = query.order_by(LogEntry.observed_at.desc()).limit(validated_args.limit)
                    result = await session.execute(query)
                    logs = result.scalars().all()
                    
                    return {
                        "entries": [{
                            "id": log.id,
                            "level": log.level,
                            "message": log.message,
                            "source": log.source,
                            "observed_at": log.observed_at.isoformat()
                        } for log in logs],
                        "total_found": len(logs)
                    }

                elif tool_name == "db_lookup":
                    if validated_args.table == "incidents":
                        record = await session.get(Incident, validated_args.id)
                    else:
                        record = await session.get(User, validated_args.id)
                    
                    if record:
                        # Extract dict representation safely
                        record_dict = {c.name: str(getattr(record, c.name)) for c in record.__table__.columns}
                        return {"record": record_dict, "found": True}
                    return {"found": False}

                elif tool_name == "report_emit":
                    # Update or insert TriageReport
                    query = select(TriageReport).where(TriageReport.incident_id == validated_args.incident_id)
                    result = await session.execute(query)
                    existing_report = result.scalar_one_or_none()
                    
                    if existing_report:
                        existing_report.summary = validated_args.summary
                        existing_report.root_cause = str([r.dict() for r in validated_args.root_causes])
                        existing_report.recommendations = validated_args.recommendations
                        existing_report.confidence = validated_args.confidence
                        existing_report.model_version = "claude-pipeline"
                        report_id = existing_report.id
                    else:
                        new_report = TriageReport(
                            incident_id=validated_args.incident_id,
                            summary=validated_args.summary,
                            root_cause=str([r.dict() for r in validated_args.root_causes]),
                            recommendations=validated_args.recommendations,
                            confidence=validated_args.confidence,
                            model_version="claude-pipeline"
                        )
                        session.add(new_report)
                        await session.flush()
                        report_id = new_report.id

                    # Publish Kafka event
                    await event_publisher.publish(
                        "triage.report.emitted",
                        {"incident_id": validated_args.incident_id, "report_id": report_id}
                    )

                    return {
                        "emitted": True,
                        "report_id": report_id
                    }

            # Add timeout handling
            from app.core.config import settings
            output = await asyncio.wait_for(execute_tool(), timeout=settings.tool_timeout_seconds)

        except asyncio.TimeoutError:
            status = "timeout"
            error = f"Tool execution timed out after {settings.tool_timeout_seconds} seconds"
        except Exception as e:
            status = "error"
            error = str(e)
        finally:
            latency = time.time() - start_time
            tool_calls_total.labels(tool_name=tool_name, status=status).inc()
            tool_latency_seconds.labels(tool_name=tool_name).observe(latency)

        return AgentResult(
            success=(status == "success"),
            output=output,
            confidence=1.0,
            tokens_used=0, # Tools themselves don't consume LLM tokens
            error=error
        )