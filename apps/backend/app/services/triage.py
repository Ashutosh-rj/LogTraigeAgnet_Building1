from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Incident, LogEntry, LogLevel, Severity, TriageReport
from app.repositories.logs import LogRepository, LOG_TRIAGE_LIMIT


class TriageService:
    """
    Rule-based triage engine. Analyses log patterns, severity, and keywords
    to generate structured incident summaries. This is NOT an ML model.
    Replace embed calls with a real LLM (e.g. Anthropic claude-sonnet-4-20250514)
    for semantic analysis.
    """

    engine_version = "logiq-heuristic-triage-v1"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logs = LogRepository(session)

    async def generate(self, incident: Incident) -> tuple[TriageReport, bool]:
        """Generate (or regenerate) a triage report for *incident*.

        Returns a ``(report, was_regenerated)`` tuple.  If a report already
        exists it is updated in place so that there is always at most one row
        per incident in ``triage_reports``.
        """
        logs = await self.logs.list_for_incident(incident.id, limit=LOG_TRIAGE_LIMIT)
        summary = self._summarize(incident, logs)
        root_cause = self._root_cause(incident, logs)
        recommendations = self._recommendations(incident, logs)
        confidence = self._confidence(incident, logs)

        result = await self.session.execute(
            select(TriageReport)
            .where(TriageReport.incident_id == incident.id)
            .order_by(TriageReport.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.summary = summary
            existing.root_cause = root_cause
            existing.recommendations = recommendations
            existing.confidence = confidence
            existing.model_version = self.engine_version
            incident.summary = summary
            incident.root_cause = root_cause
            await self.session.flush()
            return existing, True

        report = TriageReport(
            incident_id=incident.id,
            summary=summary,
            root_cause=root_cause,
            recommendations=recommendations,
            confidence=confidence,
            model_version=self.engine_version,
        )
        incident.summary = summary
        incident.root_cause = root_cause
        self.session.add(report)
        await self.session.flush()
        return report, False

    def _summarize(self, incident: Incident, logs: list[LogEntry]) -> str:
        if not logs:
            return (
                f"{incident.severity.value.title()} incident '{incident.title}' was reported from "
                f"{incident.source} with no logs attached yet."
            )
        levels = Counter(log.level.value for log in logs)
        top_levels = ", ".join(f"{level}:{count}" for level, count in levels.most_common(3))
        # logs are ordered observed_at DESC (newest first), so logs[0] is the
        # most recent event — correctly labelled "Latest signal" below.
        newest = logs[0].message[:220]
        return (
            f"{incident.severity.value.title()} incident '{incident.title}' has {len(logs)} correlated "
            f"log events ({top_levels}). Latest signal: {newest}"
        )

    def _root_cause(self, incident: Incident, logs: list[LogEntry]) -> str:
        severe_logs = [log for log in logs if log.level in {LogLevel.error, LogLevel.critical}]
        if severe_logs:
            # logs are ordered observed_at DESC (newest first), so severe_logs
            # inherits the same order: severe_logs[0] is the newest high-severity
            # event and severe_logs[-1] is the oldest (chronologically earliest).
            # We use severe_logs[-1] because the first high-severity event is the
            # most likely root-cause signal.
            earliest = severe_logs[-1]
            return (
                f"The earliest high-severity signal came from {earliest.source}: "
                f"{earliest.message[:300]}"
            )
        return (
            "The incident currently lacks error-level telemetry; correlate infrastructure metrics, "
            "recent deployments, and upstream dependency health before declaring root cause."
        )

    def _recommendations(self, incident: Incident, logs: list[LogEntry]) -> list[str]:
        recommendations = [
            "Confirm customer impact and affected service boundaries.",
            "Attach deployment, dependency, and infrastructure context to the incident timeline.",
        ]
        if incident.severity in {Severity.critical, Severity.high}:
            recommendations.insert(0, "Escalate to the on-call responder and freeze risky deployments.")
        if any("timeout" in log.message.lower() for log in logs):
            recommendations.append("Inspect upstream latency, connection pools, and retry budgets.")
        if any("database" in log.message.lower() or "sql" in log.message.lower() for log in logs):
            recommendations.append("Review database saturation, slow queries, locks, and migration history.")
        return recommendations

    def _confidence(self, incident: Incident, logs: list[LogEntry]) -> float:
        base = 0.45
        severity_weight = {
            Severity.critical: 0.2,
            Severity.high: 0.15,
            Severity.medium: 0.1,
            Severity.low: 0.05,
        }[incident.severity]
        log_weight = min(len(logs) * 0.025, 0.25)
        error_weight = 0.1 if any(log.level in {LogLevel.error, LogLevel.critical} for log in logs) else 0
        return round(min(base + severity_weight + log_weight + error_weight, 0.95), 2)
