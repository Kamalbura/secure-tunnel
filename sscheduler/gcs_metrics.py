"""
GCS Telemetry Metrics Collector
sscheduler/gcs_metrics.py

Collects real-time receiver-side metrics for the GCS, including:
- MAVLink/UDP link health (PPS, jitter, gaps)
- System health (CPU, RAM)
- Proxy status

Designed to be run as a background thread within the GCS scheduler.
"""

import time
import json
import threading
import socket
import logging
from pathlib import Path
from collections import deque
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    psutil = None

# Try to import pymavlink, but don't fail if missing
try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None

class GcsMetricsCollector:
    def __init__(self, mavlink_host, mavlink_port, proxy_status_file=None, log_dir=None):
        self.mavlink_host = mavlink_host
        self.mavlink_port = mavlink_port
        self.proxy_status_file = Path(proxy_status_file) if proxy_status_file else None
        
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path("logs/telemetry")
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "gcs_metrics.jsonl"
        
        self.running = False
        self.thread = None
        self.mav_conn = None
        self.sock = None # Fallback UDP socket
        
        # Metrics state
        self.lock = threading.Lock()
        self.seq = 0
        self.rx_count = 0
        self.rx_bytes = 0
        
        # Rolling windows for rate calculation
        self.arrival_times = deque(maxlen=200) # Keep last ~200 packet timestamps
        self.byte_counts = deque(maxlen=200)   # Keep corresponding byte counts
        self.gap_max_window = deque(maxlen=200) # Keep recent gaps
        
        self.start_time = 0
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logging.info(f"GCS Metrics Collector started. Listening on {self.mavlink_host}:{self.mavlink_port}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.mav_conn:
            self.mav_conn.close()
        if self.sock:
            self.sock.close()

    def _connect(self):
        """Attempt to connect to MAVLink stream"""
        conn_str = f"udp:{self.mavlink_host}:{self.mavlink_port}"
        
        if mavutil:
            try:
                # source_system=255 is GCS/Ground Station
                self.mav_conn = mavutil.mavlink_connection(conn_str, source_system=255)
                return True
            except Exception as e:
                logging.warning(f"pymavlink connect failed: {e}")
        
        # Fallback to raw UDP
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((self.mavlink_host, self.mavlink_port))
            self.sock.settimeout(0.5)
            return True
        except Exception as e:
            # It's possible the port isn't ready yet or bound by someone else
            # We will retry in the loop
            return False

    def _run_loop(self):
        # Initial connection attempt
        self._connect()
        
        last_log_time = time.time()
        last_print_time = time.time()
        
        while self.running:
            now = time.time()
            
            # 0. Reconnect if needed
            if not self.mav_conn and not self.sock:
                if self._connect():
                    logging.info(f"Connected to telemetry source on {self.mavlink_port}")
                else:
                    time.sleep(1.0)
                    continue

            # 1. Read packets (best effort, non-blocking burst)
            self._read_packets()
            
            # 2. Periodic Logging (JSONL)
            if now - last_log_time >= 0.5:
                self._write_log()
                last_log_time = now
                
            # 3. Periodic Printing (Stdout)
            if now - last_print_time >= 2.0:
                self._print_summary()
                last_print_time = now
                
            time.sleep(0.01) # Yield

    def _read_packets(self):
        # Read as many as available without blocking too long
        count = 0
        max_per_loop = 50
        
        while count < max_per_loop:
            ts = None
            size = 0
            
            if self.mav_conn:
                try:
                    msg = self.mav_conn.recv_match(blocking=False)
                    if msg:
                        ts = time.time()
                        # Estimate size (header + payload + crc)
                        # msg.get_header().pack() ... simplified:
                        size = getattr(msg, '_header', None) and len(msg._header.pack(msg)) or 20 
                        if hasattr(msg, 'get_payload'):
                             size += len(msg.get_payload())
                        else:
                             size = 50 # fallback
                except Exception:
                    pass
            elif self.sock:
                try:
                    data, _ = self.sock.recvfrom(65535)
                    ts = time.time()
                    size = len(data)
                except socket.timeout:
                    pass
                except Exception:
                    pass
            
            if ts:
                with self.lock:
                    self.rx_count += 1
                    self.rx_bytes += size
                    
                    if self.arrival_times:
                        gap = (ts - self.arrival_times[-1]) * 1000.0
                        self.gap_max_window.append((ts, gap))
                    self.arrival_times.append(ts)
                    self.byte_counts.append((ts, size))
                count += 1
            else:
                break

    def get_latest_snapshot(self):
        with self.lock:
            now = time.time()
            
            # Compute rates over last 2 seconds
            # Filter arrival_times to last 2s
            recent_arrivals = [t for t in self.arrival_times if now - t <= 2.0]
            rx_pps = len(recent_arrivals) / 2.0 if len(recent_arrivals) > 1 else 0.0
            
            # Compute bytes per second
            recent_bytes = [b for (t, b) in self.byte_counts if now - t <= 2.0]
            rx_bytes_per_s = sum(recent_bytes) / 2.0 if recent_bytes else 0.0
            
            # Compute max gap in last 2 seconds
            recent_gaps = [g for (t, g) in self.gap_max_window if now - t <= 2.0]
            gap_max_ms = max(recent_gaps) if recent_gaps else 0.0
            
            # Jitter (average deviation from mean gap)
            jitter = 0.0
            if len(recent_gaps) > 1:
                avg_gap = sum(recent_gaps) / len(recent_gaps)
                jitter = sum(abs(g - avg_gap) for g in recent_gaps) / len(recent_gaps)

            # System health
            cpu = psutil.cpu_percent(interval=None) if psutil else None
            mem = psutil.virtual_memory().percent if psutil else None
            
            # Proxy status
            proxy_alive = False
            active_suite = None
            # TODO: Read actual status file content if needed
            if self.proxy_status_file and self.proxy_status_file.exists():
                try:
                    mtime = self.proxy_status_file.stat().st_mtime
                    if now - mtime < 10.0:
                        proxy_alive = True
                except Exception:
                    pass

            snapshot = {
                "rx_pps": round(rx_pps, 1),
                "rx_bytes_per_s": round(rx_bytes_per_s, 1),
                "gap_max_ms": round(gap_max_ms, 1),
                "jitter_ms": round(jitter, 1),
                "cpu_pct": cpu,
                "mem_pct": mem,
                "proxy_alive": proxy_alive,
                "mavlink_status": "connected" if (self.mav_conn or self.sock) else "disconnected"
            }
            return snapshot, now

    def _write_log(self):
        snapshot, ts = self.get_latest_snapshot()
        
        entry = {
            "ts": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "seq": self.seq,
            "metrics": snapshot
        }
        self.seq += 1
        
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _print_summary(self):
        snapshot, ts = self.get_latest_snapshot()
        ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        print(f"[{ts_str}] rx_pps={snapshot['rx_pps']} gap_max={snapshot['gap_max_ms']}ms cpu={snapshot['cpu_pct']}% proxy={snapshot['proxy_alive']}")
