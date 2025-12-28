# Secure Tunnel: Post-Quantum Cryptographic Link for UAVs

## 1. Abstract

**Secure Tunnel** is a research-grade, distributed secure communication system designed to protect Command & Control (C2) and telemetry links between Ground Control Stations (GCS) and Unmanned Aerial Vehicles (UAVs).

It solves the problem of securing vulnerable MAVLink traffic against quantum computer threats by implementing a hybrid Post-Quantum Cryptography (PQC) tunnel. The system encapsulates standard MAVLink UDP packets into an authenticated, encrypted stream using cutting-edge NIST-standardized algorithms (ML-KEM, ML-DSA) alongside classical primitives.

This project is critical for future-proofing autonomous systems against "store now, decrypt later" attacks and ensuring the integrity of flight control in contested environments.

---

## 2. High-Level Architecture

The system operates as a transparent "bump-in-the-wire" proxy. Applications (like Mission Planner or MAVProxy) communicate with a local plaintext port, unaware of the complex crypto-tunnel bridging the physical network.

```ascii
      [ GCS SIDE (Windows) ]                       [ DRONE SIDE (Raspberry Pi) ]
+-----------------------------+                 +-----------------------------+
|  Mission Planner / QGC      |                 |      Pixhawk Autopilot      |
|       (MAVLink App)         |                 |      (Flight Controller)    |
+-------------+---------------+                 +--------------+--------------+
              | UDP Plaintext                                  | Serial / UDP
              v                                                v
+-------------+---------------+                 +--------------+--------------+
|      GCS Proxy (Core)       |                 |      Drone Proxy (Core)     |
|  [Plaintext Listener]       |                 |   [Plaintext Listener]      |
|  [Encrypted Sender]         |                 |   [Encrypted Sender]        |
+-------------+---------------+                 +--------------+--------------+
              |                                                |
              |  <=== TCP Authenticated Handshake (PQC) ===>   |
              |                                                |
              |  <=== UDP Encrypted Data Plane (AEAD) =====>   |
              |                                                |
+-------------+---------------+                 +--------------+--------------+
|      Physical Network       |                 |      Physical Network       |
|      (WiFi / Radio)         |                 |      (WiFi / Radio)         |
+-----------------------------+                 +-----------------------------+
```

### Components
1.  **GCS Proxy:** Runs on the ground station. Acts as the server for TCP handshakes and a peer for UDP traffic.
2.  **Drone Proxy:** Runs on the companion computer (Pi). Connects to GCS via TCP to establish keys, then bridges traffic.
3.  **Schedulers:** Orchestration layers (`scheduler` and `sscheduler`) that automate test cycles, suite rotation, and re-keying.

---

## 3. Network Topology

The system assumes a flat IP network (LAN or VPN) where GCS and Drone can reach each other.

| Role | Interface | Protocol | Port (Default) | Description |
|------|-----------|----------|----------------|-------------|
| **GCS** | 0.0.0.0 | TCP | 46000 | **Handshake Server**. Listens for Drone connections. |
| **GCS** | 0.0.0.0 | UDP | 46011 | **Encrypted RX**. Receives encrypted frames from Drone. |
| **GCS** | 127.0.0.1 | UDP | 47001 | **Plaintext TX**. App sends MAVLink here to enter tunnel. |
| **GCS** | 127.0.0.1 | UDP | 47002 | **Plaintext RX**. Tunnel delivers decrypted MAVLink here. |
| **Drone** | (Connects) | TCP | -> GCS:46000 | **Handshake Client**. Initiates key exchange. |
| **Drone** | 0.0.0.0 | UDP | 46012 | **Encrypted RX**. Receives encrypted frames from GCS. |
| **Drone** | 127.0.0.1 | UDP | 47003 | **Plaintext TX**. MAVProxy sends MAVLink here to enter tunnel. |
| **Drone** | 127.0.0.1 | UDP | 47004 | **Plaintext RX**. Tunnel delivers decrypted MAVLink here. |

**Note:** The GCS is the TCP *Listener* (Server), but the Drone is the TCP *Initiator* (Client). This allows the Drone to be behind a NAT if the GCS has a public/reachable IP, though typically both are on the same LAN.

