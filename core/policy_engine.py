"""
In-band control-plane state machine for interactive rekey negotiation.

Implements a two-phase commit protocol carried over packet type 0x02 payloads.
"""

from __future__ import annotations

import queue
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


MSG_TYPE_TELEMETRY_REPORT = "telemetry_report"


def _now_ms() -> int:
    """Return monotonic milliseconds for control timestamps."""

    return time.monotonic_ns() // 1_000_000


def _default_safe() -> bool:
    return True


@dataclass
class ControlState:
    """Mutable control-plane state shared between proxy threads."""

    role: str
    coordinator_role: str
    current_suite: str
    safe_guard: Callable[[], bool] = field(default_factory=_default_safe)
    lock: threading.Lock = field(default_factory=threading.Lock)
    outbox: "queue.Queue[dict]" = field(default_factory=queue.Queue)
    pending: Dict[str, str] = field(default_factory=dict)
    state: str = "RUNNING"
    active_rid: Optional[str] = None
    last_rekey_ms: Optional[int] = None
    last_rekey_suite: Optional[str] = None
    last_status: Optional[Dict[str, object]] = None
    last_telemetry: Optional[Dict[str, object]] = None
    stats: Dict[str, int] = field(default_factory=lambda: {
        "prepare_sent": 0,
        "prepare_received": 0,
        "rekeys_ok": 0,
        "rekeys_fail": 0,
    })
    seen_rids: deque[str] = field(default_factory=lambda: deque(maxlen=256))


@dataclass
class ControlResult:
    """Outcome of processing a control message."""

    send: List[dict] = field(default_factory=list)
    start_handshake: Optional[Tuple[str, str]] = None  # (suite_id, rid)
    notes: List[str] = field(default_factory=list)


def create_control_state(role: str, suite_id: str, *, safe_guard: Callable[[], bool] | None = None) -> ControlState:
    """Initialise ControlState with the provided role and suite."""

    guard = safe_guard or _default_safe
    return ControlState(role=role, coordinator_role="gcs", current_suite=suite_id, safe_guard=guard)


def set_coordinator_role(state: ControlState, coordinator_role: str) -> None:
    """Set the coordinator role for the in-band rekey control-plane.

    coordinator_role must be either "gcs" or "drone".
    """

    role_norm = str(coordinator_role).strip().lower()
    if role_norm not in {"gcs", "drone"}:
        raise ValueError("invalid coordinator_role")
    with state.lock:
        state.coordinator_role = role_norm


def normalize_coordinator_role(value: object, *, default: str = "gcs") -> str:
    """Normalize coordinator roles to a safe value.

    Accepts arbitrary inputs and returns either "gcs" or "drone".
    """

    try:
        role_norm = str(value).strip().lower()
    except Exception:
        role_norm = ""

    if role_norm in {"gcs", "drone"}:
        return role_norm
    return "gcs" if default not in {"gcs", "drone"} else default


def coordinator_role_from_config(cfg: dict, *, default: str = "gcs") -> str:
    """Fetch and normalize CONTROL_COORDINATOR_ROLE from a config mapping."""

    if not isinstance(cfg, dict):
        return normalize_coordinator_role(default, default="gcs")
    return normalize_coordinator_role(cfg.get("CONTROL_COORDINATOR_ROLE", default), default=default)


def is_coordinator(*, role: str, coordinator_role: str) -> bool:
    """Return True if this proxy role is the coordinator role."""

    return normalize_coordinator_role(role) == normalize_coordinator_role(coordinator_role)


def generate_rid() -> str:
    """Generate a random 64-bit hex request identifier."""

    return secrets.token_hex(8)


def enqueue_json(state: ControlState, payload: dict) -> None:
    """Place an outbound JSON payload onto the control outbox."""

    state.outbox.put(payload)


def request_prepare(state: ControlState, suite_id: str) -> str:
    """Queue a prepare_rekey message and transition to NEGOTIATING."""

    rid = generate_rid()
    now = _now_ms()
    with state.lock:
        if state.state != "RUNNING":
            raise RuntimeError("control-plane already negotiating")
        state.pending[rid] = suite_id
        state.active_rid = rid
        state.state = "NEGOTIATING"
        state.stats["prepare_sent"] += 1
    enqueue_json(
        state,
        {
            "type": "prepare_rekey",
            "suite": suite_id,
            "rid": rid,
            "t_ms": now,
        },
    )
    return rid


