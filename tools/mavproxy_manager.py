#!/usr/bin/env python3
"""Shared MavProxyManager for launching mavproxy subprocesses.

Keeps a minimal API: `start(listen_host, listen_port, peer_host, peer_port) -> bool`,
`stop()`, and `is_running()`.
"""
from pathlib import Path
import time
import subprocess
from typing import Optional
import sys
from pathlib import Path as _Path

from core.config import CONFIG


ROOT = Path(__file__).resolve().parents[1]

def _logs_dir_for(role: str) -> Path:
    d = ROOT / "logs" / "sscheduler" / role
    d.mkdir(parents=True, exist_ok=True)
    return d


class MavProxyManager:
    def __init__(self, role: str = "generic") -> None:
        self.role = role
        self.process: Optional[subprocess.Popen] = None
        self._last_log: Optional[Path] = None

    def start(self, listen_host: str, listen_port: int, peer_host: str, peer_port: int) -> bool:
        """Start a mavproxy subprocess that listens on UDP and forwards to peer.

        Returns True if the process started and is running; False on failure.
        """
        if self.process and self.process.poll() is None:
            self.stop()

        binary = str(CONFIG.get("MAVPROXY_BINARY") or "mavproxy.py")
        listen = f"udp:{listen_host}:{int(listen_port)}"
        out = f"udp:{peer_host}:{int(peer_port)}"

        # If the configured binary is an explicit Python script path, run it
        # via the current Python interpreter to ensure correct venv.
        bin_path = _Path(binary)
        if bin_path.exists() and bin_path.suffix.lower() == ".py":
            cmd = [sys.executable, str(bin_path), "--master", listen, "--out", out, "--heartbeat", "--console", "none"]
        else:
            cmd = [binary, "--master", listen, "--out", out, "--heartbeat", "--console", "none"]

        log_dir = _logs_dir_for(self.role)
        ts_now = time.strftime("%Y%m%d-%H%M%S")
        log_path = log_dir / f"mavproxy_{self.role}_{ts_now}.log"
        try:
            log_fh = open(log_path, "w", encoding="utf-8")
        except Exception:
            log_fh = subprocess.DEVNULL  # type: ignore[arg-type]

        try:
            self.process = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, text=True)
            self._last_log = log_path
            # small pause to let process initialize
            time.sleep(0.5)
            if self.process.poll() is not None:
                return False
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def stop(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def last_log(self) -> Optional[Path]:
        return self._last_log