---

## 4. Cryptographic Design

Security is provided by **Suites**, which define a specific combination of algorithms.

### Components of a Suite
1.  **KEM (Key Encapsulation Mechanism):** Used during TCP handshake to establish a shared secret.
    *   *Examples:* ML-KEM-768, Kyber512, HQC-192.
2.  **Signature:** Used to authenticate the handshake (prevent Man-in-the-Middle).
    *   *Examples:* ML-DSA-65, Falcon-512, SPHINCS+.
3.  **AEAD (Authenticated Encryption with Associated Data):** Used for the high-speed UDP data plane.
    *   *Examples:* AES-GCM, ChaCha20-Poly1305, ASCON-128.

### Protocol Flow
1.  **Handshake (TCP):**
    *   Drone connects to GCS.
    *   GCS sends `ServerHello` (Public Key + Signature).
    *   Drone verifies Signature against stored GCS public key.
    *   Drone encapsulates a shared secret using KEM and sends ciphertext.
    *   Both sides derive session keys (`K_d2g`, `K_g2d`) and Session ID.
2.  **Data Plane (UDP):**
    *   Traffic is encrypted using the derived session keys.
    *   Each packet includes a header with Session ID, Sequence Number, and AEAD Tag.
    *   Replay protection is enforced via a sliding window.

---

## 5. Core Modules

The `core/` directory contains the engine of the tunnel.

*   **`core/config.py`**: The **Single Source of Truth**. Defines all ports, IP addresses, and feature flags.
*   **`core/handshake.py`**: Implements the PQC handshake logic. Handles key generation, signing, verification, and encapsulation using `liboqs`.
*   **`core/async_proxy.py`**: The main event loop (selector-based).
    *   Manages UDP sockets (plaintext & encrypted).
    *   Handles packet encryption/decryption.
    *   Enforces rate limits and strict peer checking.
*   **`core/run_proxy.py`**: The CLI entrypoint. Parses arguments and launches the `async_proxy` engine.

---

## 6. Scheduler Systems

The project supports two orchestration modes for automated testing.

### A. `scheduler/` (Legacy / GCS-Driven)
*   **Philosophy:** GCS is the "Master". It tells the Drone what to do via SSH or RPC.
*   **Use Case:** Lab benchmarking where the operator sits at the GCS.

### B. `sscheduler/` (Simplified / Drone-Driven)
*   **Philosophy:** Drone is the "Controller". GCS is a passive "Follower".
*   **Entrypoints:**
    *   `sscheduler/sgcs.py`: Runs on GCS. Starts a control server and waits.
    *   `sscheduler/sdrone.py`: Runs on Drone. Decides which suite to run and commands the GCS to start.
*   **Use Case:** Field tests where the Drone determines the test plan (e.g., "run these 5 suites in flight"). **This is the currently active development branch.**

---

## 7. End-to-End Data Flow

1.  **Source:** Pixhawk sends MAVLink serial data to Raspberry Pi.
2.  **Bridge:** `MAVProxy` on Pi reads serial, forwards UDP packet to `127.0.0.1:47003`.
3.  **Ingress:** `Drone Proxy` receives packet on `47003`.
4.  **Encryption:** Proxy encrypts payload with `K_d2g` (Drone-to-GCS key). Adds header.
5.  **Transmission:** Encrypted packet sent from Drone `wlan0` to GCS IP `46011`.
6.  **Reception:** `GCS Proxy` receives packet on `46011`.
7.  **Decryption:** Proxy validates header/tag, decrypts using `K_d2g`.
8.  **Egress:** Plaintext packet sent to `127.0.0.1:47002`.
9.  **Sink:** GCS Application (Mission Planner) listens on `47002` and parses MAVLink.

*Return traffic follows the inverse path.*

---

## 8. Environments & Setup

### GCS (Windows)
*   **Manager:** Conda
*   **Env Name:** `oqs-dev`
*   **Key Dep:** `oqs-python` (must be compiled with PQC support).

