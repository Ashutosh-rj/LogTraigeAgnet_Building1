import os
import json
import uuid
import random
from datetime import datetime, timedelta

def generate():
    fixtures_dir = "d:/LogTraigeAgent/Upadate_18May/LogTraigeAgnet_Building1-main/LogTraigeAgnet_Building1-main/apps/backend/tests/fixtures"
    os.makedirs(fixtures_dir, exist_ok=True)
    
    categories = ["oom_killed", "database_timeout", "network_partition"]
    
    for idx in range(1, 21):
        category = random.choice(categories)
        cat_dir = os.path.join(fixtures_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        
        incident_id = str(uuid.uuid4())
        
        # logs
        logs = []
        base_time = datetime.utcnow() - timedelta(minutes=10)
        
        # background noise
        for i in range(10):
            logs.append({
                "id": str(uuid.uuid4()),
                "incident_id": incident_id,
                "level": "info",
                "message": f"Normal traffic at endpoint /healthz",
                "source": "api-gateway",
                "observed_at": (base_time + timedelta(seconds=i*5)).isoformat()
            })
            
        # The critical log
        if category == "oom_killed":
            log_line = f"FATAL: Out of memory (OOMKilled) in container {random.randint(100, 999)}"
            svc = "payment-worker"
        elif category == "database_timeout":
            log_line = f"Error querying table users: context deadline exceeded (timeout=5000ms)"
            svc = "user-service"
        else:
            log_line = f"Network connection lost to redis: EOF"
            svc = "cache-node"
            
        logs.append({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "level": "error",
            "message": log_line,
            "source": svc,
            "observed_at": (base_time + timedelta(seconds=60)).isoformat()
        })
        
        # Expected truth
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
        
        with open(os.path.join(cat_dir, f"incident_{idx:03d}.json"), "w") as f:
            json.dump({"incident_id": incident_id, "logs": logs, "expected": truth}, f, indent=2)

if __name__ == "__main__":
    generate()
