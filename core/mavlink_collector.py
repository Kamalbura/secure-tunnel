#!/usr/bin/env python3
"""
MAVLink Metrics Collector
core/mavlink_collector.py

Collects bidirectional MAVLink communication metrics for both GCS and Drone sides.
Provides message-level tracking, heartbeat monitoring, sequence gap detection,
and command latency measurement.

Usage:
    from core.mavlink_collector import MavLinkMetricsCollector
    
    collector = MavLinkMetricsCollector(role="gcs")
    collector.start_sniffing(port=14552)
    # ... run benchmark ...
    metrics = collector.get_metrics()
"""

import os
import sys
import time
import json
import socket
import struct
import threading
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

try:
    from pymavlink import mavutil
    HAS_PYMAVLINK = True
except ImportError:
    HAS_PYMAVLINK = False


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class MavLinkMessageStats:
    """Statistics for a single MAVLink message type."""
    msg_id: int = 0
    msg_name: str = ""
    count_tx: int = 0
    count_rx: int = 0
    first_seen_mono: float = 0.0
    last_seen_mono: float = 0.0
    avg_interval_ms: float = 0.0
    size_bytes: int = 0


@dataclass
class HeartbeatStats:
    """Heartbeat-specific tracking."""
    count: int = 0
    expected_count: int = 0
    loss_count: int = 0
    last_time_mono: float = 0.0
    avg_interval_ms: float = 0.0
    interval_samples: List[float] = field(default_factory=list)
    sysid: int = 0
    compid: int = 0
    mode: int = 0
    armed: bool = False


@dataclass
class CommandStats:
    """Command/ACK tracking."""
    cmd_sent: int = 0
    cmd_ack_received: int = 0
    ack_pending: Dict[int, float] = field(default_factory=dict)  # cmd_id -> send_time
    latency_samples: List[float] = field(default_factory=list)


@dataclass
class SequenceStats:
    """MAVLink sequence number tracking."""
    last_seq: Dict[int, int] = field(default_factory=dict)  # sysid -> last_seq
    gaps: int = 0
    duplicates: int = 0
    out_of_order: int = 0


# =============================================================================
# MAVLINK METRICS COLLECTOR
# =============================================================================

