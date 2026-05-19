# Orchestration

## Start a workflow
POST /orchestrations

```json
{
  "nodes": [
    {"id": "plan", "agent": "planner", "input": {"goal": "article"}},
    {"id": "write", "agent": "writer", "input": {"text": "Hello", "style": "concise"}, "depends_on": ["plan"]},
    {"id": "analyze", "agent": "analyst", "depends_on": ["write"]}
  ],
  "shared": {"project_id": "proj123"}
}
```

## Get status
GET /orchestrations/{workflow_id}

## Cancel
POST /orchestrations/{workflow_id}/cancel