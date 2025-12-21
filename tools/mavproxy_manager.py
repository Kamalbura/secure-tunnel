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
import os
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

    def start(self, master_str_or_listen_host, master_baud_or_listen_port, out_ip=None, out_port=None, extra_args=None) -> bool:
        """Start mavproxy.

        New interface:
            start(master_str, master_baud, out_ip, out_port, extra_args=None)

        Backwards compatible with old calls:
            start(listen_host, listen_port, peer_host, peer_port)

        Returns True on success, False on failure.
        """
        # Backwards compatibility: old callers passed (listen_host, listen_port, peer_host, peer_port)
        if out_ip is None and out_port is None:
            # interpret as old-style
            listen_host = str(master_str_or_listen_host)
            listen_port = int(master_baud_or_listen_port)
            peer_host = None
            peer_port = None
            # We'll require caller to pass peer via extra_args in this case, but try to be helpful
            master_str = f"udpin:{listen_host}:{listen_port}"
            out_ip = "127.0.0.1"
            out_port = listen_port  # fallback
        else:
            master_str = str(master_str_or_listen_host)

        master_baud = master_baud_or_listen_port

        if extra_args is None:
            extra_args = []

        # [MODIFIED BY AGENT] Robust cross-platform command builder
        # Determine configured binary or fallback name
        configured = CONFIG.get("MAVPROXY_BINARY")
        # Build base out argument
        out_arg = f"udp:{out_ip}:{int(out_port)}"

        # 1. Determine the path to the python interpreter currently running
        python_exe = sys.executable

        # 2. Find mavproxy.py relative to the python executable
        bin_dir = os.path.dirname(python_exe)
        mavproxy_script = os.path.join(bin_dir, "mavproxy.py")

        # 3. Fallbacks
        if os.path.exists(mavproxy_script):
            base_cmd = [python_exe, mavproxy_script]
        elif configured and _Path(str(configured)).exists() and str(configured).lower().endswith(".py"):
            # If CONFIG points to an explicit .py file, use it via sys.executable
            base_cmd = [python_exe, str(configured)]
        elif sys.platform.startswith("win"):
            # Windows fallback: run as module
            base_cmd = [python_exe, "-m", "MAVProxy.mavproxy"]
        else:
            # Linux / general fallback: rely on executable in PATH
            base_cmd = ["mavproxy.py"]

        # 4. Construct full command with master/out and recommended flags
        cmd = base_cmd + [f"--master={master_str}", f"--out={out_arg}", "--dialect=ardupilotmega", "--nowait"]

        # append any extra args verbatim
        if extra_args:
            cmd.extend(extra_args)

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
