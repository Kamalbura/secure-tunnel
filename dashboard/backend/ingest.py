import json
import glob
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    from .models import (
        ComprehensiveSuiteMetrics,
        SuiteSummary,
        RunSummary,
    )
    from .analysis import get_metric_value_for_summary
except ImportError:
    from models import (
        ComprehensiveSuiteMetrics,
        SuiteSummary,
        RunSummary,
    )
    from analysis import get_metric_value_for_summary

logger = logging.getLogger(__name__)

LOGS_DIR = Path("logs/benchmarks")
COMPREHENSIVE_DIR = LOGS_DIR / "comprehensive"
GCS_METRICS_GLOB = str(LOGS_DIR / "**" / "gcs_suite_metrics.jsonl")

# Strict filter: set to a run_id string to limit to one run, or None to load all
STRICT_RUN_FILTER = None  # Was "20260206_032324"; now loads all runs for multi-run comparison


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
                    power_sensor_type=suite.power_energy.power_sensor_type,
                    power_avg_w=suite.power_energy.power_avg_w,
                    energy_total_j=suite.power_energy.energy_total_j,
                    benchmark_pass_fail=suite.validation.benchmark_pass_fail,
                    ingest_status=suite.ingest_status,
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


def _parse_comprehensive_filename(path: Path) -> Optional[tuple]:
    """Return (suite_id, run_id, role) from comprehensive JSON filename.

    Supports two naming patterns:
      - {suite}_{date}_{time}_{role}.json   (legacy drone output)
      - {date}_{time}_{suite}_{role}.json   (current GCS + drone output)

    Detection: if the first two underscore-separated parts look like
    YYYYMMDD (8 digits) and HHMMSS (6 digits), treat them as the run_id.
    """
    if path.suffix.lower() != ".json":
        return None
    parts = path.stem.split("_")
    if len(parts) < 4:
        return None
    role = parts[-1]
    if role not in {"gcs", "drone"}:
        return None

    # Detect {date}_{time}_{suite}_{role} pattern
    if (len(parts[0]) == 8 and parts[0].isdigit() and
            len(parts[1]) == 6 and parts[1].isdigit()):
        date_part = parts[0]
        time_part = parts[1]
        run_id = f"{date_part}_{time_part}"
        suite_id = "_".join(parts[2:-1])
    else:
        # Legacy pattern: {suite}_{date}_{time}_{role}
        time_part = parts[-2]
        date_part = parts[-3]
        run_id = f"{date_part}_{time_part}"
        suite_id = "_".join(parts[:-3])

    return suite_id, run_id, role


