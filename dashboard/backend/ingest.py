import json
import glob
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Use relative import if running as package, else absolute might be needed if sys.path hacked
try:
    from .schemas import CanonicalMetrics, RunSummary, SuiteDetail
except ImportError:
    # Fallback for debugging
    from schemas import CanonicalMetrics, RunSummary, SuiteDetail

logger = logging.getLogger(__name__)

# Path aliases - strict
LOGS_DIR = Path("logs/benchmarks")
COMPREHENSIVE_DIR = LOGS_DIR / "comprehensive"

def load_comprehensive_json(suite_id: str, run_ts: str) -> Dict:
    """Find comprehensive metrics file."""
    try:
        date_part = run_ts.split('T')[0].replace('-', '') 
        pattern = str(COMPREHENSIVE_DIR / f"*{suite_id}*{date_part}*_drone.json")
        matches = glob.glob(pattern)
        
        if not matches:
            return {}
        
        # Taking the newest file if multiple
        matches.sort(key=os.path.getmtime, reverse=True)
        with open(matches[0], 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Comprehensive load failed for {suite_id}: {e}")
        return {}

def flatten_comprehensive(comp_data: Dict) -> Dict:
    """Flatten nested JSON to match CanonicalMetrics."""
    flat = {}
    
    # Sections to flatten
    sections = [
        "run_context", "crypto_identity", "lifecycle", "handshake",
        "crypto_primitives", "rekey", "data_plane",
        "mavproxy_drone", "mavproxy_gcs", "mavlink_integrity",
        "fc_telemetry", "control_plane", "system_drone",
        "power_energy", "validation", "observability"
    ]
    
    for sec in sections:
        flat.update(comp_data.get(sec, {}))
        
    # Remap specifics
    sys = comp_data.get("system_drone", {})
    if "cpu_usage_avg" in sys: flat["cpu_usage_avg_percent"] = sys["cpu_usage_avg"]
    if "cpu_usage_peak" in sys: flat["cpu_usage_peak_percent"] = sys["cpu_usage_peak"]
    
    return flat

def ingest_all_runs() -> List[RunSummary]:
    runs_map = {}
    files = glob.glob(str(LOGS_DIR / "benchmark_*.jsonl"))
    
    for fpath in files:
        try:
            with open(fpath, 'r') as f:
                lines = f.readlines()
            
            total = 0
            success = 0
            ts = ""
            
            for line in lines:
                try:
                    d = json.loads(line)
                    if "suite_id" in d:
                        total += 1
                        if d.get("success", False): success += 1
                        if not ts: ts = d.get("ts", "")
                except: continue
                
            fname = Path(fpath).name
            rid = fname.replace("benchmark_", "").replace(".jsonl", "")
            
            if total > 0:
                runs_map[rid] = RunSummary(
                    run_id=rid,
                    timestamp=ts,
                    suites_total=total,
                    suites_completed=total,
                    success_rate=success/total,
                    duration_s=0.0
                )
        except Exception:
            pass
            
    return sorted(list(runs_map.values()), key=lambda x: x.timestamp, reverse=True)

def get_run_details(run_id: str) -> List[CanonicalMetrics]:
    fpath = LOGS_DIR / f"benchmark_{run_id}.jsonl"
    if not fpath.exists():
        return []
        
    results = []
    with open(fpath, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        try:
            basic = json.loads(line)
            sid = basic.get("suite_id")
            ts = basic.get("ts")
            
            comp = load_comprehensive_json(sid, ts)
            flat = flatten_comprehensive(comp)
            
            # Merge Truth
            flat.update({
                "suite_id": sid,
                "suite_index": i,
                "run_id": run_id,
                "handshake_total_duration_ms": basic.get("handshake_ms", 0.0),
                "handshake_success": basic.get("success", False),
                # Set required defaults if missing
                "run_start_time_wall": ts,
                "run_end_time_wall": ts,
                "packets_sent": flat.get("packets_sent", 0),
                "packets_received": flat.get("packets_received", 0),
                "packets_dropped": flat.get("packets_dropped", 0),
                "packet_loss_ratio": flat.get("packet_loss_ratio", 0.0),
                "packet_delivery_ratio": flat.get("packet_delivery_ratio", 0.0),
                 # Schema enforcement fix: fill missing required fields with 0/empty
                "git_commit_hash": flat.get("git_commit_hash", "unknown"),
                "git_dirty_flag": flat.get("git_dirty_flag", False),
                "gcs_hostname": flat.get("gcs_hostname", "unknown"),
                "drone_hostname": flat.get("drone_hostname", "unknown"),
                "gcs_ip": flat.get("gcs_ip", "0.0.0.0"),
                "drone_ip": flat.get("drone_ip", "0.0.0.0"),
                 "python_env_gcs": "unknown", "python_env_drone": "unknown",
                "liboqs_version": "unknown", "kernel_version_gcs": "unknown", "kernel_version_drone": "unknown",
                 "run_start_time_mono": 0.0, "run_end_time_mono": 0.0,
                 "kem_algorithm": basic.get("kem_name", "unknown"),
                 "sig_algorithm": basic.get("sig_name", "unknown"),
                 "aead_algorithm": basic.get("aead", "unknown"),
                 "kem_family": "unknown", "sig_family": "unknown",
                 "kem_nist_level": basic.get("nist_level", "unknown"),
                 "sig_nist_level": basic.get("nist_level", "unknown"),
                  "suite_security_level": basic.get("nist_level", "unknown"),
                  "suite_selected_time": 0.0, "suite_activated_time": 0.0,
                   "suite_deactivated_time": 0.0,
                   "suite_total_duration_ms": 0.0, "suite_active_duration_ms": 0.0,
                                        "handshake_start_time_drone": 0.0, "handshake_end_time_drone": 0.0,
                      "handshake_failure_reason": basic.get("error", ""),
                      "total_crypto_time_ms": 0.0,
                      "mavproxy_drone_start_time": 0.0, "mavproxy_drone_end_time": 0.0,
                      "mavproxy_drone_tx_pps": 0.0, "mavproxy_drone_rx_pps": 0.0,
                      "mavproxy_drone_total_msgs_sent": 0, "mavproxy_drone_total_msgs_received": 0,
                      "mavproxy_drone_msg_type_counts": {},
                      "mavproxy_drone_heartbeat_interval_ms": 0.0,
                       "mavproxy_drone_heartbeat_loss_count": 0, "mavproxy_drone_seq_gap_count": 0,
                        "mavproxy_drone_cmd_sent_count": 0, "mavproxy_drone_cmd_ack_received_count": 0,
                         "mavproxy_drone_cmd_ack_latency_avg_ms": 0.0, "mavproxy_drone_cmd_ack_latency_p95_ms": 0.0,
                          "mavproxy_drone_stream_rate_hz": 0.0,
                                                    "mavproxy_gcs_total_msgs_received": 0,
                                                     "mavproxy_gcs_seq_gap_count": 0,
                                "mavlink_sysid": 0, "mavlink_compid": 0, "mavlink_protocol_version": 2,
                                 "mavlink_packet_crc_error_count": 0, "mavlink_decode_error_count": 0,
                                  "mavlink_msg_drop_count": 0, "mavlink_out_of_order_count": 0,
                                                                     "mavlink_duplicate_count": 0, "mavlink_message_latency_avg_ms": 0.0,
                                    "cpu_usage_avg_percent": 0.0, "cpu_usage_peak_percent": 0.0,
                                     "cpu_freq_mhz": 0.0, "memory_rss_mb": 0.0, "memory_vms_mb": 0.0,
                                      "thread_count": 0, "temperature_c": 0.0,
                                       "power_sensor_type": "none", "power_sampling_rate_hz": 0.0,
                                                                                "power_avg_w": 0.0, "power_peak_w": 0.0,
                                                                                 "energy_total_j": 0.0, "energy_per_handshake_j": 0.0,
                                                                                    "log_sample_count": 0, "metrics_sampling_rate_hz": 0.0,
                                           "expected_samples": 0, "collected_samples": 0, "lost_samples": 0,
                                            "success_rate_percent": 0.0, "benchmark_pass_fail": "FAIL"
            })
            
            results.append(CanonicalMetrics(**flat))
        except Exception as e:
            logger.warning(f"Row error: {e}")
            continue
            
    return results
