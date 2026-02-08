import json
f = "logs/benchmarks/live_run_20260207_172159/comprehensive/cs-classicmceliece460896-aesgcm-sphincs192s_20260207_172159_drone.json"
data = json.load(open(f))
hs = data.get("handshake", {})
print("success:", hs.get("handshake_success"))
print("total_ms:", hs.get("handshake_total_duration_ms"))
print("proto_ms:", hs.get("protocol_handshake_duration_ms"))
print("failure:", hs.get("handshake_failure_reason"))