class MavLinkMetricsCollector:
    """
    Collects comprehensive MAVLink metrics for benchmark analysis.
    
    Tracks:
    - Message rates (tx/rx per second)
    - Message type counts
    - Heartbeat intervals and losses
    - Sequence gaps/duplicates
    - Command acknowledgement latency
    - CRC errors and decode failures
    """
    
    def __init__(self, role: str = "auto"):
        """
        Initialize collector.
        
        Args:
            role: "gcs" or "drone" - determines which metrics to collect
        """
        self.role = role if role != "auto" else self._detect_role()
        
        # Connection
        self._mav_conn = None
        self._sock = None
        self._sniff_port = 0
        
        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Timing
        self._start_time_mono = 0.0
        self._end_time_mono = 0.0
        
        # Message tracking
        self._msg_stats: Dict[int, MavLinkMessageStats] = {}
        self._total_rx = 0
        self._total_tx = 0
        self._total_bytes_rx = 0
        self._total_bytes_tx = 0
        
        # Heartbeat tracking
        self._heartbeat = HeartbeatStats()
        self._last_heartbeat_mono = 0.0
        self._heartbeat_intervals: List[float] = []
        
        # Command tracking
        self._commands = CommandStats()
        
        # Sequence tracking
        self._sequences = SequenceStats()
        
        # Error tracking
        self._crc_errors = 0
        self._decode_errors = 0
        self._msg_drops = 0
        
        # Latency tracking (for timestamped messages)
        self._latency_samples: List[float] = []
        
        # Raw message log (bounded)
        self._msg_log: deque = deque(maxlen=10000)
        
        # Protocol info
        self._protocol_version = ""
        
    def _detect_role(self) -> str:
        """Detect role from platform."""
        import platform
        machine = platform.machine().lower()
        if "arm" in machine or "aarch" in machine:
            return "drone"
        return "gcs"
    
    def start_sniffing(self, port: int = 14552, host: str = "127.0.0.1"):
        """
        Start sniffing MAVLink traffic on a UDP port.
        
        For GCS: sniff MAVProxy's duplicate output port (e.g., 14552)
        For Drone: sniff the proxy's plaintext output
        """
        if self._running:
            return
        
        self._sniff_port = port
        self._start_time_mono = time.monotonic()
        self._running = True
        
        self._thread = threading.Thread(
            target=self._sniff_loop,
            args=(host, port),
            daemon=True
        )
        self._thread.start()
    
    def stop(self) -> Dict[str, Any]:
        """Stop sniffing and return collected metrics."""
        if not self._running:
            return self.get_metrics()
        
        self._running = False
        self._end_time_mono = time.monotonic()
        
        if self._thread:
            self._thread.join(timeout=2.0)
        
        if self._sock:
            try:
                self._sock.close()
            except:
                pass
        
        if self._mav_conn:
            try:
                self._mav_conn.close()
            except:
                pass
        
        return self.get_metrics()
    
    def _sniff_loop(self, host: str, port: int):
        """Main sniffing loop."""
        # Try pymavlink first
        if HAS_PYMAVLINK:
            try:
                conn_str = f"udpin:{host}:{port}"
                self._mav_conn = mavutil.mavlink_connection(
                    conn_str,
                    source_system=255,
                    source_component=0
                )
                self._protocol_version = "MAVLink 2.0"
            except Exception as e:
                self._mav_conn = None
        
        # Fallback to raw socket
        if not self._mav_conn:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._sock.bind((host, port))
                self._sock.settimeout(0.1)
            except Exception as e:
                return
        
        while self._running:
            try:
                self._process_one()
            except Exception as e:
                time.sleep(0.01)
    
    def _process_one(self):
        """Process one MAVLink message."""
        now = time.monotonic()
        
        if self._mav_conn:
            msg = self._mav_conn.recv_match(blocking=True, timeout=0.1)
            if msg:
                self._handle_message(msg, now)
        elif self._sock:
            try:
                data, addr = self._sock.recvfrom(65535)
                if data:
                    self._handle_raw_packet(data, now)
            except socket.timeout:
                pass
    
    def _handle_message(self, msg, now: float):
        """Handle a parsed MAVLink message."""
        with self._lock:
            msg_type = msg.get_type()
            msg_id = msg.get_msgId()
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()
            
            # Skip BAD_DATA
            if msg_type == "BAD_DATA":
                self._decode_errors += 1
                return
            
            # Update total counts
            self._total_rx += 1
            
            # Estimate size
            size = 12  # MAVLink 2.0 header
            try:
                payload = msg.get_payload()
                if payload and isinstance(payload, (bytes, bytearray)):
                    size += len(payload)
            except:
                pass
            self._total_bytes_rx += size
            
            # Track message type
            if msg_id not in self._msg_stats:
                self._msg_stats[msg_id] = MavLinkMessageStats(
                    msg_id=msg_id,
                    msg_name=msg_type,
                    first_seen_mono=now
                )
            
            stats = self._msg_stats[msg_id]
            stats.count_rx += 1
            stats.last_seen_mono = now
            stats.size_bytes = size
            
            # Sequence tracking
            try:
                seq = msg.get_seq()
                self._track_sequence(sysid, seq)
            except:
                pass
            
            # Heartbeat tracking
            if msg_type == "HEARTBEAT":
                self._handle_heartbeat(msg, now)
            
            # Command ACK tracking
            elif msg_type == "COMMAND_ACK":
                self._handle_command_ack(msg, now)
            
            # Log message
            self._msg_log.append({
                "t": now,
                "id": msg_id,
                "type": msg_type,
                "sysid": sysid,
                "compid": compid,
            })
    
    def _handle_raw_packet(self, data: bytes, now: float):
        """Handle raw MAVLink packet (fallback without pymavlink)."""
        with self._lock:
            self._total_rx += 1
            self._total_bytes_rx += len(data)
            
            # Basic MAVLink v2 header parsing
            if len(data) >= 12 and data[0] == 0xFD:  # MAVLink 2.0
                payload_len = data[1]
                seq = data[4]
                sysid = data[5]
                compid = data[6]
                msg_id = struct.unpack("<I", data[7:10] + b"\x00")[0]
                
                self._track_sequence(sysid, seq)
                
                if msg_id not in self._msg_stats:
                    self._msg_stats[msg_id] = MavLinkMessageStats(
                        msg_id=msg_id,
                        msg_name=f"MSG_{msg_id}",
                        first_seen_mono=now
                    )
                
                self._msg_stats[msg_id].count_rx += 1
                self._msg_stats[msg_id].last_seen_mono = now
            
            elif len(data) >= 8 and data[0] == 0xFE:  # MAVLink 1.0
                payload_len = data[1]
                seq = data[2]
                sysid = data[3]
                compid = data[4]
                msg_id = data[5]
                
                self._track_sequence(sysid, seq)
    
    def _track_sequence(self, sysid: int, seq: int):
        """Track sequence numbers for gap detection."""
        if sysid in self._sequences.last_seq:
            expected = (self._sequences.last_seq[sysid] + 1) % 256
            if seq != expected:
                if seq == self._sequences.last_seq[sysid]:
                    self._sequences.duplicates += 1
                elif seq < expected and seq > self._sequences.last_seq[sysid] - 10:
                    self._sequences.out_of_order += 1
                else:
                    # Calculate gap
                    if seq > expected:
                        self._sequences.gaps += (seq - expected)
                    else:
                        self._sequences.gaps += (256 - expected + seq)
        
        self._sequences.last_seq[sysid] = seq
    
    def _handle_heartbeat(self, msg, now: float):
        """Handle heartbeat message."""
        self._heartbeat.count += 1
        self._heartbeat.sysid = msg.get_srcSystem()
        self._heartbeat.compid = msg.get_srcComponent()
        
        try:
            self._heartbeat.mode = msg.custom_mode
            if HAS_PYMAVLINK:
                self._heartbeat.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        except:
            pass
        
        # Calculate interval
        if self._last_heartbeat_mono > 0:
            interval_ms = (now - self._last_heartbeat_mono) * 1000.0
            self._heartbeat_intervals.append(interval_ms)
            
            # Detect lost heartbeats (expected ~1Hz)
            if interval_ms > 1500:  # > 1.5s gap
                expected_beats = int(interval_ms / 1000.0)
                self._heartbeat.loss_count += max(0, expected_beats - 1)
        
        self._last_heartbeat_mono = now
    
    def _handle_command_ack(self, msg, now: float):
        """Handle command acknowledgement."""
        self._commands.cmd_ack_received += 1
        
        # Try to match with pending command
        try:
            cmd_id = msg.command
            if cmd_id in self._commands.ack_pending:
                send_time = self._commands.ack_pending.pop(cmd_id)
                latency_ms = (now - send_time) * 1000.0
                self._commands.latency_samples.append(latency_ms)
        except:
            pass
    
    def record_command_sent(self, cmd_id: int):
        """Record that a command was sent (for latency tracking)."""
        with self._lock:
            self._commands.cmd_sent += 1
            self._commands.ack_pending[cmd_id] = time.monotonic()
    
    def record_tx_message(self, msg_id: int = 0, size: int = 0):
        """Record a transmitted message."""
        with self._lock:
            self._total_tx += 1
            self._total_bytes_tx += size
            
            if msg_id > 0:
                if msg_id not in self._msg_stats:
                    self._msg_stats[msg_id] = MavLinkMessageStats(
                        msg_id=msg_id,
                        first_seen_mono=time.monotonic()
                    )
                self._msg_stats[msg_id].count_tx += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive MAVLink metrics."""
        with self._lock:
            end_time = self._end_time_mono if self._end_time_mono > 0 else time.monotonic()
            duration_s = end_time - self._start_time_mono if self._start_time_mono > 0 else 1.0
            
            # Calculate rates
            rx_pps = self._total_rx / duration_s if duration_s > 0 else 0.0
            tx_pps = self._total_tx / duration_s if duration_s > 0 else 0.0
            
            # Heartbeat stats
            hb_interval_avg = 0.0
            if self._heartbeat_intervals:
                hb_interval_avg = sum(self._heartbeat_intervals) / len(self._heartbeat_intervals)
            
            # Expected heartbeats (1 Hz)
            expected_hb = int(duration_s)
            self._heartbeat.expected_count = expected_hb
            
            # Command latency stats
            cmd_latency_avg = 0.0
            cmd_latency_p95 = 0.0
            if self._commands.latency_samples:
                samples = sorted(self._commands.latency_samples)
                cmd_latency_avg = sum(samples) / len(samples)
                p95_idx = int(len(samples) * 0.95)
                cmd_latency_p95 = samples[min(p95_idx, len(samples) - 1)]
            
            # Message latency stats (if we have timestamped messages)
            msg_latency_avg = 0.0
            msg_latency_p95 = 0.0
            if self._latency_samples:
                samples = sorted(self._latency_samples)
                msg_latency_avg = sum(samples) / len(samples)
                p95_idx = int(len(samples) * 0.95)
                msg_latency_p95 = samples[min(p95_idx, len(samples) - 1)]
            
            # Message type counts
            msg_type_counts = {
                stats.msg_name: stats.count_rx
                for stats in self._msg_stats.values()
            }
            
            # Stream rate (messages per second, excluding heartbeat)
            non_hb_msgs = sum(
                stats.count_rx for stats in self._msg_stats.values()
                if stats.msg_name != "HEARTBEAT"
            )
            stream_rate = non_hb_msgs / duration_s if duration_s > 0 else 0.0
            
            return {
                # Basic counts
                "total_msgs_sent": self._total_tx,
                "total_msgs_received": self._total_rx,
                "total_bytes_sent": self._total_bytes_tx,
                "total_bytes_received": self._total_bytes_rx,
                
                # Rates
                "tx_pps": round(tx_pps, 2),
                "rx_pps": round(rx_pps, 2),
                "stream_rate_hz": round(stream_rate, 2),
                
                # Duration
                "start_time": self._start_time_mono,
                "end_time": end_time,
                "duration_s": round(duration_s, 3),
                
                # Message type breakdown
                "msg_type_counts": msg_type_counts,
                
                # Heartbeat
                "heartbeat_count": self._heartbeat.count,
                "heartbeat_expected": expected_hb,
                "heartbeat_loss_count": self._heartbeat.loss_count,
                "heartbeat_interval_ms": round(hb_interval_avg, 2),
                "heartbeat_sysid": self._heartbeat.sysid,
                "heartbeat_compid": self._heartbeat.compid,
                "heartbeat_armed": self._heartbeat.armed,
                "heartbeat_mode": self._heartbeat.mode,
                
                # Sequence tracking
                "seq_gap_count": self._sequences.gaps,
                "seq_duplicate_count": self._sequences.duplicates,
                "seq_out_of_order_count": self._sequences.out_of_order,
                
                # Command tracking
                "cmd_sent_count": self._commands.cmd_sent,
                "cmd_ack_received_count": self._commands.cmd_ack_received,
                "cmd_ack_latency_avg_ms": round(cmd_latency_avg, 2),
                "cmd_ack_latency_p95_ms": round(cmd_latency_p95, 2),
                
                # Errors
                "crc_error_count": self._crc_errors,
                "decode_error_count": self._decode_errors,
                "msg_drop_count": self._msg_drops,
                
                # Message latency (if available)
                "message_latency_avg_ms": round(msg_latency_avg, 2),
                "message_latency_p95_ms": round(msg_latency_p95, 2),
                
                # Protocol
                "protocol_version": self._protocol_version,
                "sniff_port": self._sniff_port,
            }
    
    def populate_schema_metrics(self, mavproxy_metrics, role: str = "gcs"):
        """
        Populate the schema dataclass from collected metrics.
        
        Args:
            mavproxy_metrics: MavProxyDroneMetrics or MavProxyGcsMetrics instance
            role: "gcs" or "drone"
        """
        m = self.get_metrics()
        
        if role == "gcs":
            mavproxy_metrics.mavproxy_gcs_start_time = m["start_time"]
            mavproxy_metrics.mavproxy_gcs_end_time = m["end_time"]
            mavproxy_metrics.mavproxy_gcs_tx_pps = m["tx_pps"]
            mavproxy_metrics.mavproxy_gcs_rx_pps = m["rx_pps"]
            mavproxy_metrics.mavproxy_gcs_total_msgs_sent = m["total_msgs_sent"]
            mavproxy_metrics.mavproxy_gcs_total_msgs_received = m["total_msgs_received"]
            mavproxy_metrics.mavproxy_gcs_msg_type_counts = m["msg_type_counts"]
            mavproxy_metrics.mavproxy_gcs_heartbeat_interval_ms = m["heartbeat_interval_ms"]
            mavproxy_metrics.mavproxy_gcs_heartbeat_loss_count = m["heartbeat_loss_count"]
            mavproxy_metrics.mavproxy_gcs_seq_gap_count = m["seq_gap_count"]
            mavproxy_metrics.mavproxy_gcs_cmd_sent_count = m["cmd_sent_count"]
            mavproxy_metrics.mavproxy_gcs_cmd_ack_received_count = m["cmd_ack_received_count"]
            mavproxy_metrics.mavproxy_gcs_cmd_ack_latency_avg_ms = m["cmd_ack_latency_avg_ms"]
            mavproxy_metrics.mavproxy_gcs_cmd_ack_latency_p95_ms = m["cmd_ack_latency_p95_ms"]
            mavproxy_metrics.mavproxy_gcs_stream_rate_hz = m["stream_rate_hz"]
        else:
            mavproxy_metrics.mavproxy_drone_start_time = m["start_time"]
            mavproxy_metrics.mavproxy_drone_end_time = m["end_time"]
            mavproxy_metrics.mavproxy_drone_tx_pps = m["tx_pps"]
            mavproxy_metrics.mavproxy_drone_rx_pps = m["rx_pps"]
            mavproxy_metrics.mavproxy_drone_total_msgs_sent = m["total_msgs_sent"]
            mavproxy_metrics.mavproxy_drone_total_msgs_received = m["total_msgs_received"]
            mavproxy_metrics.mavproxy_drone_msg_type_counts = m["msg_type_counts"]
            mavproxy_metrics.mavproxy_drone_heartbeat_interval_ms = m["heartbeat_interval_ms"]
            mavproxy_metrics.mavproxy_drone_heartbeat_loss_count = m["heartbeat_loss_count"]
            mavproxy_metrics.mavproxy_drone_seq_gap_count = m["seq_gap_count"]
            mavproxy_metrics.mavproxy_drone_cmd_sent_count = m["cmd_sent_count"]
            mavproxy_metrics.mavproxy_drone_cmd_ack_received_count = m["cmd_ack_received_count"]
            mavproxy_metrics.mavproxy_drone_cmd_ack_latency_avg_ms = m["cmd_ack_latency_avg_ms"]
            mavproxy_metrics.mavproxy_drone_cmd_ack_latency_p95_ms = m["cmd_ack_latency_p95_ms"]
            mavproxy_metrics.mavproxy_drone_stream_rate_hz = m["stream_rate_hz"]
    
    def populate_mavlink_integrity(self, integrity_metrics):
        """
        Populate MAVLink integrity metrics.
        
        Args:
            integrity_metrics: MavLinkIntegrityMetrics instance
        """
        m = self.get_metrics()
        
        integrity_metrics.mavlink_sysid = m["heartbeat_sysid"]
        integrity_metrics.mavlink_compid = m["heartbeat_compid"]
        integrity_metrics.mavlink_protocol_version = m["protocol_version"]
        integrity_metrics.mavlink_packet_crc_error_count = m["crc_error_count"]
        integrity_metrics.mavlink_decode_error_count = m["decode_error_count"]
        integrity_metrics.mavlink_msg_drop_count = m["msg_drop_count"]
        integrity_metrics.mavlink_out_of_order_count = m["seq_out_of_order_count"]
        integrity_metrics.mavlink_duplicate_count = m["seq_duplicate_count"]
        integrity_metrics.mavlink_message_latency_avg_ms = m["message_latency_avg_ms"]
        integrity_metrics.mavlink_message_latency_p95_ms = m["message_latency_p95_ms"]


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MAVLINK METRICS COLLECTOR TEST")
    print("=" * 60)
    
    collector = MavLinkMetricsCollector(role="gcs")
    print(f"Role: {collector.role}")
    print(f"pymavlink available: {HAS_PYMAVLINK}")
    
    # Start sniffing (this will bind to a port)
    print("\nStarting collector on port 14599 (test port)...")
    collector.start_sniffing(port=14599)
    
    # Wait a bit
    time.sleep(2.0)
    
    # Stop and get metrics
    metrics = collector.stop()
    
    print("\n--- COLLECTED METRICS ---")
    for k, v in metrics.items():
        if isinstance(v, dict) and len(v) > 5:
            print(f"  {k}: <{len(v)} items>")
        else:
            print(f"  {k}: {v}")
    
    print("\nTest completed!")
