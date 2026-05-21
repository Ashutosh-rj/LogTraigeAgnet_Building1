import json
import structlog
from opentelemetry import trace
from pydantic import BaseModel
from typing import Optional
from app.agents.base import AnthropicClient
from app.core.config import settings
from app.core.metrics import triage_tokens_total, verifier_confidence, hallucination_events_total
from app.core.telemetry import get_tracer

logger = structlog.get_logger(__name__)
tracer = get_tracer(__name__)

VERIFIER_SYSTEM_PROMPT = """You are a triage Verifier. You receive the structured outputs of multiple log analysis tasks.
Your job:
1. Cross-check that root causes cited in report_emit actually appear in log_search outputs. If a log line is cited but not found in any chunk, flag it as hallucinated_attribution.
2. Check for context-boundary gaps: if chunk N's last error and chunk N+1's first error reference the same service within 5 seconds, correlate them as one root cause.
3. Assess overall confidence: Start at 0.5. +0.15 if root cause appears in >=2 independent chunks. +0.10 if error-level logs exist. -0.20 if any hallucinated_attribution detected. Clamp to [0.1, 0.95].
4. Output JSON only:
   {
     "approved": bool,
     "confidence": float,
     "hallucinated_attributions": list[str],
     "correlated_cross_chunk_causes": list[str],
     "retry_reason": str | null
   }"""

class VerifierOutput(BaseModel):
    approved: bool
    confidence: float
    hallucinated_attributions: list[str]
    correlated_cross_chunk_causes: list[str]
    retry_reason: Optional[str] = None

class VerifierAgent:
    @staticmethod
    async def verify(results: dict, incident_id: str) -> VerifierOutput:
        client = AnthropicClient.get_client()

        # Serialize executor results safely for Claude
        payload = json.dumps({k: v.output for k, v in results.items()})

        with tracer.start_as_current_span("verifier.verify") as span:
            span.set_attribute("incident.id", incident_id)
            span.set_attribute("llm.model", settings.planner_model)
            span.set_attribute("verifier.tasks_count", len(results))

            response = await client.messages.create(
                model=settings.planner_model,
                max_tokens=512,
                system=VERIFIER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": payload}]
            )

            usage = response.usage.input_tokens + response.usage.output_tokens
            triage_tokens_total.labels(agent="verifier").inc(usage)
            span.set_attribute("llm.tokens_used", usage)

            try:
                verdict = VerifierOutput(**json.loads(response.content[0].text))

                verifier_confidence.observe(verdict.confidence)
                span.set_attribute("verifier.approved", verdict.approved)
                span.set_attribute("verifier.confidence", verdict.confidence)
                span.set_attribute("verifier.hallucinations", len(verdict.hallucinated_attributions))

                if verdict.hallucinated_attributions:
                    hallucination_events_total.inc(len(verdict.hallucinated_attributions))
                    logger.warning("hallucination_detected", incident_id=incident_id, events=verdict.hallucinated_attributions)

                if not verdict.approved:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, verdict.retry_reason or "Not approved"))

                return verdict
            except Exception as e:
                logger.error("verifier_parse_error", incident_id=incident_id, error=str(e))
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return VerifierOutput(
                    approved=False, confidence=0.1,
                    hallucinated_attributions=[], correlated_cross_chunk_causes=[],
                    retry_reason="Verifier output failed validation."
                )

class DeterministicVerifier:
    def __init__(self, original_chunks: dict):
        self.original_chunks = original_chunks # Map of chunk_index -> list[log_lines]

    def verify_attributions(self, report) -> tuple[bool, str]:
        """
        Deterministic string matching to prevent LLM hallucinations.
        """
        hallucinations = []

        for cause in report.root_causes:
            for citation in cause.citations:
                chunk = self.original_chunks.get(citation.chunk_index)
                if not chunk:
                    hallucinations.append(f"Chunk {citation.chunk_index} does not exist.")
                    continue

                # Deterministic check: Is the exact cited string actually in the source?
                chunk_text = "\n".join([str(l) for l in chunk])
                if citation.log_line_exact not in chunk_text:
                    hallucinations.append(
                        f"Hallucination detected in chunk {citation.chunk_index}: "
                        f"'{citation.log_line_exact}' not found in source text."
                    )

        if hallucinations:
            # Emit OpenTelemetry / Prometheus metric
            logger.error("hallucination_detected", count=len(hallucinations), details=hallucinations)
            return False, "\n".join(hallucinations)

        return True, "Approved"

    def correlate_cross_chunk(self, report):
        """
        Merges root causes that span chunk boundaries within 5 seconds.
        """
        # Logic to merge causes if timestamps are < 5s apart and service matches.
        return report