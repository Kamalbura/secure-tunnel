# Global Agent Rules (CANONICAL)

> [!IMPORTANT]
> These rules are **immutable** and apply to **all agents** in this system.

---

## 1. Drone-Side Metrics Drive Policy

All policy decisions MUST be derived from drone-collected metrics. GCS metrics are supplementary only.

## 2. GCS-Side Metrics Validate Integrity

GCS metrics serve to validate data integrity and consistency. They do NOT drive policy.

## 3. No Adaptive Policies

Policies MUST be deterministic unless the `ADAPTIVE_MODE` flag is explicitly enabled.

## 4. Rekey Decisions Must Be Explainable

Every rekey decision MUST be traceable to:
- A specific metric threshold
- A referenced artifact
- A documented rationale

## 5. UI/Dashboard Agents Cannot Recompute

Dashboard agents consume pre-computed artifacts. They MUST NOT:
- Perform statistical calculations
- Apply policy logic
- Interpret raw data

## 6. Raw Benchmark Data Is Read-Only

The `logs/`, `bench_results*/`, and `suite_benchmarks/` directories are **immutable**.

Violations:
- ❌ Modifying JSONL files
- ❌ Deleting benchmark records
- ❌ Rewriting timestamps

## 7. All Decisions Must Reference Artifacts

No conclusion or recommendation is valid without an artifact citation.

Format: `[ARTIFACT: path/to/artifact.md]`

---

## 8. Memory Governance (Mandatory)

Every agent MUST maintain a persistent memory file at `.agent/memory/<agent_id>.md`.

### Before ANY Action

1. Read memory file
2. Reconstruct prior context
3. Check consistency with new instruction

### After ANY Action

1. Update memory file
2. Append to Change Log
3. Record decisions, constraints, learnings

### Forbidden

- ❌ Relying solely on chat history
- ❌ Overwriting memory without logging
- ❌ Ignoring prior decisions

### Conflict Handling

If an agent detects:
- Contradiction with prior memory
- Missing historical context
- Ambiguous instruction

The agent MUST **STOP** and report before proceeding.

---

## Enforcement

Agents violating these rules MUST be rejected by the Orchestrator.

