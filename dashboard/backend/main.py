from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

# Handle imports depending on how run (module vs script)
try:
    from .models import RunSummary, ComprehensiveSuiteMetrics
    from .ingest import get_store
    from .routes.suites import router as suites_router
    from .settings_store import get_settings_store
except ImportError:
    from models import RunSummary, ComprehensiveSuiteMetrics
    from ingest import get_store
    from routes.suites import router as suites_router
    from settings_store import get_settings_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

app = FastAPI(
    title="Secure-Tunnel Forensic Dashboard API",
    description="API for PQC forensic benchmark data — multi-run comparison & anomaly detection.",
    version="3.0"
)

# Register API routes
app.include_router(suites_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schemas ──────────────────────────────────────────────────────────

class RunLabelRequest(BaseModel):
    run_id: str
    label: str
    run_type: str  # baseline | ddos_light | ddos_heavy

class ActiveRunsRequest(BaseModel):
    run_ids: List[str]

class ThresholdsRequest(BaseModel):
    thresholds: Dict[str, float]


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "online", "system": "Secure-Tunnel Forensic Dashboard v3"}


# ── Settings endpoints ───────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings(min_suites: int = 20):
    """Return all dashboard settings including run labels, active runs, thresholds."""
    ss = get_settings_store()
    store = get_store()
    settings = ss.get_all()
    # Attach available runs from data, filtered to only significant runs
    all_runs = store.list_runs()
    settings["available_runs"] = [
        r.model_dump() for r in all_runs if r.suite_count >= min_suites
    ]
    return settings

@app.post("/api/settings/run-label")
def set_run_label(req: RunLabelRequest):
    """Assign a label + type to a run_id."""
    ss = get_settings_store()
    ss.set_run_label(req.run_id, req.label, req.run_type)
    return {"ok": True}

@app.post("/api/settings/active-runs")
def set_active_runs(req: ActiveRunsRequest):
    """Set which runs are selected for display (up to 3)."""
    ss = get_settings_store()
    ss.set_active_runs(req.run_ids[:3])
    return {"ok": True, "active": req.run_ids[:3]}

@app.post("/api/settings/thresholds")
def set_thresholds(req: ThresholdsRequest):
    """Update anomaly detection thresholds."""
    ss = get_settings_store()
    ss.update_thresholds(req.thresholds)
    return {"ok": True}


# ── Multi-run comparison ─────────────────────────────────────────────────────

@app.get("/api/multi-run/compare")
def multi_run_compare(suite_id: str):
    """
    Compare the SAME suite across multiple runs (up to 3).
    Returns each run's full metrics for the given suite_id.
    """
    ss = get_settings_store()
    store = get_store()
    active = ss.get_active_runs()
    if not active:
        # Fall back to all available runs
        active = [r.run_id for r in store.list_runs()]

    results = []
    for run_id in active:
        key = f"{run_id}:{suite_id}"
        suite = store.get_suite_by_key(key)
        if suite is None:
            continue
        label_info = ss.get_run_label(run_id) or {"label": run_id, "type": "baseline"}
        results.append({
            "run_id": run_id,
            "label": label_info.get("label", run_id),
            "run_type": label_info.get("type", "baseline"),
            "suite": suite.model_dump(),
        })
    if not results:
        raise HTTPException(status_code=404, detail=f"Suite '{suite_id}' not found in any active run")
    return {"suite_id": suite_id, "runs": results}


@app.get("/api/multi-run/overview")
def multi_run_overview():
    """
    Return aggregated KPI data for each active run — used by Overview page
    to show multi-run comparison cards.
    """
    ss = get_settings_store()
    store = get_store()
    active = ss.get_active_runs()
    if not active:
        active = [r.run_id for r in store.list_runs()]
    thresholds = ss.get_thresholds()

    overview = []
    for run_id in active:
        label_info = ss.get_run_label(run_id) or {"label": run_id, "type": "baseline"}
        suites_for_run = [
            s for s in store._suites.values()
            if s.run_context.run_id == run_id
        ]
        if not suites_for_run:
            continue

        total = len(suites_for_run)
        passed = sum(1 for s in suites_for_run if s.validation.benchmark_pass_fail == "PASS")
        failed = sum(1 for s in suites_for_run if s.validation.benchmark_pass_fail == "FAIL")

        handshake_vals = [s.handshake.handshake_total_duration_ms for s in suites_for_run if s.handshake.handshake_total_duration_ms is not None]
        power_vals = [s.power_energy.power_avg_w for s in suites_for_run if s.power_energy.power_avg_w is not None]
        energy_vals = [s.power_energy.energy_total_j for s in suites_for_run if s.power_energy.energy_total_j is not None]
        loss_vals = [s.data_plane.packet_loss_ratio for s in suites_for_run if s.data_plane.packet_loss_ratio is not None]

        # Anomaly counts
        hs_threshold = thresholds.get("handshake_ms_high", 10000)
        loss_threshold = thresholds.get("packet_loss_warning", 0.01)
        anomaly_count = sum(1 for v in handshake_vals if v > hs_threshold) + sum(1 for v in loss_vals if v > loss_threshold)

        overview.append({
            "run_id": run_id,
            "label": label_info.get("label", run_id),
            "run_type": label_info.get("type", "baseline"),
            "total_suites": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "avg_handshake_ms": round(sum(handshake_vals) / len(handshake_vals), 2) if handshake_vals else None,
            "max_handshake_ms": round(max(handshake_vals), 2) if handshake_vals else None,
            "avg_power_w": round(sum(power_vals) / len(power_vals), 3) if power_vals else None,
            "avg_energy_j": round(sum(energy_vals) / len(energy_vals), 3) if energy_vals else None,
            "total_energy_j": round(sum(energy_vals), 3) if energy_vals else None,
            "avg_packet_loss": round(sum(loss_vals) / len(loss_vals), 6) if loss_vals else None,
            "anomaly_count": anomaly_count,
        })
    return {"runs": overview}