### Drone (Raspberry Pi / Linux)
*   **Manager:** venv
*   **Path:** `~/cenv`
*   **Activation:** `source ~/cenv/bin/activate`
*   **Key Dep:** `liboqs` built from source, `oqs-python`.

**Compatibility:** Both sides MUST run compatible versions of `oqs-python` and the `secure-tunnel` codebase.

---

## 9. Installation

1.  **Clone Repository:**
    ```bash
    git clone https://github.com/project/secure-tunnel.git
    cd secure-tunnel
    ```
2.  **Install Dependencies:**
    *   Follow `liboqs` installation guide for your platform.
    *   `pip install -r requirements.txt`
    *   Ensure `import oqs` works in Python.

---

## 10. Running the System

**CRITICAL RULE:** Before *any* test run, enforce a sterile state to prevent configuration drift or residue.

### Step 1: Sterile Cleanup (Both Sides)
```bash
git reset --hard HEAD
git clean -fdx
```

### Step 2: Start GCS (Follower)
```powershell
conda activate oqs-dev
cd secure-tunnel
python -m sscheduler.sgcs
```
*GCS will wait for commands.*

### Step 3: Start Drone (Controller)
```bash
ssh dev@drone-ip
source ~/cenv/bin/activate
cd ~/secure-tunnel
sudo -E ~/cenv/bin/python -m sscheduler.sdrone
```
*Drone will connect to GCS, negotiate keys, and start traffic.*

---

## 11. Testing

*   **Unit Tests:** `pytest tests/` - Verifies crypto logic and packet framing.
*   **Loop Tests:** `python test_simple_loop.py` - Runs a local mock of both sides to verify logic without network.
*   **Integration:** Running `sdrone.py` performs a full system test with real network traffic.

---

## 12. Debugging & Observability

*   **Logs:**
    *   GCS: `logs/sscheduler/gcs/`
    *   Drone: `logs/sscheduler/drone/`
*   **Status JSON:** Proxies write `status.json` with real-time counters (packets in/out, drops, rekeys).
*   **Common Errors:**
    *   `HandshakeVerifyError`: Signature mismatch. Check `secrets/` keys.
    *   `ConnectionRefused`: GCS proxy not running or firewall blocking port 46000.
    *   `Decryption Fail (Auth)`: Wrong key or packet corruption.
    *   `Decryption Fail (Replay)`: Duplicate packet or sequence window issue.

---

## 13. Common Pitfalls

1.  **Residue:** Old `__pycache__` or `.pyc` files can cause baffling logic errors. **Always `git clean -fdx`**.
2.  **Sudo Environment:** On Linux, `sudo python` does not inherit user env vars. Use `sudo -E`.
3.  **Strict Peer Match:** The config `STRICT_UDP_PEER_MATCH = True` drops packets if the source IP doesn't match the handshake IP. Disable this if testing across complex NATs.
4.  **Time Sync:** PQC signatures and logs depend on reasonable time synchronization. Ensure NTP is active.

---

## 14. Design Lessons

*   **Strictness is Safety:** We enforce strict IP matching and sequence checking. It makes debugging harder initially but prevents security holes.
*   **Sterile State:** Distributed systems drift. The only way to trust a result is to destroy the environment and rebuild it (clean git state) before every run.

---

## 15. Extending the Project

*   **New Suites:** Add entries to `core/suites.py`. Ensure `liboqs` supports the primitives.
*   **New Schedulers:** Implement the `ControlServer` interface to drive the proxies via the JSON control plane.

---

## 16. Reproducibility Checklist

1.  [ ] **GCS:** `git status` is clean.
2.  [ ] **Drone:** `git status` is clean.
3.  [ ] **GCS:** `git clean -fdx` executed.
4.  [ ] **Drone:** `git clean -fdx` executed.
5.  [ ] **Network:** Both devices pingable.
6.  [ ] **Config:** `core/config.py` IPs match `ipconfig`/`ip addr`.
7.  [ ] **Run:** Start GCS, then Start Drone.

---

## 17. Credits & Motivation

Developed for research into **Post-Quantum UAV Security**.
The goal is to demonstrate that PQC is viable on constrained embedded hardware (Raspberry Pi) for real-time flight control.

