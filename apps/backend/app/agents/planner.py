import json
import structlog
from opentelemetry import trace
from pydantic import BaseModel
from typing import Optional
from app.agents.base import AnthropicClient
from app.core.config import settings
from app.core.metrics import triage_tokens_total
from app.core.telemetry import get_tracer

logger = structlog.get_logger(__name__)
tracer = get_tracer(__name__)

SYSTEM_PROMPT = """You are a log triage Planner. Given an incident, decompose it into a JSON list of sub-tasks.
Each sub-task must have:
  - task_id: str (unique, e.g. "T1")
  - tool: one of ["log_search", "db_lookup", "report_emit"]
  - args: dict matching that tool's input schema exactly
  - depends_on: list[str] (task_ids that must complete first)
  - chunk_index: int (0-based, for multi-chunk log processing)
  - chunk_boundary_metadata: { start_offset: int, end_offset: int } | null
Rules:
  1. Always end with exactly one report_emit task depending on all log_search results.
  2. For incidents with >500 log entries, split into multiple log_search tasks with limit=200 and sequential chunk_index values. Set chunk_boundary_metadata for each.
  3. Output ONLY valid JSON. No prose, no markdown fences."""

class ChunkBoundary(BaseModel):
    start_offset: int
    end_offset: int

class SubTask(BaseModel):
    task_id: str
    tool: str
    args: dict
    depends_on: list[str]
    chunk_index: int
    chunk_boundary_metadata: Optional[ChunkBoundary] = None

class PlannerAgent:
    @staticmethod
    async def plan(incident: dict, retry_reason: str = None) -> list[SubTask]:
        client = AnthropicClient.get_client()

        prompt = f"Plan incident {incident['id']}. Details: {json.dumps(incident)}"
        if retry_reason:
            prompt += f"\n\nCONSTRAINT (Previous attempt failed): {retry_reason}"

        with tracer.start_as_current_span("planner.plan") as span:
            span.set_attribute("incident.id", incident.get("id", ""))
            span.set_attribute("llm.model", settings.planner_model)
            span.set_attribute("planner.retry", retry_reason or "")

            response = await client.messages.create(
                model=settings.planner_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            usage = response.usage.input_tokens + response.usage.output_tokens
            triage_tokens_total.labels(agent="planner").inc(usage)
            span.set_attribute("llm.tokens_used", usage)
            span.set_attribute("llm.input_tokens", response.usage.input_tokens)
            span.set_attribute("llm.output_tokens", response.usage.output_tokens)

            try:
                raw_tasks = json.loads(response.content[0].text)
                tasks = [SubTask(**task) for task in raw_tasks]
                span.set_attribute("planner.tasks_count", len(tasks))
                return tasks
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("planner_parse_error", incident_id=incident.get("id"), error=str(e))
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e