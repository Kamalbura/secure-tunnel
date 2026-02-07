"""
mDNS / Zeroconf discovery for drone and GCS endpoints.

Uses the ``zeroconf`` library (pure Python) to:
  1. *Advertise* a service (drone or GCS) on the local network.
  2. *Resolve* ``drone.local`` / ``gcs.local`` hostnames to IP addresses.

This replaces hardcoded LAN IPs when both endpoints run mDNS.  Falls back
gracefully to the static IPs from .denv/.genv when zeroconf is unavailable
or resolution times out.

Usage
-----
>>> from core.mdns import resolve_drone, resolve_gcs, advertise_service
>>> ip = resolve_drone(timeout=3.0)            # -> "192.168.0.100" or None
>>> ip = resolve_gcs(timeout=3.0)              # -> "192.168.0.101" or None
>>> close_fn = advertise_service("drone", 46000)  # advertise _pqc._udp on port
>>> close_fn()                                  # stop advertising
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency — degrade gracefully when zeroconf is not installed
# ---------------------------------------------------------------------------
try:
    from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf, IPVersion
    _HAS_ZEROCONF = True
except ImportError:
    _HAS_ZEROCONF = False

# mDNS service type registered for the PQC secure tunnel.
SERVICE_TYPE = "_pqc-tunnel._udp.local."


# ---------------------------------------------------------------------------
# Hostname resolution  (drone.local / gcs.local)
# ---------------------------------------------------------------------------

def _resolve_mdns_hostname(hostname: str, timeout: float = 3.0) -> Optional[str]:
    """
    Resolve a ``.local`` hostname via mDNS (multicast DNS).

    Attempts socket-level resolution first (works on Linux/macOS with
    avahi / Bonjour). If that fails and zeroconf is installed, performs
    a service browse as a fallback.
    """
    # 1. Try native socket resolution (fastest, uses OS mDNS stack)
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_DGRAM)
        if results:
            ip = results[0][4][0]
            logger.debug("mDNS resolved %s → %s (socket)", hostname, ip)
            return ip
    except (socket.gaierror, OSError):
        pass

    # 2. Fallback: use python-zeroconf library for explicit multicast query
    if _HAS_ZEROCONF:
        try:
            zc = Zeroconf(ip_version=IPVersion.V4Only)
            try:
                info = zc.get_service_info(
                    SERVICE_TYPE,
                    f"{hostname.replace('.local', '')}.{SERVICE_TYPE}",
                    timeout=int(timeout * 1000),
                )
                if info and info.parsed_addresses():
                    ip = info.parsed_addresses()[0]
                    logger.debug("mDNS resolved %s → %s (zeroconf)", hostname, ip)
                    return ip
            finally:
                zc.close()
        except Exception as exc:
            logger.debug("zeroconf resolution failed for %s: %s", hostname, exc)

    logger.debug("mDNS resolution failed for %s", hostname)
    return None


def resolve_drone(
    timeout: float = 3.0,
    fallback: Optional[str] = None,
) -> Optional[str]:
    """Resolve ``drone.local`` → IP address, with optional static fallback."""
    if fallback is None:
        fallback = os.getenv("DRONE_HOST_LAN")
    ip = _resolve_mdns_hostname("drone.local", timeout=timeout)
    if ip:
        return ip
    if fallback:
        logger.info("mDNS unavailable for drone.local — falling back to %s", fallback)
    return fallback


def resolve_gcs(
    timeout: float = 3.0,
    fallback: Optional[str] = None,
) -> Optional[str]:
    """Resolve ``gcs.local`` → IP address, with optional static fallback."""
    if fallback is None:
        fallback = os.getenv("GCS_HOST_LAN")
    ip = _resolve_mdns_hostname("gcs.local", timeout=timeout)
    if ip:
        return ip
    if fallback:
        logger.info("mDNS unavailable for gcs.local — falling back to %s", fallback)
    return fallback


# ---------------------------------------------------------------------------
# Service advertisement (register this host as drone / gcs)
# ---------------------------------------------------------------------------

def advertise_service(
    role: str,
    port: int,
    *,
    properties: Optional[dict[str, str]] = None,
) -> Callable[[], None]:
    """
    Advertise this host as a ``drone`` or ``gcs`` PQC tunnel endpoint.

    Parameters
    ----------
    role : str
        ``"drone"`` or ``"gcs"``.
    port : int
        Primary port number to advertise (e.g. 46000 for handshake).
    properties : dict, optional
        Extra TXT record properties (e.g. ``{"version": "1.0"}``).

    Returns
    -------
    Callable
        A zero-arg function that stops advertising (unregisters the service).
        Call this on shutdown.

    Raises
    ------
    RuntimeError
        If ``zeroconf`` is not installed.
    """
    if not _HAS_ZEROCONF:
        raise RuntimeError(
            "python-zeroconf is required for mDNS advertising.  "
            "Install it with:  pip install zeroconf"
        )

    role = role.lower()
    if role not in ("drone", "gcs"):
        raise ValueError(f"role must be 'drone' or 'gcs', got {role!r}")

    hostname = socket.gethostname()
    # Attempt to get local LAN IP for the service record
    local_ip = _get_local_ip()

    props = {"role": role, "host": hostname}
    if properties:
        props.update(properties)

    info = ServiceInfo(
        SERVICE_TYPE,
        name=f"{role}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(local_ip)] if local_ip else [],
        port=port,
        properties={k: v.encode() for k, v in props.items()},
        server=f"{role}.local.",
    )

    zc = Zeroconf(ip_version=IPVersion.V4Only)
    zc.register_service(info)
    logger.info("mDNS: advertising %s.local on %s:%d", role, local_ip or "?", port)

    def _close() -> None:
        try:
            zc.unregister_service(info)
        except Exception:
            pass
        zc.close()
        logger.info("mDNS: stopped advertising %s.local", role)

    return _close


def _get_local_ip() -> Optional[str]:
    """Best-effort detection of the local LAN IP address."""
    try:
        # Connect to a non-routable address to discover the default interface IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except Exception:
        return None
