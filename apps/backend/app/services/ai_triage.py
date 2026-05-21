import structlog
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Incident, TriageReport
from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.agents.verifier import VerifierAgent, DeterministicVerifier
from app.agents.tools import ToolRegistry
from app.repositories.logs import LogRepository
from app.services.chunker import SlidingWindowChunker
from app.core.metrics import triage_runs_total, triage_retries_total
from app.schemas.triage import TriageReportSchema

from app.core.telemetry import get_tracer

logger = structlog.get_logger(__name__)
tracer = get_tracer(__name__)

class AITriageService:
    engine_version = "logiq-ai-triage-v1"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.log_repo = LogRepository(session)
        self.tool_registry = ToolRegistry(self.log_repo, session)
        self.chunker = SlidingWindowChunker()

    async def generate(self, incident: Incident) -> Tuple[TriageReport, bool]:
        with tracer.start_as_current_span("ai_triage_generate") as span:
            span.set_attribute("incident.id", incident.id)
            span.set_attribute("incident.title", incident.title)
            return await self._generate_internal(incident, span)

    async def _generate_internal(self, incident: Incident, parent_span) -> Tuple[TriageReport, bool]:
        triage_runs_total.labels(status="started").inc()
        
        # Fetch raw logs
        raw_logs = await self.log_repo.list_for_incident(incident.id, limit=2000)
        log_dicts = [
            {
                "id": l.id, 
                "message": l.message, 
                "level": str(l.level.value), 
                "source": l.source, 
                "timestamp": l.observed_at.isoformat()
            } 
            for l in raw_logs
        ]
        
        # Chunk logs
        chunks = self.chunker.chunk_logs(log_dicts)
        
        incident_data = {
            "id": incident.id,
            "title": incident.title,
            "description": incident.description,
            "chunks_available": len(chunks)
        }
        
        parent_span.set_attribute("chunk.count", len(chunks))

        retry_reason = None
        for attempt in range(3):
            with tracer.start_as_current_span(f"triage_attempt_{attempt}") as attempt_span:
                attempt_span.set_attribute("attempt", attempt)
                try:
                    # 1. Plan
                    with tracer.start_as_current_span("phase_plan") as plan_span:
                        plan = await PlannerAgent.plan(incident_data, retry_reason)
                        plan_span.set_attribute("plan.tasks_count", len(plan))
                    
                    # 2. Execute
                    with tracer.start_as_current_span("phase_execute"):
                        results = await ExecutorAgent.execute_plan(plan, self.session, self.tool_registry, incident.id)
                
                # Extract report payload for verifier
                report_task = next((t for t in plan if t.tool == "report_emit"), None)
                if not report_task or not results[report_task.task_id].success:
                    retry_reason = "Report emit tool failed or was not planned."
                    continue

                emitted_payload = results[report_task.task_id].output.get("payload")
                if not emitted_payload:
                    retry_reason = "Report payload missing."
                    continue

                report_schema = TriageReportSchema(**emitted_payload)

                # 3. Verify
                with tracer.start_as_current_span("phase_verify") as verify_span:
                    verdict = await VerifierAgent.verify(results, incident.id)
                    verify_span.set_attribute("verdict.approved", verdict.approved)
                
                if verdict.approved:
                    # Deterministic check
                    original_chunks_map = {c["chunk_index"]: c["logs"] for c in chunks}
                    det_verifier = DeterministicVerifier(original_chunks_map)
                    
                    with tracer.start_as_current_span("phase_deterministic_verify") as det_span:
                        is_valid, det_msg = det_verifier.verify_attributions(report_schema)
                        det_span.set_attribute("deterministic.valid", is_valid)
                        
                    if not is_valid:
                        retry_reason = det_msg
                        triage_retries_total.inc()
                        attempt_span.set_attribute("error", "deterministic_verify_failed")
                        continue
                    
                    triage_runs_total.labels(status="success").inc()
                    
                    stmt = select(TriageReport).where(TriageReport.incident_id == incident.id).order_by(TriageReport.created_at.desc()).limit(1)
                    report = (await self.session.execute(stmt)).scalar_one_or_none()
                    
                    # Update incident fields
                    if report:
                        incident.summary = report.summary
                        incident.root_cause = report.root_cause
                        await self.session.flush()
                        
                    return report, (attempt > 0)
                else:
                    retry_reason = verdict.retry_reason
                    triage_retries_total.inc()
                    attempt_span.set_attribute("error", "llm_verify_failed")
            except Exception as e:
                logger.error("triage_attempt_failed", error=str(e), attempt=attempt)
                retry_reason = f"Exception occurred: {str(e)}"
                triage_retries_total.inc()
                attempt_span.record_exception(e)
                attempt_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                
        triage_runs_total.labels(status="failed").inc()
        parent_span.set_status(trace.Status(trace.StatusCode.ERROR, "Triage failed after max retries"))
        raise Exception("Triage failed after max retries")
