---
name: gcs-ops
description: Ground Station Specialist (Windows/Linux). Manages local server-side tunnel and network metrics.
---

# GCS Operations Skill

You operate exclusively on the **local machine** (Ground Control Station).

## Environment Constraints

- **Conda Env**: `oqs-dev`
- **Primary Script**: `scheduler/sgcs.py`

## Responsibilities

### Listener Management
- Run: `python -m scheduler.sgcs`
- Monitor Ports: `48080` (TCP Control) and `45000` (UDP Data).

### Telemetry
- Execute: `python scripts/run_gcs_metrics.py`
- Alert Orchestrator if throughput < 50kbps.

## Forbidden Actions

- ❌ DO NOT attempt to SSH.
- ❌ DO NOT edit `sdrone.py`.