def _parse_run_id(run_id: str) -> Optional[datetime]:
    """Parse run_id timestamp (YYYYMMDD_HHMMSS)."""
    try:
        # Expected format: 20260205_043852
        return datetime.strptime(run_id, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def _consolidate_runs(
    suites: Dict[str, ComprehensiveSuiteMetrics],
    time_threshold: timedelta = timedelta(minutes=5)
) -> Dict[str, ComprehensiveSuiteMetrics]:
    """
    Consolidate runs that are within `time_threshold` of each other.
    
    This fixes the issue where distributed benchmarks output files with slightly 
    different timestamps, causing them to appear as fragmented runs.
    """
    if not suites:
        return suites

    # 1. Group run IDs by time
    run_ids = set()
    for s in suites.values():
        if s.run_context.run_id:
            run_ids.add(s.run_context.run_id)
    
    sorted_runs = []
    for rid in run_ids:
        dt = _parse_run_id(rid)
        if dt:
            sorted_runs.append((dt, rid))
    
    # Sort by time ascending
    sorted_runs.sort(key=lambda x: x[0])

    if not sorted_runs:
        return suites

    # 2. Cluster runs
    # Map original_run_id -> canonical_run_id
    run_map: Dict[str, str] = {}
    
    current_canonical_id = sorted_runs[0][1]
    
    run_map[current_canonical_id] = current_canonical_id
    
    for i in range(1, len(sorted_runs)):
        dt, rid = sorted_runs[i]
        prev_dt, _ = sorted_runs[i-1]
        
        # Check gap from PREVIOUS run (single-linkage), not cluster start.
        # This handles long benchmarks where timestamps might drift sequentially.
        if dt - prev_dt <= time_threshold:
            # Within window of previous item - map to current canonical
            run_map[rid] = current_canonical_id
        else:
            # Gap > threshold -> New cluster
            current_canonical_id = rid
            run_map[rid] = current_canonical_id

    # 3. Remap suites
    consolidated_suites: Dict[str, ComprehensiveSuiteMetrics] = {}
    
    for original_key, suite in suites.items():
        original_run_id = suite.run_context.run_id
        suite_id = suite.run_context.suite_id
        
        # If run_id didn't parse or wasn't mapped, keep original
        if not original_run_id or original_run_id not in run_map:
            consolidated_suites[original_key] = suite
            continue
            
        canonical_run_id = run_map[original_run_id]
        
        # Update suite context
        suite.run_context.run_id = canonical_run_id
        
        # New key
        new_key = f"{canonical_run_id}:{suite_id}"
        
        # Collision handling: 
        # If we have a collision (e.g. same suite ID in two merged timestamps),
        # we generally prefer the 'later' one or the one we just processed.
        # Since we're iterating in arbitrary dictionary order, let's just overwrite for now.
        # Real duplicates shouldn't happen often in this specific benchmark flow unless retried.
        consolidated_suites[new_key] = suite

    log_msg = f"Consolidated {len(suites)} suites into {len(consolidated_suites)} unique suites across {len(set(run_map.values()))} logical runs."
    logger.info(log_msg)
    
    return consolidated_suites


def _build_invalid_suite(
    suite_id: str,
    run_id: str,
    reason: str,
    *,
    ingest_status: str = "comprehensive_failed",
) -> ComprehensiveSuiteMetrics:
    suite = ComprehensiveSuiteMetrics()
    suite.run_context.run_id = run_id
    suite.run_context.suite_id = suite_id
    suite.run_context.suite_index = 0
    suite.validation.metric_status = {
        "ingest": {"status": "invalid", "reason": reason},
        "comprehensive": {"status": "invalid", "reason": reason},
    }
    suite.ingest_status = ingest_status
    return suite


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
    suite.ingest_status = "jsonl_fallback"
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


def _load_gcs_jsonl_entries(load_errors: List[tuple]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for fpath in glob.glob(GCS_METRICS_GLOB, recursive=True):
        path = Path(fpath)
        parent_name = path.parent.name
        # Strip 'live_run_' prefix so run_id matches comprehensive filenames
        if parent_name.startswith("live_run_"):
            dir_run_id = parent_name[len("live_run_"):]
        else:
            dir_run_id = parent_name
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        # Prefer entry's own run_id if present; else use dir-derived
                        if not entry.get("run_id"):
                            entry["run_id"] = dir_run_id
                        entries.append(entry)
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            load_errors.append((str(path), None, str(exc)))
    return entries


def _merge_gcs_metrics(
    suites: Dict[str, ComprehensiveSuiteMetrics],
    entries: List[Dict[str, Any]],
) -> None:
    for entry in entries:
        run_id = entry.get("run_id") or ""
        suite_id = entry.get("suite") or entry.get("suite_id") or ""
        if not run_id or not suite_id:
            continue
        key = f"{run_id}:{suite_id}"
        suite = suites.get(key)
        if suite is None:
            continue

        validation = suite.gcs_validation.setdefault("jsonl", {})
        system_gcs = entry.get("system_gcs")
        if isinstance(system_gcs, dict):
            validation["system_gcs"] = system_gcs
            # Map GCS system metrics into primary suite fields if missing
            sg = suite.system_gcs
            if sg.cpu_usage_avg_percent is None:
                sg.cpu_usage_avg_percent = system_gcs.get("cpu_usage_avg_percent")
            if sg.cpu_usage_peak_percent is None:
                sg.cpu_usage_peak_percent = system_gcs.get("cpu_usage_peak_percent")
            if sg.cpu_freq_mhz is None:
                sg.cpu_freq_mhz = system_gcs.get("cpu_freq_mhz")
            if sg.memory_rss_mb is None:
                sg.memory_rss_mb = system_gcs.get("memory_rss_mb")
            if sg.memory_vms_mb is None:
                sg.memory_vms_mb = system_gcs.get("memory_vms_mb")
            if sg.thread_count is None:
                sg.thread_count = system_gcs.get("thread_count")
            if sg.temperature_c is None:
                sg.temperature_c = system_gcs.get("temperature_c")
            if sg.uptime_s is None:
                sg.uptime_s = system_gcs.get("uptime_s")
            if sg.load_avg_1m is None:
                sg.load_avg_1m = system_gcs.get("load_avg_1m")
            if sg.load_avg_5m is None:
                sg.load_avg_5m = system_gcs.get("load_avg_5m")
            if sg.load_avg_15m is None:
                sg.load_avg_15m = system_gcs.get("load_avg_15m")

        latency_jitter = entry.get("latency_jitter")
        if isinstance(latency_jitter, dict):
            validation["latency_jitter"] = latency_jitter
            # Map GCS latency metrics into primary suite fields if missing
            lj = suite.latency_jitter
            if lj.one_way_latency_avg_ms is None:
                lj.one_way_latency_avg_ms = latency_jitter.get("one_way_latency_avg_ms")
            if lj.one_way_latency_p95_ms is None:
                lj.one_way_latency_p95_ms = latency_jitter.get("one_way_latency_p95_ms")
            if lj.jitter_avg_ms is None:
                lj.jitter_avg_ms = latency_jitter.get("jitter_avg_ms")
            if lj.jitter_p95_ms is None:
                lj.jitter_p95_ms = latency_jitter.get("jitter_p95_ms")
            if lj.latency_sample_count is None:
                lj.latency_sample_count = latency_jitter.get("latency_sample_count")
            if not lj.latency_invalid_reason:
                lj.latency_invalid_reason = latency_jitter.get("latency_invalid_reason")
            if lj.one_way_latency_valid is None:
                lj.one_way_latency_valid = latency_jitter.get("one_way_latency_valid")

            if lj.rtt_avg_ms is None:
                lj.rtt_avg_ms = latency_jitter.get("rtt_avg_ms")
            if lj.rtt_p95_ms is None:
                lj.rtt_p95_ms = latency_jitter.get("rtt_p95_ms")
            if lj.rtt_sample_count is None:
                lj.rtt_sample_count = latency_jitter.get("rtt_sample_count")
            if not lj.rtt_invalid_reason:
                lj.rtt_invalid_reason = latency_jitter.get("rtt_invalid_reason")
            if lj.rtt_valid is None:
                lj.rtt_valid = latency_jitter.get("rtt_valid")

        mavlink_validation = entry.get("mavlink_validation")
        if isinstance(mavlink_validation, dict):
            validation["mavlink_validation"] = mavlink_validation
            # Map GCS MAVLink validation into primary suite fields if missing
            mg = suite.mavproxy_gcs
            if mg.mavproxy_gcs_total_msgs_received is None:
                mg.mavproxy_gcs_total_msgs_received = mavlink_validation.get("total_msgs_received")
            if mg.mavproxy_gcs_seq_gap_count is None:
                mg.mavproxy_gcs_seq_gap_count = mavlink_validation.get("seq_gap_count")

        proxy_status = entry.get("proxy_status")
        if isinstance(proxy_status, dict):
            validation["proxy_status"] = proxy_status
            # Map proxy counters into data plane if missing
            counters = proxy_status.get("counters") if isinstance(proxy_status.get("counters"), dict) else None
            if counters and suite.data_plane.packets_sent is None:
                _apply_proxy_counters_to_data_plane(suite, counters)


def _apply_proxy_counters_to_data_plane(
    suite: ComprehensiveSuiteMetrics,
    counters: Dict[str, Any],
) -> None:
    dp = suite.data_plane
    dp.ptx_in = counters.get("ptx_in")
    dp.ptx_out = counters.get("ptx_out")
    dp.enc_in = counters.get("enc_in")
    dp.enc_out = counters.get("enc_out")
    dp.drop_replay = counters.get("drop_replay")
    dp.drop_auth = counters.get("drop_auth")
    dp.drop_header = counters.get("drop_header")

    dp.replay_drop_count = dp.drop_replay if dp.drop_replay is not None else None
    drop_session_epoch = counters.get("drop_session_epoch")
    if dp.drop_auth is not None and dp.drop_header is not None and drop_session_epoch is not None:
        dp.decode_failure_count = dp.drop_auth + dp.drop_header + drop_session_epoch
    else:
        dp.decode_failure_count = None

    dp.packets_sent = dp.enc_out
    dp.packets_received = dp.enc_in
    if dp.drop_replay is not None and dp.drop_auth is not None and dp.drop_header is not None:
        dp.packets_dropped = dp.drop_replay + dp.drop_auth + dp.drop_header
    else:
        dp.packets_dropped = None

    if dp.packets_sent is not None and dp.packets_dropped is not None and dp.packets_sent > 0:
        dp.packet_loss_ratio = dp.packets_dropped / dp.packets_sent
        dp.packet_delivery_ratio = 1.0 - dp.packet_loss_ratio
    else:
        dp.packet_loss_ratio = None
        dp.packet_delivery_ratio = None

    dp.bytes_sent = counters.get("ptx_bytes_out") if "ptx_bytes_out" in counters else counters.get("bytes_out")
    dp.bytes_received = counters.get("ptx_bytes_in") if "ptx_bytes_in" in counters else counters.get("bytes_in")


def _is_suite_scientifically_valid(suite: ComprehensiveSuiteMetrics) -> bool:
    hs = suite.handshake
    latency = suite.latency_jitter
    dp = suite.data_plane
    has_handshake = any(
        value is not None and value != 0
        for value in (
            hs.handshake_total_duration_ms,
            hs.end_to_end_handshake_duration_ms,
            hs.protocol_handshake_duration_ms,
        )
    )
    has_latency = bool(latency.one_way_latency_valid) or bool(latency.rtt_valid)
    has_throughput = any(
        isinstance(value, (int, float)) and value > 0
        for value in (
            dp.goodput_mbps,
            dp.achieved_throughput_mbps,
        )
    )
    return bool(has_handshake or has_latency or has_throughput)


def _load_comprehensive(load_errors: List[tuple]) -> Dict[str, ComprehensiveSuiteMetrics]:
    suites: Dict[str, ComprehensiveSuiteMetrics] = {}
    gcs_only: Dict[str, Dict[str, Any]] = {}
    for path in COMPREHENSIVE_DIR.glob("*.json"):
        payload = _load_json(path, load_errors)
        parsed = _parse_comprehensive_filename(path)
        if not parsed:
            continue
        suite_id, run_id, role = parsed
        key = f"{run_id}:{suite_id}"
        if role == "gcs":
            if key in suites:
                suites[key].raw_gcs = payload
                suites[key].gcs_validation = {"source": "gcs_json", "payload": payload}
            else:
                gcs_only[key] = payload
            continue
        try:
            suite = ComprehensiveSuiteMetrics(**payload)
        except Exception as exc:
            logger.warning("Invalid comprehensive metrics %s: %s", path, exc)
            load_errors.append((str(path), None, str(exc)))
            suite = _build_invalid_suite(suite_id, run_id, str(exc))
            suite.raw_drone = payload
            if key in gcs_only:
                suite.raw_gcs = gcs_only.pop(key)
                suite.gcs_validation = {"source": "gcs_json", "payload": suite.raw_gcs}
            suites[key] = suite
            continue
        run_id = suite.run_context.run_id or ""
        suite_id = suite.run_context.suite_id or ""
        if not run_id or not suite_id:
            logger.warning("Missing run_id or suite_id in %s", path)
            suite = _build_invalid_suite(suite_id, run_id, "missing run_id or suite_id")
            suite.raw_drone = payload
            if key in gcs_only:
                suite.raw_gcs = gcs_only.pop(key)
                suite.gcs_validation = {"source": "gcs_json", "payload": suite.raw_gcs}
            suites[key] = suite
            load_errors.append((str(path), None, "missing run_id or suite_id"))
            continue
        key = f"{run_id}:{suite_id}"
        suite.raw_drone = payload
        # Preserve existing entry (e.g. one already merged with GCS data)
        if key in suites and suites[key].raw_gcs is not None:
            continue
        if key in gcs_only:
            suite.raw_gcs = gcs_only.pop(key)
            suite.gcs_validation = {"source": "gcs_json", "payload": suite.raw_gcs}
        suites[key] = suite
    for key, payload in gcs_only.items():
        run_id, suite_id = key.split(":", 1)
        suite = _build_invalid_suite(suite_id, run_id, "missing_drone_comprehensive_metrics", ingest_status="missing_drone_comprehensive_metrics")
        suite.raw_gcs = payload
        suite.gcs_validation = {"source": "gcs_json", "payload": payload}
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
    
    # Consolidate runs before processing
    suites = _consolidate_runs(suites)

    if STRICT_RUN_FILTER:
        logger.info(f"Applying strict filter: {STRICT_RUN_FILTER}")
        filtered = {}
        for k, v in suites.items():
            # Check if canonical run_id matches filter
            if v.run_context.run_id == STRICT_RUN_FILTER:
                filtered[k] = v
        suites = filtered

    gcs_entries = _load_gcs_jsonl_entries(load_errors)
    if gcs_entries:
        _merge_gcs_metrics(suites, gcs_entries)

    for suite in suites.values():
        if suite.latency_source is None:
            if suite.latency_jitter.one_way_latency_avg_ms is not None or suite.latency_jitter.rtt_avg_ms is not None:
                suite.latency_source = "drone"
            elif isinstance(suite.gcs_validation.get("jsonl", {}).get("latency_jitter"), dict):
                suite.latency_source = "gcs_validation"
        if suite.integrity_source is None:
            if any(
                getattr(suite.mavlink_integrity, field) is not None
                for field in (
                    "mavlink_packet_crc_error_count",
                    "mavlink_decode_error_count",
                    "mavlink_msg_drop_count",
                    "mavlink_out_of_order_count",
                    "mavlink_duplicate_count",
                )
            ):
                suite.integrity_source = "drone"
            elif isinstance(suite.gcs_validation.get("jsonl", {}).get("mavlink_validation"), dict):
                suite.integrity_source = "gcs_validation"
        if suite.packet_counters_source is None:
            if suite.data_plane.packets_sent is not None or suite.data_plane.enc_out is not None:
                suite.packet_counters_source = "drone"
            elif isinstance(suite.gcs_validation.get("jsonl", {}).get("proxy_status"), dict):
                suite.packet_counters_source = "gcs_validation"

        if suite.ingest_status in {"comprehensive_failed"}:
            continue
        if not _is_suite_scientifically_valid(suite):
            suite.ingest_status = "invalid_run"
            suite.validation.metric_status["suite_validity"] = {
                "status": "invalid",
                "reason": "missing_valid_latency_throughput_and_handshake",
            }
            logger.warning(
                "Suite marked invalid (scientific validity check failed): %s:%s",
                suite.run_context.run_id,
                suite.run_context.suite_id,
            )

    if not suites:
        entries = _load_jsonl_entries(load_errors)
        if entries:
            logger.warning("Comprehensive metrics missing; using JSONL fallback for suite summaries")
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
