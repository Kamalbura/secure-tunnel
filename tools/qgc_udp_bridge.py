#!/usr/bin/env python3
"""Bidirectional UDP bridge between QGroundControl and the local plaintext proxy ports.

Why this exists:
- MAVProxy is great for serial<->UDP, but on the GCS it is easy to accidentally
  create feedback loops if you "--out" back into the same tunnel ports.
- QGC wants a simple UDP endpoint; the secure-tunnel proxy wants two ports:
  - GCS_PLAINTEXT_TX: packets *from* GCS app into proxy (uplink)
  - GCS_PLAINTEXT_RX: packets *to* GCS app from proxy (downlink)

This bridge explicitly forwards:
- QGC -> proxy TX
- proxy RX -> last-seen QGC address

It is intentionally dumb (raw UDP datagrams); MAVLink framing stays untouched.
"""

from __future__ import annotations

import argparse
import select
import socket
import sys
import time
from typing import Optional, Tuple


Addr = Tuple[str, int]


def _make_udp_server(bind_host: str, bind_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception:
        pass
    sock.bind((bind_host, bind_port))
    sock.setblocking(False)
    return sock


def _make_udp_client() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    return sock


def run_bridge(
    *,
    qgc_target: Addr,
    bridge_bind: Addr,
    proxy_rx_bind: Addr,
    proxy_tx: Addr,
    log_every_s: float = 5.0,
) -> int:
    # The bridge must NOT bind to QGC's listen port (14550 by default), otherwise
    # QGC can't start. Instead we:
    # - bind the bridge on a separate port (14551 by default)
    # - forward proxy->QGC to QGC's actual listen port
    # QGC will respond back to the bridge's source port automatically.
    bridge_sock = _make_udp_server(*bridge_bind)
    proxy_rx_sock = _make_udp_server(*proxy_rx_bind)
    proxy_tx_sock = _make_udp_client()
    qgc_tx_sock = _make_udp_client()

    last_qgc_peer: Optional[Addr] = None

    qgc_to_proxy_pkts = 0
    proxy_to_qgc_pkts = 0
    qgc_to_proxy_bytes = 0
    proxy_to_qgc_bytes = 0

    last_log = time.time()

    try:
        while True:
            readable, _, _ = select.select([bridge_sock, proxy_rx_sock], [], [], 0.25)
            for sock in readable:
                if sock is bridge_sock:
                    try:
                        data, addr = bridge_sock.recvfrom(65535)
                    except BlockingIOError:
                        continue
                    if not data:
                        continue
                    last_qgc_peer = (addr[0], int(addr[1]))
                    try:
                        proxy_tx_sock.sendto(data, proxy_tx)
                        qgc_to_proxy_pkts += 1
                        qgc_to_proxy_bytes += len(data)
                    except BlockingIOError:
                        # best-effort; drop
                        pass
                else:
                    try:
                        data, _addr = proxy_rx_sock.recvfrom(65535)
                    except BlockingIOError:
                        continue
                    if not data:
                        continue
                    try:
                        # Always forward to QGC's listen port.
                        qgc_tx_sock.sendto(data, qgc_target)
                        proxy_to_qgc_pkts += 1
                        proxy_to_qgc_bytes += len(data)
                    except BlockingIOError:
                        pass

            now = time.time()
            if log_every_s > 0 and (now - last_log) >= log_every_s:
                last_log = now
                sys.stdout.write(
                    f"[qgc-bridge] qgc->proxy {qgc_to_proxy_pkts} pkts {qgc_to_proxy_bytes} bytes | "
                    f"proxy->qgc {proxy_to_qgc_pkts} pkts {proxy_to_qgc_bytes} bytes | "
                    f"qgc_peer={last_qgc_peer} qgc_target={qgc_target} bridge_bind={bridge_bind}\n"
                )
                sys.stdout.flush()
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            bridge_sock.close()
        except Exception:
            pass
        try:
            proxy_rx_sock.close()
        except Exception:
            pass
        try:
            proxy_tx_sock.close()
        except Exception:
            pass
        try:
            qgc_tx_sock.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Bidirectional UDP bridge between QGC and secure-tunnel plaintext ports")
    ap.add_argument("--qgc-host", default="127.0.0.1")
    ap.add_argument("--qgc-port", type=int, default=14550, help="QGC listen port (default: 14550)")
    ap.add_argument("--bridge-bind-host", default="127.0.0.1")
    ap.add_argument("--bridge-port", type=int, default=14551, help="Bridge bind port (default: 14551)")
    ap.add_argument("--proxy-rx-bind-host", default="127.0.0.1")
    ap.add_argument("--proxy-rx-port", type=int, default=47002, help="GCS_PLAINTEXT_RX (proxy -> app)")
    ap.add_argument("--proxy-tx-host", default="127.0.0.1")
    ap.add_argument("--proxy-tx-port", type=int, default=47001, help="GCS_PLAINTEXT_TX (app -> proxy)")
    ap.add_argument("--log-every", type=float, default=5.0)
    args = ap.parse_args()

    return run_bridge(
        qgc_target=(args.qgc_host, args.qgc_port),
        bridge_bind=(args.bridge_bind_host, args.bridge_port),
        proxy_rx_bind=(args.proxy_rx_bind_host, args.proxy_rx_port),
        proxy_tx=(args.proxy_tx_host, args.proxy_tx_port),
        log_every_s=float(args.log_every),
    )


if __name__ == "__main__":
    raise SystemExit(main())
