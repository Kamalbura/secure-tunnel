#!/usr/bin/env python3
"""
Comprehensive Metrics Aggregator
core/metrics_aggregator.py

Aggregates metrics from all collectors into the ComprehensiveSuiteMetrics schema.
Provides APIs for both GCS and Drone sides.

Usage:
    from core.metrics_aggregator import MetricsAggregator
    
    agg = MetricsAggregator(role="drone")
    agg.start_suite("cs-mlkem512-aesgcm-falcon512")
    # ... run benchmark ...
    metrics = agg.finalize_suite()
"""

import os
import sys
import time
import json
import socket
import platform
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from core.metrics_schema import (
    ComprehensiveSuiteMetrics,
    RunContextMetrics,
    SuiteCryptoIdentity,
    SuiteLifecycleTimeline,
    HandshakeMetrics,
    CryptoPrimitiveBreakdown,
    RekeyMetrics,
    DataPlaneMetrics,
    LatencyJitterMetrics,
    MavProxyDroneMetrics,
    MavProxyGcsMetrics,
    MavLinkIntegrityMetrics,
    FlightControllerTelemetry,
    ControlPlaneMetrics,
    SystemResourcesDrone,
    SystemResourcesGcs,
    PowerEnergyMetrics,
    ObservabilityMetrics,
    ValidationMetrics,
)

from core.metrics_collectors import (
    EnvironmentCollector,
    SystemCollector,
    PowerCollector,
    NetworkCollector,
    LatencyTracker,
)

# Import MAVLink collector (optional)
try:
    from core.mavlink_collector import MavLinkMetricsCollector
    HAS_MAVLINK_COLLECTOR = True
except ImportError:
    HAS_MAVLINK_COLLECTOR = False
    MavLinkMetricsCollector = None