def record_rekey_result(state: ControlState, rid: str, suite_id: str, *, success: bool) -> None:
    """Record outcome of a rekey attempt and enqueue status update."""

    now = _now_ms()
    status_payload = {
        "type": "status",
        "state": "RUNNING",
        "suite": suite_id if success else state.current_suite,
        "rid": rid,
        "result": "ok" if success else "fail",
        "t_ms": now,
    }
    with state.lock:
        if success:
            state.current_suite = suite_id
            state.last_rekey_suite = suite_id
            state.last_rekey_ms = now
            state.stats["rekeys_ok"] += 1
        else:
            state.stats["rekeys_fail"] += 1
        state.pending.pop(rid, None)
        state.active_rid = None
        state.state = "RUNNING"
    enqueue_json(state, status_payload)


def handle_control(msg: dict, role: str, state: ControlState) -> ControlResult:
    """Process inbound control JSON and return actions for the proxy."""

    result = ControlResult()
    msg_type = msg.get("type")
    if not isinstance(msg_type, str):
        result.notes.append("missing_type")
        return result

    if msg_type == MSG_TYPE_TELEMETRY_REPORT:
        # Telemetry reports may be sent by either side, but are primarily intended
        # for follower (GCS) -> controller (drone) feedback.
        payload = msg.get("metrics")
        with state.lock:
            state.last_telemetry = payload if isinstance(payload, dict) else msg
        return result

    rid = msg.get("rid")
    now = _now_ms()

    coordinator_role = state.coordinator_role
    is_coordinator = role == coordinator_role

    if is_coordinator:
        if msg_type == "prepare_ok" and isinstance(rid, str):
            with state.lock:
                suite = state.pending.get(rid)
                if not suite:
                    result.notes.append("unknown_rid")
                    return result
                state.state = "SWAPPING"
                state.seen_rids.append(rid)
            result.send.append({
                "type": "commit_rekey",
                "suite": suite,
                "rid": rid,
                "t_ms": now,
            })
            result.start_handshake = (suite, rid)
        elif msg_type == "prepare_fail" and isinstance(rid, str):
            reason = msg.get("reason", "unknown")
            with state.lock:
                state.pending.pop(rid, None)
                state.active_rid = None
                state.state = "RUNNING"
                state.stats["rekeys_fail"] += 1
                state.seen_rids.append(rid)
            result.notes.append(f"prepare_fail:{reason}")
        elif msg_type == "status":
            with state.lock:
                state.last_status = msg
        else:
            result.notes.append(f"ignored:{msg_type}")
        return result

    if msg_type == "prepare_rekey":
        suite = msg.get("suite")
        if not isinstance(rid, str) or not isinstance(suite, str):
            result.notes.append("invalid_prepare")
            return result

        with state.lock:
            if rid in state.seen_rids:
                allow = False
            else:
                allow = state.state == "RUNNING" and state.safe_guard()
            if allow:
                state.pending[rid] = suite
                state.active_rid = rid
                state.state = "NEGOTIATING"
                state.stats["prepare_received"] += 1
                state.seen_rids.append(rid)
        if allow:
            result.send.append({
                "type": "prepare_ok",
                "rid": rid,
                "t_ms": now,
            })
        else:
            result.send.append({
                "type": "prepare_fail",
                "rid": rid,
                "reason": "unsafe",
                "t_ms": now,
            })
    elif msg_type == "commit_rekey" and isinstance(rid, str):
        with state.lock:
            suite = state.pending.get(rid)
            if not suite:
                result.notes.append("unknown_commit_rid")
                return result
            state.state = "SWAPPING"
        result.start_handshake = (suite, rid)
    elif msg_type == "status":
        with state.lock:
            state.last_status = msg
    else:
        result.notes.append(f"ignored:{msg_type}")

    return result