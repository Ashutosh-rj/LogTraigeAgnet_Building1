# app/agents/tool_definitions.py

CLAUDE_TOOLS = [
    {
        "name": "log_search",
        "description": "Searches recent logs for a specific incident. You can filter by log level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "The UUID of the incident"},
                "level_filter": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["debug", "info", "warning", "error", "critical"]},
                    "description": "Optional list of log levels to filter by"
                },
                "limit": {"type": "integer", "description": "Maximum number of logs to return (default 200)"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "db_lookup",
        "description": "Look up records from the database such as incidents or users.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "enum": ["incidents", "users"],
                    "description": "The database table to query"
                },
                "id": {"type": "string", "description": "The UUID of the record"}
            },
            "required": ["table", "id"]
        }
    },
    {
        "name": "report_emit",
        "description": "Emits the final triage report to the database and notifies listeners.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "The UUID of the incident"},
                "summary": {"type": "string", "description": "High level summary of what went wrong"},
                "root_cause": {"type": "string", "description": "Detailed explanation of the root cause"},
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recommended actions to resolve or mitigate the issue"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score of the assessment from 0.0 to 1.0"
                }
            },
            "required": ["incident_id", "summary", "root_cause", "recommendations", "confidence"]
        }
    }
]