class MetricsAggregator:
    """
    Aggregates metrics from multiple collectors into ComprehensiveSuiteMetrics.
    
    Designed to be instantiated on both GCS and Drone sides, with role-specific
    collection logic.
    """
    
    def __init__(self, role: str = "auto", output_dir: str = None):
        """
        Initialize the aggregator.
        
        Args:
            role: "gcs", "drone", or "auto" (detect from platform)
            output_dir: Directory for output files
        """
        self.role = role if role != "auto" else self._detect_role()
        
        # Output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).parent.parent / "logs" / "comprehensive_metrics"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize collectors
        self.env_collector = EnvironmentCollector()
        self.system_collector = SystemCollector()
        self.network_collector = NetworkCollector()
        self.latency_tracker = LatencyTracker()
        
        # Power collector (drone only)
        if self.role == "drone":
            self.power_collector = PowerCollector(backend="auto")
        else:
            self.power_collector = None
        
        # MAVLink collector (both sides)
        if HAS_MAVLINK_COLLECTOR:
            self.mavlink_collector = MavLinkMetricsCollector(role=self.role)
        else:
            self.mavlink_collector = None
        
        # Current metrics object
        self._current_metrics: Optional[ComprehensiveSuiteMetrics] = None
        self._run_id: str = ""
        self._suite_index: int = 0
        
        # Background collection
        self._collecting = False
        self._collect_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._system_samples: List[Dict[str, Any]] = []
        
        # Callbacks for external data
        self._proxy_metrics_callback: Optional[Callable[[], Dict[str, Any]]] = None
        self._mavlink_metrics_callback: Optional[Callable[[], Dict[str, Any]]] = None
    
    def _detect_role(self) -> str:
        """Detect role from platform."""
        machine = platform.machine().lower()
        if "arm" in machine or "aarch" in machine:
            return "drone"
        return "gcs"
    
    def set_run_id(self, run_id: str):
        """Set the run ID for this benchmark session."""
        self._run_id = run_id
    
    def register_proxy_callback(self, callback: Callable[[], Dict[str, Any]]):
        """Register callback to get proxy metrics."""
        self._proxy_metrics_callback = callback
    
    def register_mavlink_callback(self, callback: Callable[[], Dict[str, Any]]):
        """Register callback to get MAVLink metrics."""
        self._mavlink_metrics_callback = callback
    
    def start_suite(self, suite_id: str, suite_config: Dict[str, Any] = None) -> ComprehensiveSuiteMetrics:
        """
        Start collecting metrics for a new suite.
        
        Args:
            suite_id: The cipher suite identifier
            suite_config: Optional suite configuration from core.suites
        
        Returns:
            The metrics object being populated
        """
        # Create new metrics object
        self._current_metrics = ComprehensiveSuiteMetrics()
        m = self._current_metrics
        
        # A. Run & Context
        env = self.env_collector.collect()
        m.run_context.run_id = self._run_id
        m.run_context.suite_id = suite_id
        m.run_context.suite_index = self._suite_index
        m.run_context.git_commit_hash = env.get("git_commit", "")
        m.run_context.git_dirty_flag = env.get("git_dirty", False)
        
        if self.role == "gcs":
            m.run_context.gcs_hostname = env.get("hostname", "")
            m.run_context.gcs_ip = self.env_collector.get_ip_address()
            m.run_context.python_env_gcs = env.get("conda_env", "") or env.get("virtual_env", "")
            m.run_context.kernel_version_gcs = env.get("kernel_version", "")
        else:
            m.run_context.drone_hostname = env.get("hostname", "")
            m.run_context.drone_ip = self.env_collector.get_ip_address()
            m.run_context.python_env_drone = env.get("conda_env", "") or env.get("virtual_env", "")
            m.run_context.kernel_version_drone = env.get("kernel_version", "")
        
        m.run_context.liboqs_version = env.get("liboqs_version", "")
        m.run_context.run_start_time_wall = datetime.now(timezone.utc).isoformat()
        m.run_context.run_start_time_mono = time.monotonic()
        
        # B. Suite Crypto Identity (from config)
        if suite_config:
            m.crypto_identity.kem_algorithm = suite_config.get("kem_name", "")
            m.crypto_identity.kem_nist_level = suite_config.get("nist_level", "")
            m.crypto_identity.sig_algorithm = suite_config.get("sig_name", "")
            m.crypto_identity.sig_nist_level = suite_config.get("nist_level", "")
            m.crypto_identity.aead_algorithm = suite_config.get("aead", "")
            m.crypto_identity.suite_security_level = suite_config.get("nist_level", "")
            
            # Parse family from algorithm name
            kem_name = suite_config.get("kem_name", "")
            if "ML-KEM" in kem_name:
                m.crypto_identity.kem_family = "ML-KEM"
            elif "HQC" in kem_name:
                m.crypto_identity.kem_family = "HQC"
            elif "McEliece" in kem_name:
                m.crypto_identity.kem_family = "Classic-McEliece"
            
            sig_name = suite_config.get("sig_name", "")
            if "Falcon" in sig_name:
                m.crypto_identity.sig_family = "Falcon"
            elif "ML-DSA" in sig_name or "Dilithium" in sig_name:
                m.crypto_identity.sig_family = "ML-DSA"
            elif "SPHINCS" in sig_name:
                m.crypto_identity.sig_family = "SPHINCS+"
        
        # C. Lifecycle - mark selection time
        m.lifecycle.suite_selected_time = time.monotonic()
        
        # Start background collection
        self._start_background_collection()
        
        # Start power sampling (drone only)
        if self.power_collector and self.power_collector.backend != "none":
            self.power_collector.start_sampling(rate_hz=1000.0)
        
        # Start MAVLink sniffing
        if self.mavlink_collector:
            # GCS sniffs on 14552 (MAVProxy telemetry output duplicate)
            # Drone sniffs on 47005 (MAVProxy secondary output for sniffing)
            # NOTE: Drone proxy binds 47003, so we use separate 47005 to avoid conflict
            sniff_port = 14552 if self.role == "gcs" else 47005
            try:
                self.mavlink_collector.start_sniffing(port=sniff_port)
            except Exception:
                pass  # Port may already be in use
        
        self._suite_index += 1
        return m
    
    def record_handshake_start(self):
        """Mark handshake start time."""
        if self._current_metrics:
            now = time.monotonic()
            if self.role == "gcs":
                self._current_metrics.handshake.handshake_start_time_gcs = now
            else:
                self._current_metrics.handshake.handshake_start_time_drone = now
    
    def record_handshake_end(self, success: bool = True, failure_reason: str = ""):
        """Mark handshake end and record status."""
        if self._current_metrics:
            now = time.monotonic()
            h = self._current_metrics.handshake
            
            if self.role == "gcs":
                h.handshake_end_time_gcs = now
                if h.handshake_start_time_gcs > 0:
                    h.handshake_total_duration_ms = (now - h.handshake_start_time_gcs) * 1000
            else:
                h.handshake_end_time_drone = now
                if h.handshake_start_time_drone > 0:
                    h.handshake_total_duration_ms = (now - h.handshake_start_time_drone) * 1000
            
            h.handshake_success = success
            h.handshake_failure_reason = failure_reason
            
            # Mark lifecycle activation
            self._current_metrics.lifecycle.suite_activated_time = now
    
    def record_crypto_primitives(self, primitives: Dict[str, Any]):
        """
        Record cryptographic primitive timing.
        
        Expected keys:
            - kem_keygen_ns, kem_encaps_ns, kem_decaps_ns
            - sig_sign_ns, sig_verify_ns
            - pub_key_size_bytes, ciphertext_size_bytes, sig_size_bytes
        """
        if not self._current_metrics:
            return
        
        cp = self._current_metrics.crypto_primitives
        
        # Timing in milliseconds
        if "kem_keygen_ns" in primitives:
            cp.kem_keygen_ns = primitives["kem_keygen_ns"]
            cp.kem_keygen_time_ms = primitives["kem_keygen_ns"] / 1_000_000
        if "kem_encaps_ns" in primitives:
            cp.kem_encaps_ns = primitives["kem_encaps_ns"]
            cp.kem_encapsulation_time_ms = primitives["kem_encaps_ns"] / 1_000_000
        if "kem_decaps_ns" in primitives:
            cp.kem_decaps_ns = primitives["kem_decaps_ns"]
            cp.kem_decapsulation_time_ms = primitives["kem_decaps_ns"] / 1_000_000
        if "sig_sign_ns" in primitives:
            cp.sig_sign_ns = primitives["sig_sign_ns"]
            cp.signature_sign_time_ms = primitives["sig_sign_ns"] / 1_000_000
        if "sig_verify_ns" in primitives:
            cp.sig_verify_ns = primitives["sig_verify_ns"]
            cp.signature_verify_time_ms = primitives["sig_verify_ns"] / 1_000_000
        
        # Also accept ms values directly (map to correct schema field names)
        ms_field_map = {
            "kem_keygen_ms": "kem_keygen_time_ms",
            "kem_encaps_ms": "kem_encapsulation_time_ms",
            "kem_decaps_ms": "kem_decapsulation_time_ms",
            "kem_decap_ms": "kem_decapsulation_time_ms",  # alternate name
            "sig_sign_ms": "signature_sign_time_ms",
            "sig_verify_ms": "signature_verify_time_ms",
        }
        for src_key, dst_field in ms_field_map.items():
            if src_key in primitives and primitives[src_key]:
                setattr(cp, dst_field, float(primitives[src_key]))
        
        # Artifact sizes
        cp.pub_key_size_bytes = primitives.get("pub_key_size_bytes", 0)
        cp.ciphertext_size_bytes = primitives.get("ciphertext_size_bytes", 0)
        cp.sig_size_bytes = primitives.get("sig_size_bytes", 0)
        cp.shared_secret_size_bytes = primitives.get("shared_secret_size_bytes", 0)
        
        # Calculate total
        cp.total_crypto_time_ms = (
            cp.kem_keygen_time_ms + 
            cp.kem_encapsulation_time_ms + 
            cp.kem_decapsulation_time_ms +
            cp.signature_sign_time_ms +
            cp.signature_verify_time_ms
        )
    
    def record_data_plane_metrics(self, counters: Dict[str, Any]):
        """
        Record data plane (proxy) metrics.
        
        Expected keys from proxy counters:
            - ptx_in, ptx_out, enc_in, enc_out
            - drop_replay, drop_auth, drop_header
            - bytes_in, bytes_out
            - primitive_metrics (nested AEAD timing)
        """
        if not self._current_metrics:
            return
        
        dp = self._current_metrics.data_plane
        
        dp.ptx_in = counters.get("ptx_in", 0)
        dp.ptx_out = counters.get("ptx_out", 0)
        dp.enc_in = counters.get("enc_in", 0)
        dp.enc_out = counters.get("enc_out", 0)
        dp.drop_replay = counters.get("drop_replay", 0)
        dp.drop_auth = counters.get("drop_auth", 0)
        dp.drop_header = counters.get("drop_header", 0)
        
        dp.packets_sent = dp.enc_out
        dp.packets_received = dp.enc_in
        dp.packets_dropped = dp.drop_replay + dp.drop_auth + dp.drop_header
        
        # Calculate ratios
        if dp.packets_sent > 0:
            dp.packet_loss_ratio = dp.packets_dropped / dp.packets_sent
            dp.packet_delivery_ratio = 1.0 - dp.packet_loss_ratio
        
        # Byte counters
        dp.bytes_sent = counters.get("bytes_out", 0)
        dp.bytes_received = counters.get("bytes_in", 0)
        
        # AEAD timing from primitive_metrics (nested structure)
        prim = counters.get("primitive_metrics", {})
        enc_stats = prim.get("aead_encrypt", {})
        dec_stats = prim.get("aead_decrypt_ok", {})
        
        if enc_stats.get("count", 0) > 0:
            dp.aead_encrypt_count = enc_stats["count"]
            dp.aead_encrypt_avg_ns = enc_stats.get("total_ns", 0) // enc_stats["count"]
        if dec_stats.get("count", 0) > 0:
            dp.aead_decrypt_count = dec_stats["count"]
            dp.aead_decrypt_avg_ns = dec_stats.get("total_ns", 0) // dec_stats["count"]
    
    def record_latency_sample(self, latency_ms: float):
        """Record a latency sample."""
        self.latency_tracker.record(latency_ms)
    
    def record_traffic_start(self):
        """Mark start of data plane traffic."""
        if self._current_metrics:
            self._current_metrics.lifecycle.suite_traffic_start_time = time.monotonic()
    
    def record_traffic_end(self):
        """Mark end of data plane traffic."""
        if self._current_metrics:
            self._current_metrics.lifecycle.suite_traffic_end_time = time.monotonic()
    
    def _start_background_collection(self):
        """Start background system metrics collection."""
        if self._collecting:
            return
        
        self._collecting = True
        self._system_samples = []
        self._stop_event.clear()
        
        def collect_loop():
            while not self._stop_event.is_set():
                sample = self.system_collector.collect()
                sample["mono_time"] = time.monotonic()
                self._system_samples.append(sample)
                time.sleep(0.5)  # 2 Hz sampling
        
        self._collect_thread = threading.Thread(target=collect_loop, daemon=True)
        self._collect_thread.start()
    
    def _stop_background_collection(self):
        """Stop background collection."""
        if not self._collecting:
            return
        
        self._stop_event.set()
        if self._collect_thread:
            self._collect_thread.join(timeout=1.0)
        self._collecting = False
    
    def finalize_suite(self, merge_from: Dict[str, Any] = None) -> ComprehensiveSuiteMetrics:
        """
        Finalize metrics collection for current suite.
        
        Args:
            merge_from: Optional dict with additional metrics to merge
                        (e.g., from peer side via control channel)
        
        Returns:
            Completed metrics object
        """
        if not self._current_metrics:
            return ComprehensiveSuiteMetrics()
        
        m = self._current_metrics
        
        # Stop background collection
        self._stop_background_collection()
        
        # Stop power sampling
        power_samples = []
        if self.power_collector:
            power_samples = self.power_collector.stop_sampling()
        
        # Finalize timing
        now = time.monotonic()
        m.run_context.run_end_time_wall = datetime.now(timezone.utc).isoformat()
        m.run_context.run_end_time_mono = now
        
        # C. Lifecycle finalization
        m.lifecycle.suite_deactivated_time = now
        m.lifecycle.suite_total_duration_ms = (now - m.lifecycle.suite_selected_time) * 1000
        if m.lifecycle.suite_activated_time > 0:
            m.lifecycle.suite_active_duration_ms = (now - m.lifecycle.suite_activated_time) * 1000
        
        # H. Latency stats
        lat_stats = self.latency_tracker.get_stats()
        m.latency_jitter.one_way_latency_avg_ms = lat_stats["avg_ms"]
        m.latency_jitter.one_way_latency_p50_ms = lat_stats["p50_ms"]
        m.latency_jitter.one_way_latency_p95_ms = lat_stats["p95_ms"]
        m.latency_jitter.one_way_latency_max_ms = lat_stats["max_ms"]
        self.latency_tracker.clear()
        
        # N/O. System resources
        if self._system_samples:
            cpu_samples = [s["cpu_percent"] for s in self._system_samples if "cpu_percent" in s]
            
            if self.role == "drone":
                sys_m = m.system_drone
            else:
                sys_m = m.system_gcs
            
            if cpu_samples:
                sys_m.cpu_usage_avg_percent = sum(cpu_samples) / len(cpu_samples)
                sys_m.cpu_usage_peak_percent = max(cpu_samples)
            
            # Use last sample for other metrics
            last = self._system_samples[-1]
            sys_m.cpu_freq_mhz = last.get("cpu_freq_mhz", 0)
            sys_m.memory_rss_mb = last.get("memory_rss_mb", 0)
            sys_m.memory_vms_mb = last.get("memory_vms_mb", 0)
            sys_m.thread_count = last.get("thread_count", 0)
            
            if self.role == "drone":
                sys_m.temperature_c = last.get("temperature_c", 0)
                sys_m.load_avg_1m = last.get("load_avg_1m", 0)
                sys_m.load_avg_5m = last.get("load_avg_5m", 0)
                sys_m.load_avg_15m = last.get("load_avg_15m", 0)
        
        # P. Power & Energy
        if power_samples:
            energy_stats = self.power_collector.get_energy_stats(power_samples)
            m.power_energy.power_sensor_type = self.power_collector.backend
            m.power_energy.power_sampling_rate_hz = 1000.0
            m.power_energy.power_avg_w = energy_stats["power_avg_w"]
            m.power_energy.power_peak_w = energy_stats["power_peak_w"]
            m.power_energy.energy_total_j = energy_stats["energy_total_j"]
            
            # Calculate per-handshake energy
            if m.handshake.handshake_total_duration_ms > 0:
                hs_duration_s = m.handshake.handshake_total_duration_ms / 1000.0
                m.power_energy.energy_per_handshake_j = m.power_energy.power_avg_w * hs_duration_s
        
        # I/J. MAVLink metrics
        if self.mavlink_collector:
            try:
                mavlink_metrics = self.mavlink_collector.stop()
                
                if self.role == "gcs":
                    self.mavlink_collector.populate_schema_metrics(m.mavproxy_gcs, "gcs")
                else:
                    self.mavlink_collector.populate_schema_metrics(m.mavproxy_drone, "drone")
                
                # K. MAVLink integrity
                self.mavlink_collector.populate_mavlink_integrity(m.mavlink_integrity)
            except Exception:
                pass
        
        # Q. Observability
        m.observability.log_sample_count = len(self._system_samples)
        m.observability.metrics_sampling_rate_hz = 2.0
        m.observability.collection_start_time = m.run_context.run_start_time_mono
        m.observability.collection_end_time = now
        m.observability.collection_duration_ms = (now - m.run_context.run_start_time_mono) * 1000
        
        # R. Validation
        m.validation.expected_samples = int(m.observability.collection_duration_ms / 500)  # 2 Hz
        m.validation.collected_samples = len(self._system_samples)
        m.validation.lost_samples = max(0, m.validation.expected_samples - m.validation.collected_samples)
        m.validation.success_rate_percent = 100.0 if m.handshake.handshake_success else 0.0
        m.validation.benchmark_pass_fail = "PASS" if m.handshake.handshake_success else "FAIL"
        
        # Merge additional data from peer
        if merge_from:
            self._merge_peer_data(m, merge_from)
        
        # Save to file
        self._save_metrics(m)
        
        # Clear for next suite
        self._current_metrics = None
        self._system_samples = []
        
        return m
    
    def _merge_peer_data(self, m: ComprehensiveSuiteMetrics, peer_data: Dict[str, Any]):
        """Merge metrics from peer side."""
        # Merge run context
        if "drone_hostname" in peer_data:
            m.run_context.drone_hostname = peer_data["drone_hostname"]
        if "drone_ip" in peer_data:
            m.run_context.drone_ip = peer_data["drone_ip"]
        if "gcs_hostname" in peer_data:
            m.run_context.gcs_hostname = peer_data["gcs_hostname"]
        if "gcs_ip" in peer_data:
            m.run_context.gcs_ip = peer_data["gcs_ip"]
        
        # Merge handshake timing
        if "handshake_start_time_drone" in peer_data:
            m.handshake.handshake_start_time_drone = peer_data["handshake_start_time_drone"]
        if "handshake_end_time_drone" in peer_data:
            m.handshake.handshake_end_time_drone = peer_data["handshake_end_time_drone"]
        
        # Merge system metrics
        if "system_drone" in peer_data:
            for k, v in peer_data["system_drone"].items():
                if hasattr(m.system_drone, k):
                    setattr(m.system_drone, k, v)
        
        # Merge power metrics
        if "power_energy" in peer_data:
            for k, v in peer_data["power_energy"].items():
                if hasattr(m.power_energy, k):
                    setattr(m.power_energy, k, v)
    
    def _save_metrics(self, m: ComprehensiveSuiteMetrics):
        """Save metrics to JSON file."""
        filename = f"{m.run_context.run_id}_{m.run_context.suite_id}_{self.role}.json"
        filepath = self.output_dir / filename
        
        try:
            m.save_json(str(filepath))
        except Exception as e:
            print(f"Failed to save metrics: {e}")
    
    def get_current_metrics(self) -> Optional[ComprehensiveSuiteMetrics]:
        """Get current metrics object (if active)."""
        return self._current_metrics
    
    def get_exportable_data(self) -> Dict[str, Any]:
        """
        Get current metrics as dict for sending to peer.
        
        Returns subset of metrics relevant to current role.
        """
        if not self._current_metrics:
            return {}
        
        m = self._current_metrics
        
        if self.role == "drone":
            return {
                "drone_hostname": m.run_context.drone_hostname,
                "drone_ip": m.run_context.drone_ip,
                "python_env_drone": m.run_context.python_env_drone,
                "kernel_version_drone": m.run_context.kernel_version_drone,
                "handshake_start_time_drone": m.handshake.handshake_start_time_drone,
                "handshake_end_time_drone": m.handshake.handshake_end_time_drone,
                "system_drone": {
                    "cpu_usage_avg_percent": m.system_drone.cpu_usage_avg_percent,
                    "cpu_usage_peak_percent": m.system_drone.cpu_usage_peak_percent,
                    "memory_rss_mb": m.system_drone.memory_rss_mb,
                    "temperature_c": m.system_drone.temperature_c,
                },
                "power_energy": {
                    "power_sensor_type": m.power_energy.power_sensor_type,
                    "power_avg_w": m.power_energy.power_avg_w,
                    "power_peak_w": m.power_energy.power_peak_w,
                    "energy_total_j": m.power_energy.energy_total_j,
                    "energy_per_handshake_j": m.power_energy.energy_per_handshake_j,
                },
            }
        else:
            return {
                "gcs_hostname": m.run_context.gcs_hostname,
                "gcs_ip": m.run_context.gcs_ip,
                "python_env_gcs": m.run_context.python_env_gcs,
                "kernel_version_gcs": m.run_context.kernel_version_gcs,
                "handshake_start_time_gcs": m.handshake.handshake_start_time_gcs,
                "handshake_end_time_gcs": m.handshake.handshake_end_time_gcs,
                "system_gcs": {
                    "cpu_usage_avg_percent": m.system_gcs.cpu_usage_avg_percent,
                    "cpu_usage_peak_percent": m.system_gcs.cpu_usage_peak_percent,
                    "memory_rss_mb": m.system_gcs.memory_rss_mb,
                },
            }
    
    def save_suite_metrics(self, metrics: ComprehensiveSuiteMetrics = None) -> Optional[str]:
        """
        Save suite metrics to JSON file.
        
        Args:
            metrics: ComprehensiveSuiteMetrics to save (or use current if None)
        
        Returns:
            Path to saved file, or None on failure
        """
        m = metrics or self._current_metrics
        if not m:
            return None
        
        try:
            from dataclasses import asdict
            
            # Create filename
            suite_id = m.run_context.suite_id or "unknown"
            run_id = self._run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{suite_id}_{run_id}_{self.role}.json"
            output_path = self.output_dir / filename
            
            # Convert to dict
            data = asdict(m)
            
            # Write to file
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            
            return str(output_path)
        except Exception as e:
            print(f"Failed to save suite metrics: {e}")
            return None


