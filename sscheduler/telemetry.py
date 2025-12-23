import time
try:
    import psutil
import time
import threading
import psutil
import platform
import logging
import json
import os
from datetime import datetime
from pymavlink import mavutil


class TelemetryCollector:
    def __init__(self, role="unknown"):
        self.role = role # "drone" or "gcs"
        self.running = False
        self.lock = threading.Lock()
        self.os_type = platform.system() # 'Linux' or 'Windows'
        
        # Metrics Storage
        self.metrics = {
            "packet_count": 0,
            "packet_loss": 0,   # Calculated via Sequence Gaps
            "jitter_ms": 0.0,   # Calculated via Arrival Time Variance
            "cpu_util": 0.0,
            "temp_c": 0.0,      # Critical for PQC Thermal throttling
            "temp_slope": 0.0,  # Rate of change (C/s)
            "blackout_recovery": 0.0
        }
        
        # Internal Calculation State
        self.last_seq = -1
        self.last_arrival = 0
        self.blackout_start = 0
        self.prev_temp = 0
        self.prev_temp_time = 0

    def get_temperature(self):
        """Cross-platform safe temperature reading."""
        temp = 0.0
        try:
            if self.os_type == "Linux":
                # Standard Raspberry Pi Thermal Zone
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read().strip()) / 1000.0
            # Windows temperature reading is complex/hardware-specific, 
            # so we skip it to prevent crashes, or use psutil if supported later.
        except Exception:
            pass # Fail silently, return 0.0
        return temp

    def start(self, port):
        """Starts the passive sniffer in a background thread."""
        self.running = True
        # GCS listens on all interfaces, Drone listens on localhost
        bind_ip = "0.0.0.0" if self.role == "gcs" else "127.0.0.1"
        connection_str = f'udpin:{bind_ip}:{port}'
        
        logging.info(f"[Telemetry] Sniffer starting on {connection_str}")
        self.thread = threading.Thread(target=self._loop, args=(connection_str,), daemon=True)
        self.thread.start()

    def _loop(self, conn_str):
        # Establish MAVLink connection for sniffing
        conn = mavutil.mavlink_connection(conn_str)
        
        while self.running:
            # Non-blocking receive
            msg = conn.recv_match(blocking=True, timeout=1.0)
            if not msg: continue
            
            with self.lock:
                self.metrics["packet_count"] += 1
                now = time.time()

                # --- 1. Blackout Measurement ---
                if self.blackout_start > 0:
                    self.metrics["blackout_recovery"] = now - self.blackout_start
                    self.blackout_start = 0 # Reset flag
                    # Reset stream logic to avoid false jitter/loss spikes
                    self.last_arrival = 0 
                    self.last_seq = -1
                    continue

                # --- 2. Jitter Measurement (Inter-arrival) ---
                if self.last_arrival > 0:
                    delta_ms = (now - self.last_arrival) * 1000.0
                    # Simple Exponential Moving Average for Jitter
                    # We expect packets approx every 100-1000ms depending on rate
                    # This calculates variance.
                    self.metrics["jitter_ms"] = (self.metrics["jitter_ms"] * 0.9) + (abs(delta_ms) * 0.1)

                self.last_arrival = now
                
                # --- 3. Packet Loss (Sequence Analysis) ---
                # MAVLink uses 0-255 sequence numbers
                try:
                    seq = msg.get_header().seq
                    if self.last_seq != -1:
                        expected = (self.last_seq + 1) % 256
                        if seq != expected:
                            # Calculate gap
                            lost = (seq - expected) % 256
                            self.metrics["packet_loss"] += lost
                    self.last_seq = seq
                except:
                    pass

    def mark_rekey_event(self):
        """Call this immediately before tearing down the secure tunnel."""
        with self.lock:
            self.blackout_start = time.time()

    def snapshot(self):
        """Returns a copy of current metrics and updates system stats."""
        with self.lock:
            self.metrics["cpu_util"] = psutil.cpu_percent()
            
            # Temp Slope Calculation
            curr_temp = self.get_temperature()
            now = time.time()
            if self.prev_temp_time > 0 and (now - self.prev_temp_time) > 0.5:
                slope = (curr_temp - self.prev_temp) / (now - self.prev_temp_time)
                self.metrics["temp_slope"] = slope
            
            self.metrics["temp_c"] = curr_temp
            self.prev_temp = curr_temp
            self.prev_temp_time = now

            return self.metrics.copy()

    def stop(self):
        self.running = False
        # close file handle if present
        try:
            if hasattr(self, "file_handle") and self.file_handle:
                self.file_handle.close()
        except Exception:
            pass

    def configure_logging(self, base_log_dir, run_id):
        """Sets up the log directory for this specific run."""
        self.run_id = run_id
        # Create structure: base_log_dir/run_<run_id>/
        self.run_dir = os.path.join(base_log_dir, f"run_{run_id}")
        os.makedirs(self.run_dir, exist_ok=True)

        # Define file path: base_log_dir/run_<id>/<role>_telemetry.jsonl
        self.log_file = os.path.join(self.run_dir, f"{self.role}_telemetry.jsonl")

        # Open file in Append mode
        self.file_handle = open(self.log_file, "a", encoding="utf-8")
        logging.info(f"[{self.role}] Telemetry logging to: {self.log_file}")

    def log_snapshot(self, suite_name):
        """Captures snapshot, adds metadata, writes to JSON line."""
        stats = self.snapshot()

        log_entry = {
            "timestamp": time.time(),
            "iso_time": datetime.utcnow().isoformat() + "Z",
            "run_id": getattr(self, "run_id", ""),
            "role": self.role,
            "suite": suite_name,
            "metrics": stats,
        }

        if hasattr(self, 'file_handle') and self.file_handle:
            try:
                self.file_handle.write(json.dumps(log_entry) + "\n")
                self.file_handle.flush()
            except Exception:
                pass

        return log_entry

    def close(self):
        self.running = False
        try:
            if hasattr(self, 'file_handle') and self.file_handle:
                self.file_handle.close()
        except Exception:
            pass
