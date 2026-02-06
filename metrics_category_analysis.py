#!/usr/bin/env python3
"""
COMPREHENSIVE METRICS CATEGORY ANALYSIS
========================================
Deep dive into all 18 metrics categories collected during PQC benchmarks.
"""

import json
from pathlib import Path
from collections import defaultdict
import statistics

def analyze_all_categories():
    print("=" * 80)
    print("   PQC SECURE TUNNEL - COMPREHENSIVE METRICS CATEGORY ANALYSIS")
    print("=" * 80)
    
    # Load sample metrics
    comp_dir = Path('bench_analysis/latest_run/comprehensive')
    files = list(comp_dir.glob('*_drone.json'))
    
    if not files:
        print("No metrics files found in latest_run!")
        return
    
    print(f"\nLoaded {len(files)} metrics files from latest run")
    
    # Load all data
    all_data = []
    for f in files:
        with open(f) as fp:
            all_data.append(json.load(fp))
    
    # Use first file as reference for structure
    sample = all_data[0]
    
    print("\n" + "=" * 80)
    print("   18 METRICS CATEGORIES - DETAILED BREAKDOWN")
    print("=" * 80)
    
    # =========================================================================
    # CATEGORY 1: RUN CONTEXT
    # =========================================================================
    print("\n" + "-" * 80)
    print("📋 CATEGORY 1: RUN_CONTEXT")
    print("-" * 80)
    print("Purpose: Identifies the test run and environment configuration")
    ctx = sample.get('run_context', {})
    print(f"""
    run_id                  : {ctx.get('run_id')} (unique benchmark run identifier)
    suite_id                : {ctx.get('suite_id')} (cipher suite being tested)
    suite_index             : {ctx.get('suite_index')} (position in 72-suite sequence)
    git_commit_hash         : {ctx.get('git_commit_hash')} (code version)
    git_dirty_flag          : {ctx.get('git_dirty_flag')} (uncommitted changes?)
    gcs_hostname            : {ctx.get('gcs_hostname')} (Ground Control Station)
    drone_hostname          : {ctx.get('drone_hostname')} (UAV Raspberry Pi)
    gcs_ip / drone_ip       : {ctx.get('gcs_ip')} / {ctx.get('drone_ip')}
    python_env_gcs          : {ctx.get('python_env_gcs')}
    python_env_drone        : {ctx.get('python_env_drone')}
    liboqs_version          : {ctx.get('liboqs_version')}
    kernel_version_gcs      : {ctx.get('kernel_version_gcs')}
    kernel_version_drone    : {ctx.get('kernel_version_drone')}
    clock_offset_ms         : {ctx.get('clock_offset_ms'):.2f}ms (GCS-drone time diff)
    clock_offset_method     : {ctx.get('clock_offset_method')} (synchronization method)
    run_start/end_time_wall : Wall clock timestamps (ISO 8601)
    run_start/end_time_mono : Monotonic timestamps (for duration calc)
    """)
    
    # =========================================================================
    # CATEGORY 2: CRYPTO IDENTITY
    # =========================================================================
    print("\n" + "-" * 80)
    print("🔐 CATEGORY 2: CRYPTO_IDENTITY")
    print("-" * 80)
    print("Purpose: Defines the cryptographic algorithms used in this suite")
    crypto = sample.get('crypto_identity', {})
    print(f"""
    kem_algorithm           : {crypto.get('kem_algorithm')} (Key Encapsulation Mechanism)
    kem_family              : {crypto.get('kem_family')}
    kem_nist_level          : {crypto.get('kem_nist_level')} (Security level L1-L5)
    sig_algorithm           : {crypto.get('sig_algorithm')} (Digital Signature)
    sig_family              : {crypto.get('sig_family')}
    sig_nist_level          : {crypto.get('sig_nist_level')}
    aead_algorithm          : {crypto.get('aead_algorithm')} (Authenticated Encryption)
    suite_security_level    : {crypto.get('suite_security_level')} (Overall security)
    
    📊 Algorithms Tested:
       KEMs: Classic-McEliece-348864/460896/8192128, ML-KEM-512/768/1024, HQC-128/192/256
       Signatures: Falcon-512/1024, ML-DSA-44/65/87, SPHINCS+-128s/192s/256s
       AEADs: AES-256-GCM, ChaCha20-Poly1305, Ascon-128a
    """)
    
    # =========================================================================
    # CATEGORY 3: LIFECYCLE
    # =========================================================================
    print("\n" + "-" * 80)
    print("⏱️ CATEGORY 3: LIFECYCLE")
    print("-" * 80)
    print("Purpose: Tracks timing of suite activation and execution")
    life = sample.get('lifecycle', {})
    print(f"""
    suite_selected_time     : {life.get('suite_selected_time')} (monotonic)
    suite_activated_time    : {life.get('suite_activated_time')} (monotonic)
    suite_deactivated_time  : {life.get('suite_deactivated_time')} (monotonic)
    suite_total_duration_ms : {life.get('suite_total_duration_ms'):.2f}ms (~110s target)
    suite_active_duration_ms: {life.get('suite_active_duration_ms'):.2f}ms (actual active time)
    """)
    
    # =========================================================================
    # CATEGORY 4: HANDSHAKE
    # =========================================================================
    print("\n" + "-" * 80)
    print("🤝 CATEGORY 4: HANDSHAKE")
    print("-" * 80)
    print("Purpose: PQC key exchange and authentication timing")
    hs = sample.get('handshake', {})
    print(f"""
    handshake_start_time_drone  : {hs.get('handshake_start_time_drone')} (monotonic)
    handshake_end_time_drone    : {hs.get('handshake_end_time_drone')} (monotonic)
    handshake_total_duration_ms : {hs.get('handshake_total_duration_ms'):.2f}ms (end-to-end)
    protocol_handshake_duration_ms: {hs.get('protocol_handshake_duration_ms'):.2f}ms (crypto only)
    handshake_success           : {hs.get('handshake_success')}
    handshake_failure_reason    : "{hs.get('handshake_failure_reason')}" (if failed)
    
    ⚡ Protocol handshake = KEM encaps + signature verify + key derivation
    """)
    
    # =========================================================================
    # CATEGORY 5: CRYPTO PRIMITIVES
    # =========================================================================
    print("\n" + "-" * 80)
    print("🔑 CATEGORY 5: CRYPTO_PRIMITIVES")
    print("-" * 80)
    print("Purpose: Individual cryptographic operation timings and sizes")
    cp = sample.get('crypto_primitives', {})
    print(f"""
    kem_keygen_time_ms          : {cp.get('kem_keygen_time_ms')} (usually on drone side)
    kem_encapsulation_time_ms   : {cp.get('kem_encapsulation_time_ms')} (GCS encapsulates)
    kem_decapsulation_time_ms   : {cp.get('kem_decapsulation_time_ms')} (drone decapsulates)
    signature_sign_time_ms      : {cp.get('signature_sign_time_ms')} (drone signs)
    signature_verify_time_ms    : {cp.get('signature_verify_time_ms')} (GCS verifies)
    
    📐 Sizes:
    pub_key_size_bytes          : {cp.get('pub_key_size_bytes'):,} bytes ({cp.get('pub_key_size_bytes', 0)/1024:.1f} KB)
    ciphertext_size_bytes       : {cp.get('ciphertext_size_bytes'):,} bytes
    sig_size_bytes              : {cp.get('sig_size_bytes'):,} bytes
    shared_secret_size_bytes    : {cp.get('shared_secret_size_bytes')} bytes (always 32)
    """)
    
    # =========================================================================
    # CATEGORY 6: REKEY
    # =========================================================================
    print("\n" + "-" * 80)
    print("🔄 CATEGORY 6: REKEY")
    print("-" * 80)
    print("Purpose: Key rotation during long sessions (not used in benchmark)")
    rk = sample.get('rekey', {})
    print(f"""
    rekey_attempts              : {rk.get('rekey_attempts')}
    rekey_success               : {rk.get('rekey_success')}
    rekey_failure               : {rk.get('rekey_failure')}
    rekey_interval_ms           : {rk.get('rekey_interval_ms')}ms
    rekey_duration_ms           : {rk.get('rekey_duration_ms')}ms
    rekey_blackout_duration_ms  : {rk.get('rekey_blackout_duration_ms')}ms
    rekey_trigger_reason        : "{rk.get('rekey_trigger_reason')}"
    
    Note: Rekey not triggered in 110s benchmark windows
    """)
    
    # =========================================================================
    # CATEGORY 7: DATA PLANE
    # =========================================================================
    print("\n" + "-" * 80)
    print("📡 CATEGORY 7: DATA_PLANE")
    print("-" * 80)
    print("Purpose: Encrypted tunnel traffic statistics")
    dp = sample.get('data_plane', {})
    print(f"""
    achieved_throughput_mbps    : {dp.get('achieved_throughput_mbps'):.4f} Mbps
    goodput_mbps                : {dp.get('goodput_mbps'):.4f} Mbps (payload only)
    wire_rate_mbps              : {dp.get('wire_rate_mbps'):.4f} Mbps (with overhead)
    
    Packet Counts:
    packets_sent                : {dp.get('packets_sent'):,}
    packets_received            : {dp.get('packets_received'):,}
    packets_dropped             : {dp.get('packets_dropped')}
    packet_loss_ratio           : {dp.get('packet_loss_ratio')}
    packet_delivery_ratio       : {dp.get('packet_delivery_ratio')}
    
    Proxy Counters:
    ptx_in                      : {dp.get('ptx_in'):,} (plaintext packets in)
    ptx_out                     : {dp.get('ptx_out'):,} (plaintext packets out)
    enc_in                      : {dp.get('enc_in'):,} (encrypted packets in)
    enc_out                     : {dp.get('enc_out'):,} (encrypted packets out)
    
    Security Drops:
    drop_replay                 : {dp.get('drop_replay')} (replay attack detected)
    drop_auth                   : {dp.get('drop_auth')} (auth tag failed)
    drop_header                 : {dp.get('drop_header')} (malformed header)
    replay_drop_count           : {dp.get('replay_drop_count')}
    decode_failure_count        : {dp.get('decode_failure_count')}
    
    Bytes:
    bytes_sent                  : {dp.get('bytes_sent'):,}
    bytes_received              : {dp.get('bytes_received'):,}
    
    AEAD Performance:
    aead_encrypt_avg_ns         : {dp.get('aead_encrypt_avg_ns'):,}ns ({dp.get('aead_encrypt_avg_ns', 0)/1000:.1f}µs)
    aead_decrypt_avg_ns         : {dp.get('aead_decrypt_avg_ns'):,}ns ({dp.get('aead_decrypt_avg_ns', 0)/1000:.1f}µs)
    aead_encrypt_count          : {dp.get('aead_encrypt_count'):,}
    aead_decrypt_count          : {dp.get('aead_decrypt_count'):,}
    """)
    
    # =========================================================================
    # CATEGORY 8: LATENCY & JITTER
    # =========================================================================
    print("\n" + "-" * 80)
    print("⏲️ CATEGORY 8: LATENCY_JITTER")
    print("-" * 80)
    print("Purpose: Network timing measurements (requires time sync)")
    lat = sample.get('latency_jitter', {})
    print(f"""
    one_way_latency_avg_ms      : {lat.get('one_way_latency_avg_ms')}
    one_way_latency_p95_ms      : {lat.get('one_way_latency_p95_ms')}
    one_way_latency_valid       : {lat.get('one_way_latency_valid')}
    latency_invalid_reason      : "{lat.get('latency_invalid_reason')}"
    
    jitter_avg_ms               : {lat.get('jitter_avg_ms')}
    jitter_p95_ms               : {lat.get('jitter_p95_ms')}
    
    rtt_avg_ms                  : {lat.get('rtt_avg_ms')}
    rtt_p95_ms                  : {lat.get('rtt_p95_ms')}
    rtt_valid                   : {lat.get('rtt_valid')}
    rtt_invalid_reason          : "{lat.get('rtt_invalid_reason')}"
    
    ⚠️ Note: Latency metrics require command/response pairs (not in passive mode)
    """)
    
    # =========================================================================
    # CATEGORY 9: MAVPROXY DRONE
    # =========================================================================
    print("\n" + "-" * 80)
    print("🚁 CATEGORY 9: MAVPROXY_DRONE")
    print("-" * 80)
    print("Purpose: MAVLink proxy statistics on the drone side")
    md = sample.get('mavproxy_drone', {})
    print(f"""
    mavproxy_drone_tx_pps       : {md.get('mavproxy_drone_tx_pps')} packets/sec (TX)
    mavproxy_drone_rx_pps       : {md.get('mavproxy_drone_rx_pps')} packets/sec (RX)
    mavproxy_drone_total_msgs_sent    : {md.get('mavproxy_drone_total_msgs_sent'):,}
    mavproxy_drone_total_msgs_received: {md.get('mavproxy_drone_total_msgs_received'):,}
    
    Heartbeat:
    mavproxy_drone_heartbeat_interval_ms: {md.get('mavproxy_drone_heartbeat_interval_ms')}ms
    mavproxy_drone_heartbeat_loss_count : {md.get('mavproxy_drone_heartbeat_loss_count')}
    
    Integrity:
    mavproxy_drone_seq_gap_count       : {md.get('mavproxy_drone_seq_gap_count')}
    mavproxy_drone_stream_rate_hz      : {md.get('mavproxy_drone_stream_rate_hz')} Hz
    
    Commands:
    mavproxy_drone_cmd_sent_count      : {md.get('mavproxy_drone_cmd_sent_count')}
    mavproxy_drone_cmd_ack_received_count: {md.get('mavproxy_drone_cmd_ack_received_count')}
    
    Message Types (top 5):
    """)
    msg_counts = md.get('mavproxy_drone_msg_type_counts', {})
    for msg, count in sorted(msg_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"      {msg}: {count:,}")
    
    # =========================================================================
    # CATEGORY 10: MAVPROXY GCS
    # =========================================================================
    print("\n" + "-" * 80)
    print("🖥️ CATEGORY 10: MAVPROXY_GCS")
    print("-" * 80)
    print("Purpose: MAVLink proxy statistics on GCS side")
    mg = sample.get('mavproxy_gcs', {})
    print(f"""
    mavproxy_gcs_total_msgs_received: {mg.get('mavproxy_gcs_total_msgs_received'):,}
    mavproxy_gcs_seq_gap_count      : {mg.get('mavproxy_gcs_seq_gap_count')}
    """)
    
    # =========================================================================
    # CATEGORY 11: MAVLINK INTEGRITY
    # =========================================================================
    print("\n" + "-" * 80)
    print("✅ CATEGORY 11: MAVLINK_INTEGRITY")
    print("-" * 80)
    print("Purpose: MAVLink protocol health checks")
    mi = sample.get('mavlink_integrity', {})
    print(f"""
    mavlink_sysid               : {mi.get('mavlink_sysid')} (system ID)
    mavlink_compid              : {mi.get('mavlink_compid')} (component ID)
    mavlink_protocol_version    : {mi.get('mavlink_protocol_version')}
    
    Error Counts:
    mavlink_packet_crc_error_count: {mi.get('mavlink_packet_crc_error_count')}
    mavlink_decode_error_count    : {mi.get('mavlink_decode_error_count')}
    mavlink_msg_drop_count        : {mi.get('mavlink_msg_drop_count')}
    mavlink_out_of_order_count    : {mi.get('mavlink_out_of_order_count')}
    mavlink_duplicate_count       : {mi.get('mavlink_duplicate_count')}
    """)
    
    # =========================================================================
    # CATEGORY 12: FC TELEMETRY
    # =========================================================================
    print("\n" + "-" * 80)
    print("🎮 CATEGORY 12: FC_TELEMETRY")
    print("-" * 80)
    print("Purpose: Flight Controller (Pixhawk) status")
    fc = sample.get('fc_telemetry', {})
    print(f"""
    fc_mode                     : {fc.get('fc_mode')} (flight mode)
    fc_armed_state              : {fc.get('fc_armed_state')} (motors armed?)
    fc_heartbeat_age_ms         : {fc.get('fc_heartbeat_age_ms'):.1f}ms (last heartbeat)
    
    Update Rates:
    fc_attitude_update_rate_hz  : {fc.get('fc_attitude_update_rate_hz'):.1f} Hz
    fc_position_update_rate_hz  : {fc.get('fc_position_update_rate_hz'):.1f} Hz
    
    Battery:
    fc_battery_voltage_v        : {fc.get('fc_battery_voltage_v'):.3f} V
    fc_battery_current_a        : {fc.get('fc_battery_current_a'):.2f} A
    fc_battery_remaining_percent: {fc.get('fc_battery_remaining_percent'):.0f}%
    
    System:
    fc_cpu_load_percent         : {fc.get('fc_cpu_load_percent'):.1f}%
    fc_sensor_health_flags      : {fc.get('fc_sensor_health_flags')} (bitmask)
    """)
    
    # =========================================================================
    # CATEGORY 13: CONTROL PLANE
    # =========================================================================
    print("\n" + "-" * 80)
    print("🎛️ CATEGORY 13: CONTROL_PLANE")
    print("-" * 80)
    print("Purpose: Benchmark scheduler state")
    cp = sample.get('control_plane', {})
    print(f"""
    scheduler_tick_interval_ms  : {cp.get('scheduler_tick_interval_ms')}ms (110s)
    scheduler_action_type       : {cp.get('scheduler_action_type')}
    scheduler_action_reason     : {cp.get('scheduler_action_reason')}
    policy_name                 : {cp.get('policy_name')}
    policy_state                : {cp.get('policy_state')}
    policy_suite_index          : {cp.get('policy_suite_index')} / {cp.get('policy_total_suites')}
    """)
    
    # =========================================================================
    # CATEGORY 14: SYSTEM DRONE
    # =========================================================================
    print("\n" + "-" * 80)
    print("🖥️ CATEGORY 14: SYSTEM_DRONE")
    print("-" * 80)
    print("Purpose: Raspberry Pi resource usage")
    sd = sample.get('system_drone', {})
    print(f"""
    cpu_usage_avg_percent       : {sd.get('cpu_usage_avg_percent'):.1f}%
    cpu_usage_peak_percent      : {sd.get('cpu_usage_peak_percent'):.1f}%
    cpu_freq_mhz                : {sd.get('cpu_freq_mhz'):.0f} MHz
    memory_rss_mb               : {sd.get('memory_rss_mb'):.1f} MB (resident)
    memory_vms_mb               : {sd.get('memory_vms_mb'):.1f} MB (virtual)
    temperature_c               : {sd.get('temperature_c'):.1f}°C
    uptime_s                    : {sd.get('uptime_s'):.0f}s ({sd.get('uptime_s', 0)/3600:.1f} hours)
    load_avg_1m                 : {sd.get('load_avg_1m'):.2f}
    load_avg_5m                 : {sd.get('load_avg_5m'):.2f}
    load_avg_15m                : {sd.get('load_avg_15m'):.2f}
    """)
    
    # =========================================================================
    # CATEGORY 15: SYSTEM GCS
    # =========================================================================
    print("\n" + "-" * 80)
    print("💻 CATEGORY 15: SYSTEM_GCS")
    print("-" * 80)
    print("Purpose: Windows GCS resource usage")
    sg = sample.get('system_gcs', {})
    print(f"""
    cpu_usage_avg_percent       : {sg.get('cpu_usage_avg_percent'):.1f}%
    cpu_usage_peak_percent      : {sg.get('cpu_usage_peak_percent'):.1f}%
    cpu_freq_mhz                : {sg.get('cpu_freq_mhz'):.0f} MHz
    memory_rss_mb               : {sg.get('memory_rss_mb'):.1f} MB
    memory_vms_mb               : {sg.get('memory_vms_mb'):.1f} MB
    thread_count                : {sg.get('thread_count')}
    uptime_s                    : {sg.get('uptime_s'):.0f}s ({sg.get('uptime_s', 0)/3600:.1f} hours)
    """)
    
    # =========================================================================
    # CATEGORY 16: POWER & ENERGY
    # =========================================================================
    print("\n" + "-" * 80)
    print("⚡ CATEGORY 16: POWER_ENERGY")
    print("-" * 80)
    print("Purpose: INA219 power sensor measurements")
    pw = sample.get('power_energy', {})
    print(f"""
    power_sensor_type           : {pw.get('power_sensor_type')} (I2C power monitor)
    power_sampling_rate_hz      : {pw.get('power_sampling_rate_hz')} Hz
    
    Measurements:
    voltage_avg_v               : {pw.get('voltage_avg_v'):.3f} V
    current_avg_a               : {pw.get('current_avg_a'):.3f} A
    power_avg_w                 : {pw.get('power_avg_w'):.2f} W
    power_peak_w                : {pw.get('power_peak_w'):.2f} W
    
    Energy:
    energy_total_j              : {pw.get('energy_total_j'):.2f} J (total for suite)
    energy_per_handshake_j      : {pw.get('energy_per_handshake_j'):.2f} J (per handshake)
    """)
    
    # =========================================================================
    # CATEGORY 17: OBSERVABILITY
    # =========================================================================
    print("\n" + "-" * 80)
    print("📊 CATEGORY 17: OBSERVABILITY")
    print("-" * 80)
    print("Purpose: Metrics collection health")
    obs = sample.get('observability', {})
    print(f"""
    log_sample_count            : {obs.get('log_sample_count')}
    metrics_sampling_rate_hz    : {obs.get('metrics_sampling_rate_hz')} Hz
    collection_start_time       : {obs.get('collection_start_time')}
    collection_end_time         : {obs.get('collection_end_time')}
    collection_duration_ms      : {obs.get('collection_duration_ms'):.0f}ms
    """)
    
    # =========================================================================
    # CATEGORY 18: VALIDATION
    # =========================================================================
    print("\n" + "-" * 80)
    print("✅ CATEGORY 18: VALIDATION")
    print("-" * 80)
    print("Purpose: Test result validation")
    val = sample.get('validation', {})
    print(f"""
    expected_samples            : {val.get('expected_samples')}
    collected_samples           : {val.get('collected_samples')}
    lost_samples                : {val.get('lost_samples')}
    success_rate_percent        : {val.get('success_rate_percent'):.1f}%
    benchmark_pass_fail         : {val.get('benchmark_pass_fail')}
    
    Metric Status (invalid metrics):
    """)
    for metric, status in val.get('metric_status', {}).items():
        print(f"      {metric}: {status.get('reason')}")
    
    print("\n" + "=" * 80)
    print("   END OF METRICS CATEGORY ANALYSIS")
    print("=" * 80)

if __name__ == "__main__":
    analyze_all_categories()