@app.get("/api/anomalies")
def detect_anomalies(run_id: Optional[str] = None):
    """
    Detect anomalies across suites based on configured thresholds.
    Returns list of flagged suites with reasons.
    """
    ss = get_settings_store()
    store = get_store()
    thresholds = ss.get_thresholds()

    target_suites = list(store._suites.values())
    if run_id:
        target_suites = [s for s in target_suites if s.run_context.run_id == run_id]

    anomalies = []
    for suite in target_suites:
        flags = []
        sid = suite.run_context.suite_id
        rid = suite.run_context.run_id

        # Handshake anomalies
        hs = suite.handshake.handshake_total_duration_ms
        if hs is not None:
            if hs > thresholds.get("handshake_ms_critical", 30000):
                flags.append({"metric": "handshake_ms", "value": hs, "severity": "critical", "threshold": thresholds.get("handshake_ms_critical", 30000)})
            elif hs > thresholds.get("handshake_ms_high", 10000):
                flags.append({"metric": "handshake_ms", "value": hs, "severity": "warning", "threshold": thresholds.get("handshake_ms_high", 10000)})

        # Packet loss
        loss = suite.data_plane.packet_loss_ratio
        if loss is not None:
            if loss > thresholds.get("packet_loss_critical", 0.05):
                flags.append({"metric": "packet_loss", "value": loss, "severity": "critical", "threshold": thresholds.get("packet_loss_critical", 0.05)})
            elif loss > thresholds.get("packet_loss_warning", 0.01):
                flags.append({"metric": "packet_loss", "value": loss, "severity": "warning", "threshold": thresholds.get("packet_loss_warning", 0.01)})

        # Handshake failure
        if suite.handshake.handshake_success is False:
            flags.append({"metric": "handshake_failure", "value": suite.handshake.handshake_failure_reason or "unknown", "severity": "critical", "threshold": None})

        # Benchmark fail
        if suite.validation.benchmark_pass_fail == "FAIL":
            flags.append({"metric": "benchmark_fail", "value": "FAIL", "severity": "critical", "threshold": None})

        # MAVLink integrity issues
        for field_name, attr in [
            ("crc_errors", "mavlink_packet_crc_error_count"),
            ("decode_errors", "mavlink_decode_error_count"),
            ("msg_drops", "mavlink_msg_drop_count"),
            ("out_of_order", "mavlink_out_of_order_count"),
            ("duplicates", "mavlink_duplicate_count"),
        ]:
            val = getattr(suite.mavlink_integrity, attr, None)
            if val is not None and val > 0:
                flags.append({"metric": f"mavlink_{field_name}", "value": val, "severity": "warning", "threshold": 0})

        # Replay / auth drops
        if suite.data_plane.drop_replay and suite.data_plane.drop_replay > 0:
            flags.append({"metric": "replay_drops", "value": suite.data_plane.drop_replay, "severity": "critical", "threshold": 0})
        if suite.data_plane.drop_auth and suite.data_plane.drop_auth > 0:
            flags.append({"metric": "auth_drops", "value": suite.data_plane.drop_auth, "severity": "critical", "threshold": 0})

        if flags:
            anomalies.append({
                "suite_id": sid,
                "run_id": rid,
                "key": f"{rid}:{sid}",
                "kem": suite.crypto_identity.kem_algorithm,
                "sig": suite.crypto_identity.sig_algorithm,
                "flags": flags,
                "severity": "critical" if any(f["severity"] == "critical" for f in flags) else "warning",
            })

    anomalies.sort(key=lambda a: (0 if a["severity"] == "critical" else 1, a["suite_id"]))
    return {"anomalies": anomalies, "total": len(anomalies), "thresholds": thresholds}
