from __future__ import annotations

import json
import logging
import os
import platform
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

try:  # Optional dependency
    import psutil  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    psutil = None  # type: ignore

try:  # Optional dependency
    from pymavlink import mavutil  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    mavutil = None  # type: ignore


class TelemetryCollector:
    """Passive MAVLink telemetry collector."""

    def __init__(self, role: str = "unknown") -> None:
        self.role = role  # "drone" or "gcs"
        self.running = False
        self.lock = threading.Lock()
        self.os_type = platform.system()

        self.metrics: Dict[str, Any] = {
            "packet_count": 0,
            "packet_loss": 0,
            "jitter_ms": 0.0,
            "cpu_util": 0.0,
            "temp_c": 0.0,
            "temp_slope": 0.0,
            "blackout_recovery": 0.0,
        }

        self.last_seq = -1
        self.last_arrival = 0.0
        self.blackout_start = 0.0
        self.prev_temp = 0.0
        self.prev_temp_time = 0.0
        self.thread: Optional[threading.Thread] = None

        self.run_id = ""
        self.run_dir = ""
        self.log_file = ""
        self.file_handle = None

    def get_temperature(self) -> float:
        if self.os_type != "Linux":
            return 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as handle:
                return int(handle.read().strip()) / 1000.0
        except Exception:
            return 0.0

    def start(self, port: int) -> None:
        if mavutil is None:
            raise RuntimeError("pymavlink not installed; cannot start telemetry sniffer")

        self.running = True
        bind_ip = "0.0.0.0" if self.role == "gcs" else "127.0.0.1"
        connection_str = f"udpin:{bind_ip}:{int(port)}"
        logging.info(f"[Telemetry:{self.role}] Sniffer starting on {connection_str}")
        self.thread = threading.Thread(target=self._loop, args=(connection_str,), daemon=True)
        self.thread.start()

    def _loop(self, conn_str: str) -> None:
        assert mavutil is not None
        conn = mavutil.mavlink_connection(conn_str)

        while self.running:
            try:
                msg = conn.recv_match(blocking=True, timeout=1.0)
            except Exception:
                continue
            if not msg:
                continue

            with self.lock:
                self.metrics["packet_count"] += 1
                now = time.time()

                if self.blackout_start > 0:
                    self.metrics["blackout_recovery"] = now - self.blackout_start
                    self.blackout_start = 0.0
                    self.last_arrival = 0.0
                    self.last_seq = -1
                    continue

                if self.last_arrival > 0:
                    delta_ms = (now - self.last_arrival) * 1000.0
                    self.metrics["jitter_ms"] = (self.metrics["jitter_ms"] * 0.9) + (abs(delta_ms) * 0.1)
                self.last_arrival = now

                try:
                    seq = int(msg.get_header().seq)
                    if self.last_seq != -1:
                        expected = (self.last_seq + 1) % 256
                        if seq != expected:
                            self.metrics["packet_loss"] += int((seq - expected) % 256)
                    self.last_seq = seq
                except Exception:
                    pass

    def mark_rekey_event(self) -> None:
        with self.lock:
            self.blackout_start = time.time()

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            if psutil is not None:
                try:
                    self.metrics["cpu_util"] = float(psutil.cpu_percent())
                except Exception:
                    self.metrics["cpu_util"] = 0.0
            else:
                self.metrics["cpu_util"] = 0.0

            curr_temp = self.get_temperature()
            now = time.time()
            if self.prev_temp_time > 0 and (now - self.prev_temp_time) > 0.5:
                self.metrics["temp_slope"] = (curr_temp - self.prev_temp) / (now - self.prev_temp_time)
            self.metrics["temp_c"] = curr_temp
            self.prev_temp = curr_temp
            self.prev_temp_time = now
            return dict(self.metrics)

    def stop(self) -> None:
        self.running = False
        try:
            if self.thread:
                self.thread.join(timeout=1.0)
        except Exception:
            pass
        self.close()

    def configure_logging(self, base_log_dir: str, run_id: str) -> None:
        self.run_id = run_id
        self.run_dir = os.path.join(base_log_dir, f"run_{run_id}")
        os.makedirs(self.run_dir, exist_ok=True)
        self.log_file = os.path.join(self.run_dir, f"{self.role}_telemetry.jsonl")
        self.file_handle = open(self.log_file, "a", encoding="utf-8")
        logging.info(f"[{self.role}] Telemetry logging to: {self.log_file}")

    def log_snapshot(self, suite_name: str) -> Dict[str, Any]:
        stats = self.snapshot()
        log_entry: Dict[str, Any] = {
            "timestamp": time.time(),
            "iso_time": datetime.utcnow().isoformat() + "Z",
            "run_id": getattr(self, "run_id", ""),
            "role": self.role,
            "suite": suite_name,
            "metrics": stats,
        }

        if self.file_handle:
            try:
                self.file_handle.write(json.dumps(log_entry) + "\n")
                self.file_handle.flush()
            except Exception:
                pass

        return log_entry

    def close(self) -> None:
        self.running = False
        try:
            if self.file_handle:
                self.file_handle.close()
        except Exception:
            pass
        self.file_handle = None
