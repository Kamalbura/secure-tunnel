"""TCP JSON control server for core proxy.

This is intentionally small and dependency-free. It exists to bridge external
controllers/schedulers that speak the legacy TCP JSON protocol:

  {"cmd": "rekey", "suite": "cs-..."}

into the core in-band control plane (policy_engine.request_prepare).

Security model:
- The listener is expected to bind on a trusted interface.
- Commands are accepted only from an allow-list of peer IPs.
- Rekey commands are further restricted: only the drone host may initiate rekey.

This module must never log secrets.
"""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from core.logging_utils import get_logger
from core.policy_engine import ControlState, coordinator_role_from_config, is_coordinator, request_prepare
from core.suites import get_suite


_logger = get_logger("pqc")


@dataclass(frozen=True)
class ControlTcpConfig:
    host: str
    port: int
    allowed_peers: tuple[str, ...]
    rekey_allowed_peers: tuple[str, ...]
    role: str
    coordinator_role: str


class ControlTcpServer:
    """A small threaded TCP server that reads newline-delimited JSON."""

    def __init__(
        self,
        config: ControlTcpConfig,
        control_state: ControlState,
        *,
        quiet: bool = False,
    ) -> None:
        self._cfg = config
        self._state = control_state
        self._quiet = quiet
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self._cfg.host, self._cfg.port))
            srv.listen(8)
            srv.settimeout(0.5)
            self._sock = srv
        except OSError as exc:
            _logger.warning(
                "TCP control listener failed to start",
                extra={
                    "role": self._cfg.role,
                    "host": self._cfg.host,
                    "port": self._cfg.port,
                    "error": str(exc),
                },
            )
            return False

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        if not self._quiet:
            _logger.info(
                "TCP control listener started",
                extra={
                    "role": self._cfg.role,
                    "host": self._cfg.host,
                    "port": self._cfg.port,
                    "allowed_peers": list(self._cfg.allowed_peers),
                },
            )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as exc:
                # Defensive: keep listener alive; do not log secrets.
                _logger.debug(
                    "TCP control accept loop error",
                    extra={"role": self._cfg.role, "error": str(exc)},
                )
                continue

            t = threading.Thread(target=self._client_loop, args=(conn, addr), daemon=True)
            t.start()

    def _client_loop(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        peer_ip = addr[0]
        try:
            conn.settimeout(5.0)
            with conn:
                if not _is_allowed_peer(peer_ip, self._cfg.allowed_peers):
                    _send_json(conn, {"ok": False, "error": "unauthorized"})
                    return

                # Read line-by-line using raw socket recv to avoid buffering issues
                buf = b""
                while True:
                    if self._stop.is_set():
                        return
                    try:
                        chunk = conn.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        # EOF reached
                        return
                    buf += chunk
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            _send_json(conn, {"ok": False, "error": "bad_json"})
                            continue
                        if not isinstance(msg, dict):
                            _send_json(conn, {"ok": False, "error": "bad_message"})
                            continue
                        try:
                            resp = self._handle_message(msg, peer_ip)
                        except Exception as exc:
                            _logger.warning(
                                "TCP control _handle_message exception",
                                extra={"role": self._cfg.role, "peer": peer_ip, "error": str(exc), "cmd": msg.get("cmd")},
                            )
                            resp = {"ok": False, "error": f"internal_error:{type(exc).__name__}"}
                        _send_json(conn, resp)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _logger.debug(
                "TCP control client loop socket/parse error",
                extra={"role": self._cfg.role, "peer": peer_ip, "error": str(exc)},
            )
            return
        except Exception as exc:
            _logger.warning(
                "TCP control client loop error",
                extra={"role": self._cfg.role, "peer": peer_ip, "error": str(exc)},
            )
            return

    def _handle_message(self, msg: dict, peer_ip: str) -> dict:
        cmd = msg.get("cmd")
        if not isinstance(cmd, str):
            return {"ok": False, "error": "missing_cmd"}

        cmd_lower = cmd.lower().strip()

        # Log command receipt for debugging
        _logger.debug(
            "TCP control received command",
            extra={"role": self._cfg.role, "peer": peer_ip, "cmd": cmd_lower},
        )

        if cmd_lower in {"ping", "health"}:
            return {"ok": True, "role": self._cfg.role, "coordinator_role": self._cfg.coordinator_role}

        if cmd_lower == "status":
            with self._state.lock:
                return {
                    "ok": True,
                    "role": self._cfg.role,
                    "state": self._state.state,
                    "suite": self._state.current_suite,
                    "stats": dict(self._state.stats),
                    "active_rid": self._state.active_rid,
                    "last_rekey_ms": self._state.last_rekey_ms,
                    "last_rekey_suite": self._state.last_rekey_suite,
                    "last_status": self._state.last_status,
                }

        if cmd_lower == "rekey":
            if not _is_allowed_rekey_peer(
                peer_ip,
                rekey_allowed_peers=self._cfg.rekey_allowed_peers,
                server_role=self._cfg.role,
            ):
                return {"ok": False, "error": "unauthorized_rekey"}
            if not is_coordinator(role=self._cfg.role, coordinator_role=self._cfg.coordinator_role):
                return {"ok": False, "error": "coordinator_only", "coordinator_role": self._cfg.coordinator_role}
            suite = msg.get("suite")
            if not isinstance(suite, str) or not suite.strip():
                return {"ok": False, "error": "missing_suite"}
            try:
                suite_dict = get_suite(suite)
                suite_id = suite_dict.get("suite_id") if isinstance(suite_dict, dict) else None
                if not isinstance(suite_id, str) or not suite_id.strip():
                    return {"ok": False, "error": "invalid_suite"}
                rid = request_prepare(self._state, suite_id)
                return {"ok": True, "rid": rid, "suite": suite_id}
            except RuntimeError as exc:
                return {"ok": False, "error": f"busy:{exc}"}
            except Exception as exc:
                _logger.debug(
                    "TCP control rekey failed",
                    extra={
                        "role": self._cfg.role,
                        "peer": peer_ip,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                return {"ok": False, "error": f"rekey_failed:{type(exc).__name__}"}

        return {"ok": False, "error": "unknown_cmd"}


def _send_json(conn: socket.socket, payload: dict) -> None:
    try:
        data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        data = "{\"ok\":false,\"error\":\"encode_fail\"}"
    try:
        conn.sendall((data + "\n").encode("utf-8", errors="replace"))
    except OSError:
        pass


def _is_allowed_peer(peer_ip: str, allowed_peers: Iterable[str]) -> bool:
    for allowed in allowed_peers:
        if peer_ip == allowed:
            return True
    # Always allow loopback.
    return peer_ip in {"127.0.0.1", "::1"}


def _is_allowed_rekey_peer(*, peer_ip: str, rekey_allowed_peers: Iterable[str], server_role: str) -> bool:
    """Return True if this peer may request cmd=rekey.

    Policy:
    - Only the drone host(s) may initiate rekey.
    - Additionally allow loopback only when the control listener runs on the drone itself,
      so local drone tooling can drive rekeys without exposing that power to the GCS host.
    """

    for allowed in rekey_allowed_peers:
        if peer_ip == allowed:
            return True

    if server_role == "drone" and peer_ip in {"127.0.0.1", "::1"}:
        return True
    return False


def build_allowed_peers(*, cfg: dict) -> tuple[str, ...]:
    """Build peer allow-list from CONFIG.

    Includes LAN + tailscale endpoints when present.
    """

    peers: list[str] = []
    for key in (
        "DRONE_HOST",
        "GCS_HOST",
        "DRONE_HOST_LAN",
        "GCS_HOST_LAN",
        "DRONE_HOST_TAILSCALE",
        "GCS_HOST_TAILSCALE",
    ):
        value = cfg.get(key)
        if isinstance(value, str) and value and value not in peers:
            peers.append(value)
    return tuple(peers)


def build_rekey_allowed_peers(*, cfg: dict) -> tuple[str, ...]:
    """Build allow-list for cmd=rekey.

    Restrict to drone endpoints only.
    """

    peers: list[str] = []
    for key in (
        "DRONE_HOST",
        "DRONE_HOST_LAN",
        "DRONE_HOST_TAILSCALE",
    ):
        value = cfg.get(key)
        if isinstance(value, str) and value and value not in peers:
            peers.append(value)
    return tuple(peers)


def start_control_server_if_enabled(
    *,
    role: str,
    cfg: dict,
    control_state: ControlState,
    quiet: bool,
    enabled: bool,
) -> Optional[ControlTcpServer]:
    if not enabled:
        return None

    host_key = "GCS_CONTROL_HOST" if role == "gcs" else "DRONE_CONTROL_HOST"
    port_key = "GCS_CONTROL_PORT" if role == "gcs" else "DRONE_CONTROL_PORT"
    host = str(cfg.get(host_key) or "0.0.0.0")
    port = int(cfg.get(port_key) or 48080)

    coordinator_role = coordinator_role_from_config(cfg)

    server = ControlTcpServer(
        ControlTcpConfig(
            host=host,
            port=port,
            allowed_peers=build_allowed_peers(cfg=cfg),
            rekey_allowed_peers=build_rekey_allowed_peers(cfg=cfg),
            role=role,
            coordinator_role=coordinator_role,
        ),
        control_state,
        quiet=quiet,
    )
    if not server.start():
        return None
    return server
