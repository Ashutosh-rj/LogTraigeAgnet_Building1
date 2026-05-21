import os
import json
import uuid
import pytest
from datetime import datetime, timedelta, UTC

from app.db.models import Incident, LogEntry, Severity
from app.services.ai_triage import AITriageService
from app.core.config import settings

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "../fixtures")

def generate_fixtures_if_missing():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    categories = ["oom_killed", "database_timeout", "network_partition"]
    
    count = 0
    for root, dirs, files in os.walk(FIXTURES_DIR):
        for file in files:
            if file.endswith(".json"):
                count += 1
                
    if count >= 20:
        return
        
    for i in range(20):
        category = categories[i % len(categories)]
        cat_dir = os.path.join(FIXTURES_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        
        incident_id = str(uuid.uuid4())
        base_time = datetime.now(UTC) - timedelta(minutes=10)
        logs = []
        
        # Add background logs
        for j in range(10):
            logs.append({
                "id": str(uuid.uuid4()),
                "level": "info",
                "message": f"Normal traffic at endpoint /healthz",
                "source": "api-gateway",
                "observed_at": (base_time + timedelta(seconds=j*5)).isoformat()
            })
            
        # Add critical log
        if category == "oom_killed":
            log_line = f"FATAL: Out of memory (OOMKilled) in container"
            svc = "payment-worker"
        elif category == "database_timeout":
            log_line = f"Error querying table users: context deadline exceeded"
            svc = "user-service"
        else:
            log_line = f"Network connection lost to redis"
            svc = "cache-node"
            
        logs.append({
            "id": str(uuid.uuid4()),
            "level": "error",
            "message": log_line,
            "source": svc,
            "observed_at": (base_time + timedelta(seconds=60)).isoformat()
        })
        
        truth = {
            "incident_id": incident_id,
            "root_causes": [
                {
                    "service": svc,
                    "failure_category": category,
                    "description": f"Service {svc} failed due to {category}",
                    "citations": [
                        {
                            "chunk_index": 0,
                            "log_line_exact": log_line,
                            "timestamp": logs[-1]["observed_at"]
                        }
                    ]
                }
            ]
        }
        
        with open(os.path.join(cat_dir, f"incident_{i+1:03d}.json"), "w") as f:
            json.dump({"incident_id": incident_id, "logs": logs, "expected": truth}, f, indent=2)

def load_fixtures():
    generate_fixtures_if_missing()
    fixtures = []
    for root, dirs, files in os.walk(FIXTURES_DIR):
        for file in files:
            if file.endswith(".json"):
                with open(os.path.join(root, file), "r") as f:
                    fixtures.append(json.load(f))
    return fixtures

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", load_fixtures())
async def test_ai_triage_pipeline(fixture, db_session):
    # This assumes db_session fixture is available in conftest.py
    # 1. Setup DB state
    incident = Incident(
        id=fixture["incident_id"],
        title="Eval Incident",
        description="Eval harness incident",
        severity=Severity.high,
        source="eval"
    )
    db_session.add(incident)
    
    for log_data in fixture["logs"]:
        log_entry = LogEntry(
            id=log_data["id"],
            incident_id=incident.id,
            level=log_data["level"],
            message=log_data["message"],
            source=log_data["source"],
            observed_at=datetime.fromisoformat(log_data["observed_at"])
        )
        db_session.add(log_entry)
        
    await db_session.flush()
    
    # 2. Execute Triage
    settings.triage_mode = "claude_pipeline"
    triage_service = AITriageService(db_session)
    
    report, _ = await triage_service.generate(incident)
    
    # 3. Verify Constraints
    assert report is not None
    assert report.incident_id == incident.id
    
    # Verify deterministic verifier worked
    assert report.root_cause
    root_causes_arr = json.loads(report.root_cause.replace("'", '"')) # Simple parse for eval
    assert len(root_causes_arr) > 0
    
    # Match against expected ground truth
    expected_category = fixture["expected"]["root_causes"][0]["failure_category"]
    actual_category = root_causes_arr[0]["failure_category"]
    assert actual_category == expected_category
