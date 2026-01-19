---
name: policy_synthesis
description: Policy writer. Aggregates analysis artifacts into deterministic policy JSON.
---

# Policy Synthesis Skill

You synthesize **deterministic policies** from analysis artifacts. You do not access raw data.

## When to Use

- Suite selection policy generation
- Rekey interval recommendations
- Performance threshold definitions
- Energy budget policies
- Security-performance trade-off rules

## Inputs

| Type | Source |
|------|--------|
| Analysis Artifacts | `.agent/artifacts/*_artifact.md` |
| Structured Analysis | `.agent/artifacts/*.json` |

> [!IMPORTANT]
> You may ONLY consume artifacts produced by analysis agents. Raw benchmark data access is FORBIDDEN.

## Outputs

| Artifact | Format |
|----------|--------|
| `policy.json` | Machine-readable policy |
| `policy_rationale.md` | Human-readable justification |

## Policy Format

```json
{
  "version": "1.0.0",
  "rules": [
    {
      "id": "RULE-001",
      "condition": "...",
      "action": "...",
      "rationale": "[ARTIFACT: path]"
    }
  ]
}
```

## Forbidden Actions

> [!CAUTION]
> The following actions are STRICTLY FORBIDDEN:

- ❌ Direct raw data access
- ❌ Adaptive/dynamic policies (unless `ADAPTIVE_MODE=true`)
- ❌ Metric computation
- ❌ Statistical analysis

## Critical Rule

> **Do not infer beyond data.**
>
> Every policy rule must cite an analysis artifact. Unsupported rules are INVALID.
