"""
GCS Telemetry Metrics Collector (Schema v1)
sscheduler/gcs_metrics.py

Collects real-time receiver-side metrics for the GCS, matching schema uav.pqc.telemetry.v1.
Non-blocking, bounded memory, best-effort.
"""

import os
import time
import json
import threading
import socket
import logging
from pathlib import Path
from collections import deque, defaultdict
from datetime import datetime, timezone
from core.config import CONFIG

try:
    import psutil
except ImportError:
    psutil = None

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None

# Constants
SCHEMA_NAME = "uav.pqc.telemetry.v1"
SCHEMA_VER = 1
WINDOW_S = 5.0
BURST_GAP_THRESHOLD_MS = 200.0
MAX_PACKETS_PER_LOOP = 100

class GcsMetricsCollector:
    def __init__(self, mavlink_host, mavlink_port, proxy_manager=None, mavproxy_proc=None, log_dir=None):
        self.mavlink_host = mavlink_host
        self.mavlink_port = mavlink_port
        self.proxy_manager = proxy_manager
        self.mavproxy_proc = mavproxy_proc
        
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path(__file__).parent.parent / "logs"
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Telemetry always writes to the production file. Simulation support removed.
        self.log_file = self.log_dir / "gcs_telemetry_v1.jsonl"
        
        self.running = False
        self.thread = None
        self.mav_conn = None
        self.sock = None
        self.lock = threading.Lock()
        
        # Identity
        self.pid = os.getpid()
        self.boot_id = int(time.time())
        
        # Metrics State (Sliding Window)
        self.arrival_times = deque() # (mono_s, size_bytes)
        self.gaps = deque()          # (mono_s, gap_ms)
        self.burst_gaps = 0          # Count of gaps > threshold in window
        
        # MAVLink State
        self.mav_state = {
            "heartbeat": None,
            "sys_status": None,
            "radio_status": None,
            "failsafe": {"flags": 0, "last_statustext": None},
            "decode_stats": {"ok": 0, "parse_errors": 0, "reason": None}
        }
        self.msg_rates = defaultdict(int) # msg_id -> count in window
        self.msg_timestamps = deque()     # (mono_s, msg_id)
        
        # Tunnel/Events
        self.events = [] # List of event dicts
        
        # Loop health
        self.last_tick_mono = 0.0
        self.loop_lag_ms = 0.0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logging.info(f"GCS Metrics Collector v1 started on {self.mavlink_host}:{self.mavlink_port}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.mav_conn:
            self.mav_conn.close()
        if self.sock:
            self.sock.close()

    def _connect(self):
        # Use udpin to bind and listen for packets from MAVProxy
        conn_str = f"udpin:{self.mavlink_host}:{self.mavlink_port}"
        if mavutil:
            try:
                self.mav_conn = mavutil.mavlink_connection(conn_str, source_system=255)
                return True
            except Exception as e:
                logging.error(f"MAVLink connect failed: {e}")
                pass
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((self.mavlink_host, self.mavlink_port))
            self.sock.settimeout(0.1)
            return True
        except Exception as e:
            logging.error(f"Socket bind failed: {e}")
            return False

    def _prune_windows(self, now_mono):
        cutoff = now_mono - WINDOW_S
        
        while self.arrival_times and self.arrival_times[0][0] < cutoff:
            self.arrival_times.popleft()
            
        while self.gaps and self.gaps[0][0] < cutoff:
            self.gaps.popleft()
            
        while self.msg_timestamps and self.msg_timestamps[0][0] < cutoff:
            _, msg_id = self.msg_timestamps.popleft()
            self.msg_rates[msg_id] = max(0, self.msg_rates[msg_id] - 1)

    def _process_mavlink(self, msg, now_mono):
        msg_type = msg.get_type()
        msg_id = msg.get_msgId()
        
        # Rate tracking
        self.msg_rates[msg_id] += 1
        self.msg_timestamps.append((now_mono, msg_id))
        
        if msg_type == 'HEARTBEAT':
            self.mav_state['heartbeat'] = {
                "age_ms": 0, # Updated at snapshot time
                "last_mono": now_mono,
                "armed": bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) if mavutil else False,
                "mode": msg.custom_mode,
                "sysid": msg.get_srcSystem(),
                "compid": msg.get_srcComponent()
            }
        elif msg_type == 'SYS_STATUS':
            self.mav_state['sys_status'] = {
                "battery_remaining_pct": msg.battery_remaining,
                "voltage_battery_mv": msg.voltage_battery,
                "drop_rate_comm": msg.drop_rate_comm,
                "errors_count": [msg.errors_count1, msg.errors_count2, msg.errors_count3, msg.errors_count4],
                "load_pct": msg.load / 10.0 # usually 1000 = 100%
            }
        elif msg_type == 'RADIO_STATUS':
            self.mav_state['radio_status'] = {
                "rssi": msg.rssi,
                "remrssi": msg.remrssi,
                "noise": msg.noise,
                "remnoise": msg.remnoise,
                "rxerrors": msg.rxerrors,
                "fixed": msg.fixed
            }
        elif msg_type == 'STATUSTEXT':
            txt = msg.text
            if isinstance(txt, bytes):
                txt = txt.decode('utf-8', errors='ignore')
            self.mav_state['failsafe']['last_statustext'] = txt

    def _read_packets(self):
        count = 0
        now_mono = time.monotonic()
        
        while count < MAX_PACKETS_PER_LOOP:
            ts_mono = None
            size = 0
            msg = None
            
            if self.mav_conn:
                try:
                    msg = self.mav_conn.recv_match(blocking=False)
                    if msg:
                        # Robust guard: Check for BAD_DATA explicitly
                        if msg.get_type() == 'BAD_DATA':
                            self.mav_state['decode_stats']['parse_errors'] += 1
                            # Bound reason string
                            reason = "MAVLink_bad_data"
                            if hasattr(msg, 'reason'):
                                reason = str(msg.reason)[:50]
                            self.mav_state['decode_stats']['reason'] = reason
                            continue

                        ts_mono = time.monotonic()
                        # Estimate size
                        size = 20 # Header
                        if hasattr(msg, 'get_payload'):
                             payload = msg.get_payload()
                             # Robust guard: Never call len(payload) unless payload is bytes-like
                             if payload is not None and isinstance(payload, (bytes, bytearray)):
                                 size += len(payload)
                             elif payload is None:
                                 # Payload is None, safe to ignore or handle
                                 pass
                        
                        self.mav_state['decode_stats']['ok'] += 1
                        self._process_mavlink(msg, ts_mono)
                except Exception as e:
                    self.mav_state['decode_stats']['parse_errors'] += 1
                    self.mav_state['decode_stats']['reason'] = str(e)[:50] # Bounded reason string
            elif self.sock:
                try:
                    data, _ = self.sock.recvfrom(65535)
                    ts_mono = time.monotonic()
                    size = len(data)
                except socket.timeout:
                    pass
                except Exception:
                    pass
            
            if ts_mono:
                with self.lock:
                    # Gap detection
                    if self.arrival_times:
                        last_mono = self.arrival_times[-1][0]
                        gap_ms = (ts_mono - last_mono) * 1000.0
                        self.gaps.append((ts_mono, gap_ms))
                        if gap_ms > BURST_GAP_THRESHOLD_MS:
                            self.burst_gaps += 1
                    
                    self.arrival_times.append((ts_mono, size))
                count += 1
            else:
                break
        
        with self.lock:
            self._prune_windows(now_mono)
            # Prune burst gaps count (recalculate from window)
            self.burst_gaps = sum(1 for _, g in self.gaps if g > BURST_GAP_THRESHOLD_MS)

    def get_snapshot(self):
        now_mono = time.monotonic()
        now_wall = time.time()
        
        with self.lock:
            # Metrics Calculation
            count = len(self.arrival_times)
            total_bytes = sum(s for _, s in self.arrival_times)
            
            rx_pps = count / WINDOW_S
            rx_bps = total_bytes / WINDOW_S
            
            silence_ms = 0.0
            if self.arrival_times:
                silence_ms = (now_mono - self.arrival_times[-1][0]) * 1000.0
            
            gap_max_ms = 0.0
            gap_p95_ms = 0.0
            jitter_ms = 0.0
            
            if self.gaps:
                gap_values = [g for _, g in self.gaps]
                gap_max_ms = max(gap_values)
                gap_values.sort()
                idx = int(len(gap_values) * 0.95)
                gap_p95_ms = gap_values[idx] if gap_values else 0.0
                
                if len(gap_values) > 1:
                    mean_gap = sum(gap_values) / len(gap_values)
                    jitter_ms = sum(abs(g - mean_gap) for g in gap_values) / len(gap_values)

            # System Stats
            cpu_pct = psutil.cpu_percent(interval=None) if psutil else 0.0
            mem_pct = psutil.virtual_memory().percent if psutil else 0.0
            cpu_freq = 0.0
            if psutil and hasattr(psutil, 'cpu_freq'):
                f = psutil.cpu_freq()
                if f: cpu_freq = f.current
            
            # Process Health
            mavproxy_alive = False
            mavproxy_pid = 0
            if self.mavproxy_proc:
                mavproxy_alive = self.mavproxy_proc.is_running()
                mavproxy_pid = self.mavproxy_proc.process.pid if self.mavproxy_proc.process else 0
            
            # Proxy Status
            proxy_alive = False
            proxy_pid = 0
            active_suite = None
            if self.proxy_manager:
                proxy_alive = self.proxy_manager.is_running()
                active_suite = self.proxy_manager.current_suite
                # If ManagedProcess exposed PID, we'd use it. Assuming it does via .process
                if self.proxy_manager.managed_proc and self.proxy_manager.managed_proc.process:
                    proxy_pid = self.proxy_manager.managed_proc.process.pid

            # MAVLink Rates
            msg_rate_total = len(self.msg_timestamps) / WINDOW_S
            # Critical: HEARTBEAT(0), SYS_STATUS(1), STATUSTEXT(253)
            msg_rate_critical = (self.msg_rates[0] + self.msg_rates[1] + self.msg_rates[253]) / WINDOW_S
            # High: ATTITUDE(30), VFR_HUD(74) - examples
            msg_rate_high = (self.msg_rates[30] + self.msg_rates[74]) / WINDOW_S

            # Heartbeat Age
            hb = self.mav_state['heartbeat']
            if hb:
                hb['age_ms'] = (now_mono - hb['last_mono']) * 1000.0
                # Remove internal field before export
                hb_export = hb.copy()
                del hb_export['last_mono']
            else:
                hb_export = None

            snapshot = {
                "schema": SCHEMA_NAME,
                "schema_ver": SCHEMA_VER,
                "sender": {
                    "role": "gcs",
                    "node_id": socket.gethostname(),
                    "pid": self.pid
                },
                "t": {
                    "wall_ms": now_wall * 1000.0,
                    "mono_ms": now_mono * 1000.0,
                    "boot_id": self.boot_id
                },
                    "caps": {
                        "pymavlink": mavutil is not None,
                        "psutil": psutil is not None,
                        "proxy_status_file": False, # Deprecated in favor of process check
                    },
                "state": {
                    "gcs": {
                        "mavproxy_alive": mavproxy_alive,
                        "mavproxy_pid": mavproxy_pid,
                        "qgc_alive": False, # Placeholder
                        "collector_alive": True,
                        "collector_last_tick_mono_ms": self.last_tick_mono * 1000.0,
                        "collector_loop_lag_ms": self.loop_lag_ms
                    },
                    "suite": {
                        "active_suite": active_suite,
                        "suite_epoch": 0, # TODO: wire if available
                        "pending_suite": None
                    }
                },
                "metrics": {
                    "sniff": {
                        "bind": f"{self.mavlink_host}:{self.mavlink_port}",
                        "window_s": WINDOW_S,
                        "sample_count": count,
                        "rx_pps": round(rx_pps, 1),
                        "rx_bps": round(rx_bps, 1),
                        "silence_ms": round(silence_ms, 1),
                        "gap_max_ms": round(gap_max_ms, 1),
                        "gap_p95_ms": round(gap_p95_ms, 1),
                        "jitter_ms": round(jitter_ms, 1),
                        "burst_gap_count": self.burst_gaps,
                        "burst_gap_threshold_ms": BURST_GAP_THRESHOLD_MS
                    },
                    "sys": {
                        "cpu_pct": cpu_pct,
                        "mem_pct": mem_pct,
                        "cpu_freq_mhz": cpu_freq,
                        "temp_c": 0.0 # Requires platform specific
                    }
                },
                "mav": {
                    "decode": self.mav_state['decode_stats'],
                    "heartbeat": hb_export,
                    "sys_status": self.mav_state['sys_status'],
                    "radio_status": self.mav_state['radio_status'],
                    "rates": {
                        "window_s": WINDOW_S,
                        "msg_rate_total": round(msg_rate_total, 1),
                        "msg_rate_critical": round(msg_rate_critical, 1),
                        "msg_rate_high": round(msg_rate_high, 1)
                    },
                    "failsafe": self.mav_state['failsafe']
                },
                "tunnel": {
                    "proxy_alive": proxy_alive,
                    "proxy_pid": proxy_pid,
                    "status_file_age_ms": 0,
                    "counters": None
                },
                "events": list(self.events) # Copy
            }
            
            # Clear one-shot events
            self.events.clear()
            
            return snapshot

    def _run_loop(self):
        self._connect()
        last_log_time = time.monotonic()
        
        while self.running:
            loop_start = time.monotonic()
            
            # Reconnect
            if not self.mav_conn and not self.sock:
                if not self._connect():
                    time.sleep(1.0)
                    continue

            self._read_packets()
            
            # Logging (1Hz)
            if loop_start - last_log_time >= 1.0:
                self._write_log()
                last_log_time = loop_start
            
            # Loop health
            self.last_tick_mono = loop_start
            elapsed = time.monotonic() - loop_start
            self.loop_lag_ms = elapsed * 1000.0
            
            sleep_time = max(0.01, 0.1 - elapsed) # Aim for 10Hz loop
            time.sleep(sleep_time)

    def _write_log(self):
        try:
            snapshot = self.get_snapshot()
            # JSON serialization helper for non-serializable types
            def default(o):
                if isinstance(o, (datetime,)):
                    return o.isoformat()
                return str(o)
                
            with open(self.log_file, "a") as f:
                f.write(json.dumps(snapshot, default=default) + "\n")
        except Exception:
            pass

    def add_event(self, event_type, **kwargs):
        with self.lock:
            evt = {
                "type": event_type,
                "t_mono_ms": time.monotonic() * 1000.0,
                **kwargs
            }
            self.events.append(evt)
