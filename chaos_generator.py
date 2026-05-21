import asyncio
import httpx
import random
import time

BASE_URL = "http://localhost:8080/api/v1"

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Register the first user (will become admin)
        print("Registering user...")
        resp = await client.post("/auth/register", json={
            "email": "demo@example.com",
            "name": "Demo Admin",
            "password": "SuperSecret123!"
        })
        
        # If already registered, login
        if resp.status_code != 201 and resp.status_code != 200:
            print("Already registered, logging in...")
            resp = await client.post("/auth/login", json={
                "email": "demo@example.com",
                "password": "SuperSecret123!"
            })
            if resp.status_code != 200:
                print("Failed to login:", resp.text)
                return
        
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        incidents = [
            {
                "title": "Payment Gateway Timeout (Stripe)",
                "description": "Checkout service is failing to connect to Stripe API. Users are unable to complete purchases.",
                "severity": "critical",
                "source": "pagerduty",
                "tags": ["payment", "stripe", "checkout"]
            },
            {
                "title": "Database Connection Pool Exhaustion",
                "description": "High latency and connection pool timeouts on the primary PostgreSQL cluster.",
                "severity": "high",
                "source": "datadog",
                "tags": ["database", "postgres", "latency"]
            },
            {
                "title": "Frontend Memory Leak in React Dashboard",
                "description": "Users report the dashboard tab crashing after 30 minutes of usage. OOM errors observed.",
                "severity": "medium",
                "source": "sentry",
                "tags": ["frontend", "memory", "react"]
            }
        ]

        log_templates = {
            "payment": [
                ('error', 'stripe.error.ApiConnectionError: Request to Stripe API timed out.'),
                ('error', 'Failed to charge customer cu_12345: Timeout'),
                ('warning', 'Retrying payment charge for cart_8891...'),
                ('info', 'Checkout session initialized for user u_551'),
            ],
            "database": [
                ('error', 'FATAL: remaining connection slots are reserved for non-replication superuser connections'),
                ('error', 'sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached, connection timed out'),
                ('warning', 'Slow query detected (1500ms): SELECT * FROM users WHERE last_login < ...'),
                ('info', 'Connection returned to pool.'),
            ],
            "frontend": [
                ('error', 'DOMException: Failed to execute \'removeChild\' on \'Node\': The node to be removed is no longer a child of this node.'),
                ('warning', 'Performance warning: 5000 DOM nodes created in 5 seconds.'),
                ('error', 'Uncaught Error: Out of memory'),
                ('info', 'Component Dashboard mounted.'),
            ]
        }

        for inc_data in incidents:
            print(f"Creating incident: {inc_data['title']}")
            resp = await client.post("/incidents", json=inc_data, headers=headers)
            if resp.status_code != 201:
                print("Failed to create incident:", resp.text)
                continue
            
            incident_id = resp.json()["id"]
            incident_type = inc_data["tags"][0]
            
            print(f"Streaming logs into incident {incident_id}...")
            # Send 50 logs rapidly
            templates = log_templates[incident_type]
            for i in range(50):
                lvl, msg = random.choice(templates)
                await client.post(f"/incidents/{incident_id}/logs", json={
                    "level": lvl,
                    "message": f"{msg} (trace_id: {random.randint(1000, 9999)})",
                    "source": "simulator"
                }, headers=headers)
                
            print(f"Triggering AI Triage for incident {incident_id}...")
            await client.post(f"/incidents/{incident_id}/triage", headers=headers)

if __name__ == "__main__":
    asyncio.run(main())
