import json
import glob
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from models import (
    ComprehensiveSuiteMetrics,
    SuiteSummary,
    RunSummary,
)

logger = logging.getLogger(__name__)

LOGS_DIR = Path("logs/benchmarks")
COMPREHENSIVE_DIR = LOGS_DIR / "comprehensive"


class MetricsStore:
    def __init__(self, suites: Dict[str, ComprehensiveSuiteMetrics], runs: Dict[str, RunSummary], load_errors: List[tuple]):
        self._suites = suites
        self._runs = runs
        self.load_errors = load_errors

    @property
    def suite_count(self) -> int:
        return len(self._suites)

    @property
    def run_count(self) -> int:
        return len(self._runs)

    def list_runs(self) -> List[RunSummary]:
        runs = list(self._runs.values())
        runs.sort(key=lambda r: r.run_start_time_wall or "", reverse=True)
        return runs

    def list_suites(
        self,
        kem_family: Optional[str] = None,
        sig_family: Optional[str] = None,
        aead: Optional[str] = None,
        nist_level: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> List[SuiteSummary]:
        suites = []
        for key, suite in self._suites.items():
            if run_id and not key.startswith(run_id + ":"):
                continue
            if kem_family and suite.crypto_identity.kem_family != kem_family:
                continue
            if sig_family and suite.crypto_identity.sig_family != sig_family:
                continue
            if aead and suite.crypto_identity.aead_algorithm != aead:
                continue
            if nist_level and suite.crypto_identity.kem_nist_level != nist_level:
                continue

            suites.append(
                SuiteSummary(
                    suite_id=suite.run_context.suite_id,
                    run_id=suite.run_context.run_id,
                    suite_index=suite.run_context.suite_index,
                    kem_algorithm=suite.crypto_identity.kem_algorithm,
                    sig_algorithm=suite.crypto_identity.sig_algorithm,
                    aead_algorithm=suite.crypto_identity.aead_algorithm,
                    suite_security_level=suite.crypto_identity.suite_security_level,
                    handshake_success=suite.handshake.handshake_success,
                    handshake_total_duration_ms=suite.handshake.handshake_total_duration_ms,
                    power_avg_w=suite.power_energy.power_avg_w,
                    energy_total_j=suite.power_energy.energy_total_j,
                    benchmark_pass_fail=suite.validation.benchmark_pass_fail,
                )
            )

        return suites

    def get_suite_by_key(self, suite_key: str) -> Optional[ComprehensiveSuiteMetrics]:
        return self._suites.get(suite_key)

    def get_suite(self, suite_id: str) -> Optional[ComprehensiveSuiteMetrics]:
        for suite in self._suites.values():
            if suite.run_context.suite_id == suite_id:
                return suite
        return None

    def get_unique_values(self, field: str) -> List[str]:
        values = set()
        for suite in self._suites.values():
            if field == "kem_family":
                value = suite.crypto_identity.kem_family
            elif field == "sig_family":
                value = suite.crypto_identity.sig_family
            elif field == "aead_algorithm":
                value = suite.crypto_identity.aead_algorithm
            elif field == "nist_level":
                value = suite.crypto_identity.kem_nist_level
            else:
                value = None
            if value:
                values.add(value)
        return sorted(values)


def _load_json(path: Path, load_errors: List[tuple]) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning("Failed to load JSON %s: %s", path, exc)
        load_errors.append((str(path), None, str(exc)))
        return {}


def _get_path_for_status(suite: ComprehensiveSuiteMetrics, path: str) -> Any:
    cur: Any = suite
    for part in path.split("."):
        if cur is None:
            return None
        if hasattr(cur, part):
            cur = getattr(cur, part)
        else:
            return None
    return cur


def _build_minimal_suite(entry: Dict[str, Any], suite_index: int) -> ComprehensiveSuiteMetrics:
    ts = entry.get("ts")
    run_id = entry.get("run_id") or entry.get("run") or ""
    suite_id = entry.get("suite_id") or ""

    suite = ComprehensiveSuiteMetrics()
    suite.run_context.run_id = run_id
    suite.run_context.suite_id = suite_id
    suite.run_context.suite_index = suite_index
    suite.run_context.run_start_time_wall = ts
    suite.run_context.run_end_time_wall = ts

    suite.crypto_identity.kem_algorithm = entry.get("kem_name")
    suite.crypto_identity.sig_algorithm = entry.get("sig_name")
    suite.crypto_identity.aead_algorithm = entry.get("aead")
    suite.crypto_identity.kem_nist_level = entry.get("nist_level")
    suite.crypto_identity.sig_nist_level = entry.get("nist_level")
    suite.crypto_identity.suite_security_level = entry.get("nist_level")

    success = entry.get("success")
    suite.handshake.handshake_total_duration_ms = entry.get("handshake_ms")
    suite.handshake.handshake_success = success if success is not None else None
    suite.handshake.handshake_failure_reason = entry.get("error")

    if success is True:
        suite.validation.benchmark_pass_fail = "PASS"
    elif success is False:
        suite.validation.benchmark_pass_fail = "FAIL"
    else:
        suite.validation.benchmark_pass_fail = None
    missing_reason = "missing_comprehensive_metrics"
    suite.validation.metric_status = {
        "comprehensive": {
            "status": "not_collected",
            "reason": missing_reason,
        }
    }
    for field in (
        "run_context.git_commit_hash",
        "run_context.gcs_hostname",
        "run_context.drone_hostname",
    ):
        if _get_path_for_status(suite, field) is None:
            suite.validation.metric_status[field] = {
                "status": "not_collected",
                "reason": missing_reason,
            }
    for field in (
        "handshake.handshake_total_duration_ms",
        "handshake.handshake_success",
        "handshake.handshake_failure_reason",
        "crypto_identity.kem_algorithm",
        "crypto_identity.sig_algorithm",
        "crypto_identity.aead_algorithm",
        "crypto_identity.suite_security_level",
        "data_plane.packets_sent",
        "data_plane.packets_received",
        "data_plane.packets_dropped",
        "data_plane.packet_delivery_ratio",
        "latency_jitter.one_way_latency_avg_ms",
        "latency_jitter.one_way_latency_p95_ms",
        "latency_jitter.jitter_avg_ms",
        "latency_jitter.jitter_p95_ms",
        "latency_jitter.rtt_avg_ms",
        "latency_jitter.rtt_p95_ms",
        "mavlink_integrity.mavlink_out_of_order_count",
        "mavlink_integrity.mavlink_packet_crc_error_count",
        "mavlink_integrity.mavlink_decode_error_count",
        "mavlink_integrity.mavlink_duplicate_count",
        "system_drone.cpu_usage_avg_percent",
        "system_drone.cpu_usage_peak_percent",
        "system_drone.memory_rss_mb",
        "system_drone.temperature_c",
        "system_gcs.cpu_usage_avg_percent",
        "system_gcs.cpu_usage_peak_percent",
        "system_gcs.memory_rss_mb",
        "system_gcs.temperature_c",
        "power_energy.power_sensor_type",
        "power_energy.power_avg_w",
        "power_energy.power_peak_w",
        "power_energy.energy_total_j",
        "power_energy.voltage_avg_v",
        "power_energy.current_avg_a",
        "power_energy.energy_per_handshake_j",
        "power_energy.power_sampling_rate_hz",
        "validation.collected_samples",
        "validation.lost_samples",
        "validation.success_rate_percent",
        "validation.benchmark_pass_fail",
    ):
        value = _get_path_for_status(suite, field)
        if value is None:
            suite.validation.metric_status[field] = {
                "status": "not_collected",
                "reason": missing_reason,
            }
    return suite


def _load_comprehensive(load_errors: List[tuple]) -> Dict[str, ComprehensiveSuiteMetrics]:
    suites: Dict[str, ComprehensiveSuiteMetrics] = {}
    for path in COMPREHENSIVE_DIR.glob("*.json"):
        payload = _load_json(path, load_errors)
        if not payload:
            continue
        try:
            suite = ComprehensiveSuiteMetrics(**payload)
        except Exception as exc:
            logger.warning("Invalid comprehensive metrics %s: %s", path, exc)
            load_errors.append((str(path), None, str(exc)))
            continue
        run_id = suite.run_context.run_id or ""
        suite_id = suite.run_context.suite_id or ""
        if not run_id or not suite_id:
            logger.warning("Missing run_id or suite_id in %s", path)
            continue
        key = f"{run_id}:{suite_id}"
        suites[key] = suite
    return suites


def _load_jsonl_entries(load_errors: List[tuple]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for fpath in glob.glob(str(LOGS_DIR / "benchmark_*.jsonl")):
        run_id = Path(fpath).name.replace("benchmark_", "").replace(".jsonl", "")
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        entry["run_id"] = run_id
                        entries.append(entry)
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("Failed to read %s: %s", fpath, exc)
            load_errors.append((str(fpath), None, str(exc)))
    return entries


def _build_runs(suites: Dict[str, ComprehensiveSuiteMetrics]) -> Dict[str, RunSummary]:
    runs: Dict[str, RunSummary] = {}
    for suite in suites.values():
        run_id = suite.run_context.run_id
        if not run_id:
            continue
        if run_id not in runs:
            runs[run_id] = RunSummary(
                run_id=run_id,
                run_start_time_wall=suite.run_context.run_start_time_wall,
                gcs_hostname=suite.run_context.gcs_hostname,
                drone_hostname=suite.run_context.drone_hostname,
                suite_count=1,
                git_commit_hash=suite.run_context.git_commit_hash,
            )
        else:
            runs[run_id].suite_count = (runs[run_id].suite_count or 0) + 1
    return runs


def build_store() -> MetricsStore:
    load_errors: List[tuple] = []
    suites = _load_comprehensive(load_errors)

    entries = _load_jsonl_entries(load_errors)
    if entries:
        index_by_run: Dict[str, int] = {}
        for entry in entries:
            run_id = entry.get("run_id") or ""
            suite_id = entry.get("suite_id") or ""
            if not run_id or not suite_id:
                continue
            index_by_run.setdefault(run_id, 0)
            suite_key = f"{run_id}:{suite_id}"
            if suite_key not in suites:
                suite = _build_minimal_suite(entry, index_by_run[run_id])
                suites[suite_key] = suite
            index_by_run[run_id] += 1

    if not suites:
        raise RuntimeError("No benchmark data found in logs/benchmarks")

    runs = _build_runs(suites)
    return MetricsStore(suites=suites, runs=runs, load_errors=load_errors)


_STORE: Optional[MetricsStore] = None


def get_store() -> MetricsStore:
    global _STORE
    if _STORE is None:
        _STORE = build_store()
    return _STORE
