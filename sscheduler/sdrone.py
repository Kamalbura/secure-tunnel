#!/usr/bin/env python3
"""
Simplified Drone Scheduler (CONTROLLER) - sscheduler/sdrone.py

REVERSED CONTROL: Drone is the controller, GCS follows.
- Drone decides suite order, timing, rekey
- Drone sends commands to GCS
- Drone runs echo server (receives traffic from GCS)
- Drone starts its proxy first, then tells GCS to start

Usage:
    python -m sscheduler.sdrone [options]

Environment:
    DRONE_HOST          Drone IP (default: from config)
    GCS_HOST            GCS IP (default: from config)
    GCS_CONTROL_HOST    GCS control server IP (default: GCS_HOST)
"""

import os
import sys
import time
import json
import socket
import signal
import argparse
import threading
import subprocess
import logging
import atexit
from pathlib import Path
from collections import deque
from datetime import datetime, timezone
import statistics
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG
from sscheduler.telemetry_window import TelemetryWindow
from core.suites import get_suite, list_suites
from core.process import ManagedProcess
from tools.mavproxy_manager import MavProxyManager
from sscheduler.policy import (
    LinearLoopPolicy, 
    RandomPolicy, 
    ManualOverridePolicy,
    TelemetryAwarePolicyV1,
    DecisionInput,
    PolicyAction,
    PolicyOutput,
    get_suite_tier,
    COOLDOWN_SWITCH_S,
    COOLDOWN_REKEY_S,
    COOLDOWN_DOWNGRADE_S,
)

# Extract config values (use CONFIG as single source of truth)
DRONE_HOST = str(CONFIG.get("DRONE_HOST"))
GCS_HOST = str(CONFIG.get("GCS_HOST"))
DRONE_PLAIN_RX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_RX", 47004))
DRONE_PLAIN_TX_PORT = int(CONFIG.get("DRONE_PLAINTEXT_TX", 47003))
GCS_TELEMETRY_PORT = int(CONFIG.get("GCS_TELEMETRY_PORT", 52080))

# Control endpoint for GCS: use configured GCS_HOST and GCS_CONTROL_PORT
GCS_CONTROL_HOST = str(CONFIG.get("GCS_HOST"))
GCS_CONTROL_PORT = int(CONFIG.get("GCS_CONTROL_PORT", 48080))

# Derived internal proxy control port to avoid collisions
PROXY_INTERNAL_CONTROL_PORT = GCS_CONTROL_PORT + 100

DEFAULT_SUITE = "cs-mlkem768-aesgcm-mldsa65"
SECRETS_DIR = Path(__file__).parent.parent / "secrets" / "matrix"

# Traffic settings (for telling GCS how long to run)
DEFAULT_DURATION = 10.0  # seconds per suite
DEFAULT_RATE_MBPS = 110.0
PAYLOAD_SIZE = 1200

# --------------------
# Local editable configuration (edit here, no CLI args needed)
# --------------------
LOCAL_DURATION = None  # override DEFAULT_DURATION if set, e.g. 10.0
LOCAL_RATE_MBPS = None  # override DEFAULT_RATE_MBPS if set, e.g. 110.0
LOCAL_MAX_SUITES = None  # limit suites run, e.g. 2
LOCAL_SUITES = None  # list of suite names to run, or None

# Get all suites (list_suites returns dict, convert to list of dicts)
_suites_dict = list_suites()
SUITES = [{"name": k, **v} for k, v in _suites_dict.items()]

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs" / "sscheduler" / "drone"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Logging
# ============================================================

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [sdrone-ctrl] {msg}", flush=True)

# ============================================================
# Telemetry Listener & Decision Context
# ============================================================

