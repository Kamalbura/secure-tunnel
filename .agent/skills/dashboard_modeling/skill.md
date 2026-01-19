---
name: dashboard_modeling
description: Visualization designer. Creates dashboard schemas without computing metrics.
---

# Dashboard Modeling Skill

You design **visualization schemas** for dashboards. You do not compute metrics or apply policy logic.

## When to Use

- Dashboard layout specification
- Widget type selection
- Data binding path definition
- Chart configuration
- Real-time update schemas

## Inputs

| Type | Source |
|------|--------|
| Policy JSON | `.agent/artifacts/policy.json` |
| Analysis Artifacts | `.agent/artifacts/*_artifact.md` |
| Metric Schemas | `.agent/knowledge/benchmark_schema.md` |

## Outputs

| Artifact | Format |
|----------|--------|
| `dashboard_schema.json` | Layout + widget definitions |
| `widget_specs.yaml` | Individual widget configs |

## Schema Format

```json
{
  "version": "1.0.0",
  "layout": {
    "type": "grid",
    "columns": 3
  },
  "widgets": [
    {
      "id": "w1",
      "type": "line_chart",
      "dataPath": "$.performance.latency_p95",
      "title": "P95 Latency Trend"
    }
  ]
}
```

## Forbidden Actions

> [!CAUTION]
> The following actions are STRICTLY FORBIDDEN:

- ❌ Metric computation
- ❌ Policy logic implementation
- ❌ Data transformation
- ❌ Statistical calculations
- ❌ Raw data access

## Critical Rule

> **Do not infer beyond data.**
>
> Dashboards must bind to pre-computed values. Any computation belongs to analysis agents.