# =============================================================================
# MAIN - Test aggregator
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("METRICS AGGREGATOR TEST")
    print("=" * 60)
    
    # Create aggregator
    agg = MetricsAggregator(role="auto")
    print(f"Detected role: {agg.role}")
    
    # Simulate benchmark
    agg.set_run_id("test_20260112_120000")
    
    # Start suite
    suite_config = {
        "kem_name": "ML-KEM-512",
        "sig_name": "Falcon-512",
        "aead": "AES-256-GCM",
        "nist_level": "L1",
    }
    
    print("\nStarting suite benchmark...")
    metrics = agg.start_suite("cs-mlkem512-aesgcm-falcon512", suite_config)
    
    # Simulate handshake
    agg.record_handshake_start()
    time.sleep(0.1)  # Simulate 100ms handshake
    agg.record_handshake_end(success=True)
    
    # Record crypto primitives
    agg.record_crypto_primitives({
        "kem_encaps_ns": 500_000,  # 0.5ms
        "sig_verify_ns": 1_200_000,  # 1.2ms
        "pub_key_size_bytes": 800,
        "ciphertext_size_bytes": 768,
        "sig_size_bytes": 666,
    })
    
    # Simulate traffic
    agg.record_traffic_start()
    time.sleep(0.5)  # Simulate 500ms of traffic
    agg.record_traffic_end()
    
    # Record data plane metrics
    agg.record_data_plane_metrics({
        "ptx_in": 100,
        "ptx_out": 100,
        "enc_in": 100,
        "enc_out": 100,
        "drop_replay": 0,
        "drop_auth": 0,
    })
    
    # Finalize
    print("\nFinalizing metrics...")
    final_metrics = agg.finalize_suite()
    
    # Print summary
    print("\n--- METRICS SUMMARY ---")
    print(f"Suite: {final_metrics.run_context.suite_id}")
    print(f"Handshake success: {final_metrics.handshake.handshake_success}")
    print(f"Handshake duration: {final_metrics.handshake.handshake_total_duration_ms:.2f} ms")
    print(f"CPU avg: {final_metrics.system_drone.cpu_usage_avg_percent:.1f}%" if agg.role == "drone" 
          else f"CPU avg: {final_metrics.system_gcs.cpu_usage_avg_percent:.1f}%")
    print(f"Total duration: {final_metrics.lifecycle.suite_total_duration_ms:.2f} ms")
    
    print(f"\nMetrics saved to: {agg.output_dir}")
    print("\nTest completed successfully!")