class TelemetryListener:
    """Receives telemetry updates from GCS via UDP"""
    MAX_PACKET_SIZE = 8192
    SCHEMA = "uav.pqc.telemetry.v1"
    HISTORY_LEN = 50 # 5 seconds at 10Hz

    def __init__(self, port: int, allowed_ip: str = None):
        self.port = port
        self.allowed_ip = allowed_ip
        self.sock = None
        self.running = False
        self.thread = None
        self.latest_data = {}
        self.last_update = 0
        self.last_update_mono = 0.0
        self.last_sender = None
        # History stores (mono_time, packet_dict)
        self.history = deque(maxlen=self.HISTORY_LEN)
        self.lock = threading.Lock()
        
        self.log_file = LOGS_DIR / "drone_telemetry_rx.jsonl"
        # Full packet dump for forensic inspection (keeps original schema payloads)
        self.full_log_file = LOGS_DIR / "drone_telemetry_full.jsonl"
        # Sliding window helper (monotonic-time based)
        self.window = TelemetryWindow(window_s=5.0)

    def start(self):
        if self.running:
            return
            
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.settimeout(1.0)
        
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        log(f"Telemetry listener started on port {self.port} (allowed_ip={self.allowed_ip})")

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                
                # Bounded size check
                if len(data) > self.MAX_PACKET_SIZE:
                    continue

                # IP Allow-list check
                if self.allowed_ip and addr[0] != self.allowed_ip:
                    # log(f"Dropped telemetry from unauthorized IP: {addr[0]}")
                    continue
                
                try:
                    packet = json.loads(data.decode('utf-8'))
                    
                    # Schema Validation
                    if packet.get("schema") != self.SCHEMA:
                        continue
                    if packet.get("schema_ver") != 1:
                        continue

                    now_mono = time.monotonic()
                    with self.lock:
                        self.latest_data = packet
                        self.last_update = time.time()
                        self.last_update_mono = now_mono
                        self.last_sender = addr[0]
                        self.history.append((now_mono, packet))
                        # Feed sliding window
                        try:
                            self.window.add(now_mono, packet)
                        except Exception:
                            pass
                    
                    # Best-effort logging
                    self._write_log(now_mono, addr[0], packet)

                except json.JSONDecodeError:
                    pass
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log(f"Telemetry error: {e}")

    def _write_log(self, now_mono, sender_ip, packet):
        try:
            # Calculate simple stats for log
            rx_pps = 0
            if len(self.history) > 1:
                # approximate pps from history duration
                duration = self.history[-1][0] - self.history[0][0]
                if duration > 0:
                    rx_pps = len(self.history) / duration
            
            seq = packet.get("seq", 0)
            
            cpu_pct = 0
            if "metrics" in packet and "sys" in packet["metrics"]:
                cpu_pct = packet["metrics"]["sys"].get("cpu_pct", 0)

            entry = {
                "recv_mono_ms": now_mono * 1000.0,
                "sender_ip": sender_ip,
                "seq": seq,
                "summary": {
                    "rx_pps": round(rx_pps, 1),
                    "silence_ms": 0,
                    "cpu_pct": cpu_pct
                }
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            # Also write the raw full telemetry packet (preserve original schema)
            try:
                with open(self.full_log_file, "a", encoding="utf-8") as ff:
                    ff.write(json.dumps(packet) + "\n")
            except Exception:
                # Non-fatal: keep best-effort
                pass
        except Exception:
            pass

    def get_latest(self):
        with self.lock:
            return self.latest_data, self.last_update

    def get_age_ms(self):
        with self.lock:
            if self.last_update_mono == 0.0:
                return -1.0
            return (time.monotonic() - self.last_update_mono) * 1000.0

    def get_sender_ip(self):
        with self.lock:
            return self.last_sender
            
    def get_history_snapshot(self):
        with self.lock:
            return list(self.history)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.sock:
            self.sock.close()

class DecisionContext:
    """Aggregates system state for policy decisions"""
    def __init__(self, telemetry: TelemetryListener, suites: List[str]):
        self.telemetry = telemetry
        self.suites = suites
        # cooldown after suite switch (mono seconds)
        self._last_switch_mono = 0.0
        self._cooldown_until_mono = 0.0
        self._current_suite = ""
        self._local_epoch = 0
        self._armed_since_mono = 0.0
        
        # Telemetry-aware policy
        self._policy = TelemetryAwarePolicyV1(suites)

    def get_gcs_status(self):
        data, ts = self.telemetry.get_latest()
        age = time.time() - ts
        return data, age

    def get_summary(self) -> Dict[str, Any]:
        """Return windowed telemetry stats."""
        now = time.monotonic()
        summary = self.telemetry.window.summarize(now)
        last_seq = summary.get("last_seq", 0)

        return {
            "valid": summary.get("sample_count", 0) > 0,
            "telemetry_age_ms": summary.get("telemetry_age_ms", -1),
            "rx_pps_median": summary.get("rx_pps_median", 0.0),
            "gap_p95_ms": summary.get("gap_p95_ms", 0.0),
            "silence_max_ms": summary.get("silence_max_ms", 0.0),
            "jitter_ms": summary.get("jitter_ms", 0.0),
            "gcs_cpu_median": summary.get("gcs_cpu_median", 0.0),
            "gcs_cpu_p95": summary.get("gcs_cpu_p95", 0.0),
            "sample_count_window": summary.get("sample_count", 0),
            "telemetry_last_seq": last_seq,
            "confidence": summary.get("confidence", 0.0),
            "missing_seq_count": summary.get("missing_seq_count", 0),
            "out_of_order_count": summary.get("out_of_order_count", 0),
        }

    def record_suite_switch(self, suite_name: str, cooldown_s: float = COOLDOWN_SWITCH_S):
        """Record a suite switch event and set cooldown."""
        now_mono = time.monotonic()
        self._last_switch_mono = now_mono
        self._cooldown_until_mono = now_mono + cooldown_s
        self._current_suite = suite_name
        self._local_epoch += 1

    def build_decision_input(self, expected_suite: str) -> DecisionInput:
        """Build immutable DecisionInput from current state."""
        now = time.monotonic()
        now_ms = now * 1000.0
        
        summary = self.telemetry.window.summarize(now)
        flight_state = self.telemetry.window.get_flight_state()
        
        # Extract remote sync state from latest telemetry if available
        latest, _ = self.telemetry.get_latest()
        remote_suite = latest.get("active_suite") if latest else None
        remote_epoch = latest.get("epoch", 0) if latest else 0
        
        # MAVProxy/collector health - infer from telemetry presence
        mavproxy_alive = summary.get("sample_count", 0) > 0
        collector_alive = summary.get("telemetry_age_ms", -1) >= 0
        
        # Armed duration
        armed = flight_state.get("armed", False)
        armed_duration_s = 0.0
        if armed:
            if self._armed_since_mono == 0.0:
                self._armed_since_mono = now
            armed_duration_s = now - self._armed_since_mono
        else:
            self._armed_since_mono = 0.0
        
        return DecisionInput(
            mono_ms=now_ms,
            telemetry_valid=summary.get("sample_count", 0) > 0,
            telemetry_age_ms=summary.get("telemetry_age_ms", -1.0),
            sample_count=summary.get("sample_count", 0),
            rx_pps_median=summary.get("rx_pps_median", 0.0),
            gap_p95_ms=summary.get("gap_p95_ms", 0.0),
            silence_max_ms=summary.get("silence_max_ms", 0.0),
            jitter_ms=summary.get("jitter_ms", 0.0),
            gcs_cpu_median=summary.get("gcs_cpu_median", 0.0),
            gcs_cpu_p95=summary.get("gcs_cpu_p95", 0.0),
            telemetry_last_seq=summary.get("last_seq", 0),
            mavproxy_alive=mavproxy_alive,
            collector_alive=collector_alive,
            heartbeat_age_ms=flight_state.get("heartbeat_age_ms", 0.0),
            failsafe_active=flight_state.get("failsafe", False),
            armed=armed,
            armed_duration_s=armed_duration_s,
            remote_suite=remote_suite,
            remote_epoch=remote_epoch,
            expected_suite=expected_suite,
            current_tier=get_suite_tier(expected_suite),
            local_epoch=self._local_epoch,
            last_switch_mono_ms=self._last_switch_mono * 1000.0,
            cooldown_until_mono_ms=self._cooldown_until_mono * 1000.0,
        )

    def evaluate_policy(self, expected_suite: str) -> PolicyOutput:
        """Evaluate the telemetry-aware policy and return output."""
        inp = self.build_decision_input(expected_suite)
        return self._policy.evaluate(inp)

    def decide(self, expected_suite: str) -> Dict[str, Any]:
        """Legacy decide() for backward compatibility - returns dict."""
        now = time.monotonic()
        s = self.get_summary()
        
        # Use new policy
        policy_out = self.evaluate_policy(expected_suite)

        result = {
            "schema": "uav.pqc.drone.decision_context.v1",
            "mono_ms": now * 1000.0,
            "suite_expected": expected_suite,
            "suite_tier": get_suite_tier(expected_suite),
            "local_epoch": self._local_epoch,
            "telemetry_last_seq": s.get("telemetry_last_seq", 0),
            "telemetry_age_ms": s.get("telemetry_age_ms"),
            "rx_pps_median": s.get("rx_pps_median"),
            "gap_p95_ms": s.get("gap_p95_ms"),
            "silence_max_ms": s.get("silence_max_ms"),
            "jitter_ms": s.get("jitter_ms"),
            "gcs_cpu_median": s.get("gcs_cpu_median"),
            "gcs_cpu_p95": s.get("gcs_cpu_p95"),
            "sample_count_window": s.get("sample_count_window"),
            "confidence": s.get("confidence", 0.0),
            "missing_seq": s.get("missing_seq_count", 0),
            "out_of_order": s.get("out_of_order_count", 0),
            # Policy output
            "policy_action": policy_out.action.value,
            "policy_target_suite": policy_out.target_suite,
            "policy_reasons": policy_out.reasons,
            "policy_confidence": policy_out.confidence,
            "cooldown_remaining_ms": policy_out.cooldown_remaining_ms,
        }

        return result

# ============================================================
# UDP Echo Server (drone receives traffic from GCS)
# ============================================================

class UdpEchoServer:
    """Echoes UDP packets: receives on DRONE_PLAIN_RX, sends back on DRONE_PLAIN_TX"""
    
    def __init__(self):
        self.rx_sock = None
        self.tx_sock = None
        self.running = False
        self.thread = None
        self.rx_count = 0
        self.tx_count = 0
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.lock = threading.Lock()
    
    def start(self):
        if self.running:
            return
        
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        self.rx_sock.bind((DRONE_HOST, DRONE_PLAIN_RX_PORT))
        self.rx_sock.settimeout(1.0)
        
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        
        self.running = True
        self.thread = threading.Thread(target=self._echo_loop, daemon=True)
        self.thread.start()
        
        log(f"Echo server listening on {DRONE_HOST}:{DRONE_PLAIN_RX_PORT}")
    
    def _echo_loop(self):
        while self.running:
            try:
                data, addr = self.rx_sock.recvfrom(65535)
                with self.lock:
                    self.rx_count += 1
                    self.rx_bytes += len(data)
                
                self.tx_sock.sendto(data, (DRONE_HOST, DRONE_PLAIN_TX_PORT))
                with self.lock:
                    self.tx_count += 1
                    self.tx_bytes += len(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log(f"Echo error: {e}")
    
    def get_stats(self):
        with self.lock:
            return {
                "rx_count": self.rx_count,
                "tx_count": self.tx_count,
                "rx_bytes": self.rx_bytes,
                "tx_bytes": self.tx_bytes,
            }
    
    def reset_stats(self):
        with self.lock:
            self.rx_count = 0
            self.tx_count = 0
            self.rx_bytes = 0
            self.tx_bytes = 0
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.rx_sock:
            self.rx_sock.close()
        if self.tx_sock:
            self.tx_sock.close()


# MavProxyManager imported from tools.mavproxy_manager

# ============================================================
# GCS Control Client (drone sends commands to GCS)
# ============================================================

def send_gcs_command(cmd: str, **params) -> dict:
    """Send command to GCS control server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect((GCS_CONTROL_HOST, GCS_CONTROL_PORT))
        
        request = {"cmd": cmd, **params}
        sock.sendall(json.dumps(request).encode() + b"\n")
        
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break
        
        sock.close()
        return json.loads(response.decode().strip())
    except Exception as e:
        return {"status": "error", "message": str(e)}

def wait_for_gcs(timeout: float = 30.0) -> bool:
    """Wait for GCS control server to be ready"""
    start = time.time()
    while time.time() - start < timeout:
        result = send_gcs_command("ping")
        if result.get("status") == "ok":
            return True
        time.sleep(0.5)
    return False

# ============================================================
# Drone Proxy Management
# ============================================================

class DroneProxyManager:
    """Manages drone proxy subprocess"""
    
    def __init__(self):
        self.managed_proc = None
        self.current_suite = None
    
    def start(self, suite_name: str) -> bool:
        """Start drone proxy with given suite"""
        if self.managed_proc and self.managed_proc.is_running():
            self.stop()
        
        suite = get_suite(suite_name)
        if not suite:
            log(f"Unknown suite: {suite_name}")
            return False
        
        secret_dir = SECRETS_DIR / suite_name
        peer_pubkey = secret_dir / "gcs_signing.pub"
        
        if not peer_pubkey.exists():
            log(f"Missing key: {peer_pubkey}")
            return False
        
        cmd = [
            sys.executable, "-m", "core.run_proxy", "drone",
            "--suite", suite_name,
            "--peer-pubkey-file", str(peer_pubkey),
            "--quiet",
            "--status-file", str(LOGS_DIR / "drone_status.json")
        ]

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = LOGS_DIR / f"drone_{suite_name}_{timestamp}.log"
        log(f"Launching: {' '.join(cmd)} (log: {log_path})")
        log_handle = open(log_path, "w", encoding="utf-8")
        
        self.managed_proc = ManagedProcess(
            cmd=cmd,
            name=f"proxy-{suite_name}",
            stdout=log_handle,
            stderr=subprocess.STDOUT
        )
        
        if self.managed_proc.start():
            self._last_log = log_path
            self.current_suite = suite_name
            time.sleep(3.0)
            if not self.managed_proc.is_running():
                log(f"Proxy exited early")
                return False
            return True
        return False
    
    def stop(self):
        """Stop drone proxy"""
        if self.managed_proc:
            self.managed_proc.stop()
            self.managed_proc = None
            self.current_suite = None
    
    def is_running(self) -> bool:
        return self.managed_proc is not None and self.managed_proc.is_running()

# ============================================================
# Suite Runner
# ============================================================

def run_suite(proxy: DroneProxyManager, mavproxy, 
              suite_name: str, duration: float, is_first: bool = False) -> dict:
    """Run a single suite test - drone controls the flow.
    
    NOTE: Even though drone is the controller, GCS proxy must start first
    because the TCP handshake requires GCS to listen and drone to connect.
    Drone controls WHEN to start, but GCS proxy goes up first.
    """
    
    result = {
        "suite": suite_name,
        "status": "unknown",
        "echo_rx": 0,
        "echo_tx": 0,
    }
    
    # Ensure mavproxy (application-layer relay) is available
    mav_running = False
    try:
        # Support either the manager object with is_running(), or a subprocess.Popen
        if hasattr(mavproxy, "is_running"):
            mav_running = bool(mavproxy.is_running())
        else:
            # treat mavproxy as subprocess-like
            mav_running = mavproxy is not None and getattr(mavproxy, "poll", lambda: None)() is None
    except Exception:
        mav_running = False
    
    if not is_first:
        # Rekey: tell GCS to prepare (stop its proxy)
        log("Preparing GCS for rekey...")
        resp = send_gcs_command("prepare_rekey")
        if resp.get("status") != "ok":
            log(f"GCS prepare_rekey failed: {resp}")
            result["status"] = "gcs_prepare_failed"
            return result
        
        # Stop our proxy too
        proxy.stop()
        time.sleep(0.5)
    
    # Tell GCS to start its proxy first (GCS listens, drone connects)
    log(f"Telling GCS to start proxy for {suite_name}...")
    resp = send_gcs_command("start_proxy", suite=suite_name)
    log(f"GCS start_proxy response: {resp}")
    if resp.get("status") != "ok":
        log(f"GCS start_proxy failed: {resp}")
        result["status"] = "gcs_start_failed"
        return result

    # Wait for GCS proxy to be ready by polling status
    log("Waiting for GCS proxy to report ready...")
    start_wait = time.time()
    ready = False
    while time.time() - start_wait < 20.0:
        time.sleep(0.5)
        try:
            st = send_gcs_command("status")
            if st.get("proxy_running"):
                ready = True
                break
        except Exception:
            pass

    if not ready:
        log("GCS proxy did not become ready in time")
        result["status"] = "gcs_not_ready"
        return result
    
    # Now start drone proxy (it will connect to GCS)
    log(f"Starting drone proxy for {suite_name}...")
    if not proxy.start(suite_name):
        result["status"] = "proxy_start_failed"
        # include last log path if available
        try:
            tail = getattr(proxy, "_last_log", None)
            if tail:
                result["log"] = str(tail)
        except Exception:
            pass
        return result
    
    # Wait for handshake
    time.sleep(1.0)
    
    # Tell GCS to start traffic
    log("Telling GCS to start traffic...")
    resp = send_gcs_command("start_traffic", duration=duration)
    if resp.get("status") != "ok":
        log(f"GCS start_traffic failed: {resp}")
        result["status"] = "gcs_traffic_failed"
        return result
    
    log("Traffic started, waiting for completion... (mavproxy relaying MAVLink)")
    
    # Wait for GCS to finish traffic generation
    # Poll GCS status
    traffic_done = False
    start_time = time.time()
    max_wait = duration + 30  # Extra buffer
    
    while time.time() - start_time < max_wait:
        time.sleep(2.0)
        
        # Log mavproxy status periodically
        try:
            log(f"mavproxy running: {mavproxy.is_running()}")
        except Exception:
            pass
        
        # Check GCS status
        status = send_gcs_command("status")
        if status.get("traffic_complete"):
            traffic_done = True
            break
        
        # Check if proxy died
        if not proxy.is_running():
            log("Proxy exited unexpectedly")
            result["status"] = "proxy_exited"
            return result
    
    if not traffic_done:
        log("Traffic did not complete in time")
        result["status"] = "timeout"
        return result
    
    # Indicate mavproxy and proxy status in result
    try:
        if hasattr(mavproxy, "is_running"):
            result["mavproxy_running"] = bool(mavproxy.is_running())
        else:
            result["mavproxy_running"] = mavproxy is not None and getattr(mavproxy, "poll", lambda: 1)() is None
    except Exception:
        result["mavproxy_running"] = False
    result["proxy_running"] = bool(proxy.is_running())
    result["status"] = "pass"
    
    return result


# ============================================================
# Scheduler Class
# ============================================================


class DroneScheduler:
    """Manages persistent MAVProxy and per-suite crypto tunnels."""

    def __init__(self, args, suites):
        self.args = args
        self.suites = suites
        self.policy = LinearLoopPolicy(self.suites)
        self.proxy = DroneProxyManager()
        self.mavproxy_proc = None
        self.current_proxy_proc = None
        self.current_suite = None
        
        # Telemetry & Decision Context
        self.telemetry = TelemetryListener(GCS_TELEMETRY_PORT, allowed_ip=GCS_HOST)
        self.context = DecisionContext(self.telemetry, self.suites)
        
        # Action log file
        self.action_log_file = LOGS_DIR / "drone_actions.jsonl"
        self.decision_log_file = LOGS_DIR / "drone_decision_context.jsonl"
        
        # Simple GCS client wrapper exposing send_command
        class _GcsClient:
            def send_command(self, cmd, params=None):
                params = params or {}
                try:
                    return send_gcs_command(cmd, **params)
                except Exception as e:
                    return {"status": "error", "message": str(e)}

        self.gcs_client = _GcsClient()

    def wait_for_handshake_completion(self, timeout: float = 10.0) -> bool:
        """Poll for the handshake completion status file."""
        status_file = Path(__file__).resolve().parents[1] / "logs" / "drone_status.json"
        start_time = time.time()
        while time.time() - start_time < timeout:
            if status_file.exists():
                try:
                    with open(status_file, "r") as f:
                        data = json.load(f)
                        if data.get("status") == "handshake_ok":
                            return True
                except Exception:
                    pass
            time.sleep(0.1)
        return False

    def start_persistent_mavproxy(self) -> bool:
        """Start MAVProxy once for the scheduler and keep handle."""
        try:
            python_exe = sys.executable
            master = self.args.mav_master
            out_arg = f"udp:127.0.0.1:{DRONE_PLAIN_TX_PORT}"

            # Interactive mode requested
            # [FIX] Added --daemon to prevent prompt_toolkit crash on Windows/Headless environments
            cmd = [
                python_exe,
                "-m",
                "MAVProxy.mavproxy",
                f"--master={master}",
                f"--out={out_arg}",
                "--nowait",
                "--daemon",
            ]

            ts = time.strftime("%Y%m%d-%H%M%S")
            log_dir = LOGS_DIR
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"mavproxy_drone_{ts}.log"
            try:
                fh = open(log_path, "w", encoding="utf-8")
            except Exception:
                fh = subprocess.DEVNULL

            log(f"Starting persistent mavproxy (drone): {' '.join(cmd)} (log: {log_path})")
            
            self.mavproxy_proc = ManagedProcess(
                cmd=cmd,
                name="mavproxy-drone",
                stdout=fh,
                stderr=subprocess.STDOUT,
                new_console=False # Headless for stability
            )
            
            if self.mavproxy_proc.start():
                time.sleep(1.0)
                return self.mavproxy_proc.is_running()
            return False
        except Exception as e:
            log(f"start_persistent_mavproxy exception: {e}")
            return False

    def start_tunnel_for_suite(self, suite_name: str) -> bool:
        return self.proxy.start(suite_name)

    def stop_current_tunnel(self):
        try:
            # stop crypto proxy
            if self.proxy and self.proxy.is_running():
                logging.info("Stopping crypto proxy")
                self.proxy.stop()
        except Exception:
            pass

    def _log_action(self, action: str, suite: str, target_suite: Optional[str], reasons: List[str], confidence: float):
        """Write action to JSONL log (only for non-HOLD actions)."""
        try:
            entry = {
                "schema": "uav.pqc.drone.action.v1",
                "ts_iso": datetime.now(timezone.utc).isoformat(),
                "mono_ms": time.monotonic() * 1000.0,
                "action": action,
                "current_suite": suite,
                "target_suite": target_suite,
                "reasons": reasons,
                "confidence": round(confidence, 3),
                "local_epoch": self.context._local_epoch,
            }
            with open(self.action_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _log_decision(self, decision: Dict[str, Any]):
        """Write decision context to JSONL log (every tick)."""
        try:
            decision["ts_iso"] = datetime.now(timezone.utc).isoformat()
            with open(self.decision_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(decision) + "\n")
        except Exception:
            pass

    def execute_action(self, policy_out: PolicyOutput, current_suite: str) -> bool:
        """
        Execute policy action.
        
        Returns True if action was executed successfully, False otherwise.
        HOLD always returns True (no-op success).
        """
        action = policy_out.action
        
        if action == PolicyAction.HOLD:
            return True
        
        target = policy_out.target_suite or current_suite
        
        # Log the action before executing
        self._log_action(
            action=action.value,
            suite=current_suite,
            target_suite=target,
            reasons=policy_out.reasons,
            confidence=policy_out.confidence,
        )
        
        if action == PolicyAction.DOWNGRADE:
            log(f"[ACTION] DOWNGRADE from {current_suite} to {target}")
            return self._execute_suite_switch(target, cooldown_s=COOLDOWN_DOWNGRADE_S)
        
        elif action == PolicyAction.UPGRADE:
            log(f"[ACTION] UPGRADE from {current_suite} to {target}")
            return self._execute_suite_switch(target, cooldown_s=COOLDOWN_SWITCH_S)
        
        elif action == PolicyAction.REKEY:
            log(f"[ACTION] REKEY suite {target}")
            return self._execute_rekey(target)
        
        return True

    def _execute_suite_switch(self, target_suite: str, cooldown_s: float) -> bool:
        """Execute a suite switch (downgrade or upgrade)."""
        try:
            # Tell GCS to prepare for rekey
            log(f"Telling GCS to prepare rekey for switch to {target_suite}...")
            resp = self.gcs_client.send_command("prepare_rekey")
            if resp.get("status") != "ok":
                log(f"GCS prepare_rekey failed: {resp}")
                return False
            
            # Stop local proxy
            self.stop_current_tunnel()
            time.sleep(0.5)
            
            # Tell GCS to start its proxy for new suite
            log(f"Telling GCS to start proxy for {target_suite}...")
            resp = self.gcs_client.send_command("start_proxy", {"suite": target_suite})
            if resp.get("status") != "ok":
                log(f"GCS start_proxy failed: {resp}")
                return False
            
            # Start local proxy
            if not self.start_tunnel_for_suite(target_suite):
                log(f"Failed to start local proxy for {target_suite}")
                return False
            
            # Record the switch
            self.context.record_suite_switch(target_suite, cooldown_s)
            self.current_suite = target_suite
            log(f"Suite switch to {target_suite} complete")
            return True
            
        except Exception as e:
            log(f"Suite switch error: {e}")
            return False

    def _execute_rekey(self, suite_name: str) -> bool:
        """Execute a rekey (restart proxies with same suite)."""
        try:
            log(f"Executing rekey for {suite_name}...")
            
            # Tell GCS to prepare
            resp = self.gcs_client.send_command("prepare_rekey")
            if resp.get("status") != "ok":
                log(f"GCS prepare_rekey failed: {resp}")
                return False
            
            # Stop and restart local proxy
            self.stop_current_tunnel()
            time.sleep(0.5)
            
            # Tell GCS to restart
            resp = self.gcs_client.send_command("start_proxy", {"suite": suite_name})
            if resp.get("status") != "ok":
                log(f"GCS start_proxy failed: {resp}")
                return False
            
            # Restart local
            if not self.start_tunnel_for_suite(suite_name):
                log(f"Failed to restart local proxy for {suite_name}")
                return False
            
            # Record rekey with longer cooldown
            self.context.record_suite_switch(suite_name, COOLDOWN_REKEY_S)
            log(f"Rekey for {suite_name} complete")
            return True
            
        except Exception as e:
            log(f"Rekey error: {e}")
            return False

    def cleanup(self):
        logging.info("--- DroneScheduler CLEANUP START ---")
        try:
            if self.telemetry:
                self.telemetry.stop()
        except Exception:
            pass

        try:
            self.stop_current_tunnel()
        except Exception:
            pass

        try:
            if self.mavproxy_proc:
                logging.info(f"Terminating MAVProxy")
                self.mavproxy_proc.stop()
        except Exception:
            pass

        logging.info("--- DroneScheduler CLEANUP COMPLETE ---")

    def run_scheduler(self):
        """
        Main scheduler loop with telemetry-aware policy evaluation.
        
        Flow:
        1. Start telemetry listener and MAVProxy
        2. Pick initial suite from policy
        3. Per-tick loop:
           a. Evaluate policy -> PolicyOutput (HOLD/DOWNGRADE/UPGRADE/REKEY)
           b. Log decision context (every tick)
           c. Execute action if not HOLD
           d. Sleep tick interval
        4. Suite duration triggers advance to next policy suite
        """
        def _sigint(sig, frame):
            log("Interrupted; cleaning up and exiting")
            self.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, _sigint)

        # Start Telemetry Listener
        self.telemetry.start()

        # Start MAVProxy once
        ok = self.start_persistent_mavproxy()
        if not ok:
            log("Warning: persistent MAVProxy failed to start; continuing")

        TICK_INTERVAL_S = 1.0  # Policy evaluation rate
        count = 0
        
        try:
            while True:
                # Get next suite from legacy policy (for scheduling progression)
                suite_name = self.policy.next_suite()
                duration = self.policy.get_duration()
                self.current_suite = suite_name
                
                log(f"=== Activating Suite: {suite_name} (duration={duration}) ===")

                # Coordinate with GCS: request GCS to start its proxy BEFORE starting local proxy
                try:
                    log(f"Telling GCS to start proxy for {suite_name}...")
                    resp = self.gcs_client.send_command("start_proxy", {"suite": suite_name})
                    if resp.get("status") != "ok":
                        logging.error(f"GCS rejected start_proxy: {resp}")
                        time.sleep(1.0)
                        continue
                    else:
                        log(f"GCS acknowledged start_proxy for {suite_name}")
                except Exception as e:
                    logging.error(f"Failed to command GCS: {e}")
                    time.sleep(1.0)
                    continue

                # Now start local crypto tunnel (drone proxy)
                self.start_tunnel_for_suite(suite_name)
                
                # Record suite activation
                self.context.record_suite_switch(suite_name, COOLDOWN_SWITCH_S)
                
                # Wait for handshake to complete before counting duration
                if self.wait_for_handshake_completion(timeout=10.0):
                    log(f"Handshake complete for {suite_name}")
                else:
                    log(f"Warning: Handshake timed out for {suite_name}")

                # ============================================
                # POLICY-DRIVEN MONITORING LOOP
                # ============================================
                start_run = time.time()
                tick_count = 0
                
                while time.time() - start_run < duration:
                    tick_count += 1
                    now_mono = time.monotonic()
                    
                    # 1. Evaluate telemetry-aware policy
                    try:
                        policy_out = self.context.evaluate_policy(self.current_suite)
                        decision = self.context.decide(self.current_suite)
                        
                        # 2. Log decision context (every tick)
                        self._log_decision(decision)
                        
                        # 3. Execute action if not HOLD
                        if policy_out.action != PolicyAction.HOLD:
                            log(f"[TICK {tick_count}] Policy action: {policy_out.action.value} -> {policy_out.target_suite}")
                            log(f"  Reasons: {policy_out.reasons}")
                            log(f"  Confidence: {policy_out.confidence:.2f}")
                            
                            # Execute the action
                            success = self.execute_action(policy_out, self.current_suite)
                            if success:
                                log(f"  Action executed successfully")
                                # If we switched suites, update current
                                if policy_out.target_suite:
                                    self.current_suite = policy_out.target_suite
                            else:
                                log(f"  Action execution FAILED")
                        else:
                            # HOLD - optional verbose logging (every 10th tick)
                            if tick_count % 10 == 0:
                                stats = self.telemetry.window.summarize()
                                log(f"[TICK {tick_count}] HOLD - suite={self.current_suite}, "
                                    f"samples={stats.get('count', 0)}, "
                                    f"gap_p95={stats.get('gap_p95_ms', 'N/A')}, "
                                    f"conf={policy_out.confidence:.2f}")
                    
                    except Exception as e:
                        logging.warning(f"Policy evaluation error: {e}")
                    
                    time.sleep(TICK_INTERVAL_S)

                # Duration complete - stop tunnel before switching
                self.stop_current_tunnel()

                count += 1
                if self.args.max_suites and count >= int(self.args.max_suites):
                    log(f"Reached max_suites ({self.args.max_suites}), stopping scheduler")
                    break

                time.sleep(2.0)
                
        except Exception as e:
            logging.error(f"Scheduler crash: {e}")
        finally:
            self.cleanup()


# ============================================================
# Main
# ============================================================

def cleanup_environment():
    """Force kill any stale instances of our components (Linux/Posix)."""
    log("Cleaning up stale processes...")
    patterns = ["mavproxy.py", "core.run_proxy"]
    for p in patterns:
        try:
            # -f matches full command line, ignore exit code (1 if not found)
            subprocess.run(["pkill", "-f", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log(f"Cleanup warning: {e}")
    # Give OS time to reclaim resources
    time.sleep(1.0)

def main():
    parser = argparse.ArgumentParser(description="Drone Scheduler (Controller)")
    parser.add_argument("--mav-master", default=str(CONFIG.get("MAV_MASTER", "/dev/ttyACM0")), help="Primary MAVLink master (e.g. /dev/ttyACM0 or tcp:host:port)")
    parser.add_argument("--suite", default=None, help="Single suite to run")
    parser.add_argument("--nist-level", choices=["L1", "L3", "L5"], help="Run suites for NIST level")
    parser.add_argument("--all", action="store_true", help="Run all suites")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION, help="Seconds per suite")
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE_MBPS, help="Traffic rate Mbps")
    parser.add_argument("--max-suites", type=int, default=None, help="Max suites to run")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Simplified Drone Scheduler (CONTROLLER) - sscheduler")
    print("=" * 60)
    # Configuration dump for debugging
    cfg = {
        "DRONE_HOST": DRONE_HOST,
        "GCS_HOST": GCS_HOST,
        "GCS_CONTROL": f"{GCS_CONTROL_HOST}:{GCS_CONTROL_PORT}",
        "PROXY_INTERNAL_CONTROL_PORT": PROXY_INTERNAL_CONTROL_PORT,
        "DRONE_PLAINTEXT_RX": DRONE_PLAIN_RX_PORT,
        "DRONE_PLAINTEXT_TX": DRONE_PLAIN_TX_PORT,
    }
    log("Configuration Dump:")
    for k, v in cfg.items():
        log(f"  {k}: {v}")
    log(f"Duration: {args.duration}s per suite, Rate: {args.rate} Mbps")
    
    # Determine suites to run
    if args.suite:
        suites_to_run = [args.suite]
    elif args.nist_level:
        suites_to_run = [s["name"] for s in SUITES if s.get("nist_level") == args.nist_level]
    elif args.all:
        suites_to_run = [s["name"] for s in SUITES]
    else:
        # Default: run all available suites
        suites_to_run = [s["name"] for s in SUITES]

    if args.max_suites:
        suites_to_run = suites_to_run[:args.max_suites]

    # Register cleanup on exit
    atexit.register(cleanup_environment)

    # Apply local in-file overrides
    if LOCAL_RATE_MBPS is not None:
        args.rate = float(LOCAL_RATE_MBPS)
    if LOCAL_DURATION is not None:
        args.duration = float(LOCAL_DURATION)
    if LOCAL_SUITES:
        suites_to_run = [s for s in LOCAL_SUITES if s in [x["name"] for x in SUITES]]
    if LOCAL_MAX_SUITES:
        suites_to_run = suites_to_run[: int(LOCAL_MAX_SUITES)]

    log(f"Suites to run: {len(suites_to_run)}")

    # Cleanup environment before starting
    cleanup_environment()

    # Initialize components
    scheduler = DroneScheduler(args, suites_to_run)
    # configure logging
    logging.basicConfig(level=logging.INFO)
    scheduler.run_scheduler()

    return 0

if __name__ == "__main__":
    sys.exit(main())
