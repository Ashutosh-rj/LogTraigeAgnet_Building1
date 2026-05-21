import asyncio
import structlog
from opentelemetry import trace
from app.agents.planner import SubTask
from app.agents.tools import ToolRegistry
from app.agents.base import AgentResult
from app.core.config import settings
from app.core.telemetry import get_tracer

logger = structlog.get_logger(__name__)
tracer = get_tracer(__name__)

class ExecutorAgent:
    @staticmethod
    async def execute_plan(tasks: list[SubTask], session, registry: ToolRegistry, incident_id: str) -> dict[str, AgentResult]:
        """Topological execution of tool calls via asyncio graph dependencies."""
        events = {t.task_id: asyncio.Event() for t in tasks}
        results: dict[str, AgentResult] = {}

        async def run_task(task: SubTask):
            with tracer.start_as_current_span(f"executor.tool.{task.tool}") as span:
                span.set_attribute("incident.id", incident_id)
                span.set_attribute("task.id", task.task_id)
                span.set_attribute("task.tool", task.tool)
                span.set_attribute("task.chunk_index", task.chunk_index)
                span.set_attribute("task.depends_on", str(task.depends_on))

                # Wait for dependencies
                for dep in task.depends_on:
                    await events[dep].wait()
                    if not results[dep].success:
                        results[task.task_id] = AgentResult(
                            success=False, output={}, confidence=0, tokens_used=0,
                            error=f"Dependency {dep} failed"
                        )
                        span.set_attribute("task.skipped_due_to_dep", dep)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, f"Dependency {dep} failed"))
                        events[task.task_id].set()
                        return

                # Execute tool with retries + exponential backoff
                res = AgentResult(success=False, output={}, confidence=0, tokens_used=0, error="No attempts made")
                for attempt in range(settings.max_tool_retries):
                    res = await registry.call(task.tool, task.args, session)
                    if res.success:
                        break
                    await asyncio.sleep(0.5 * (2 ** attempt))

                # Record chunk boundary metadata if it's a log search
                if task.tool == "log_search" and task.chunk_boundary_metadata:
                    res.output["chunk_metadata"] = task.chunk_boundary_metadata.dict()

                span.set_attribute("task.success", res.success)
                span.set_attribute("task.confidence", res.confidence)
                if not res.success:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, res.error or "Tool failed"))

                logger.info(
                    "tool_executed",
                    incident_id=incident_id,
                    task_id=task.task_id,
                    tool=task.tool,
                    success=res.success,
                )
                results[task.task_id] = res
                events[task.task_id].set()

        await asyncio.gather(*(run_task(t) for t in tasks))
        return results