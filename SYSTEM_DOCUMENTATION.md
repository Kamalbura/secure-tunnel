# Secure Tunnel System Documentation

## 1. System Overview

The **Secure Tunnel** project implements a Post-Quantum Cryptography (PQC) secured communication channel between a Drone (UAV) and a Ground Control Station (GCS).

### Key Architecture: Reversed Control
Unlike traditional setups where the GCS commands the Drone, this system uses a **Reversed Control** architecture for the crypto tunnel:
- **Drone = Controller**: The Drone decides which cryptographic suite to use, when to rotate keys (rekey), and when to start/stop the tunnel.
- **GCS = Follower**: The GCS waits for commands from the Drone via a TCP control channel and follows instructions to start its side of the tunnel.

### Communication Channels
1.  **Control Channel (TCP)**: JSON commands from Drone to GCS (e.g., "Start Proxy", "Prepare Rekey").
2.  **Telemetry Channel (UDP)**: Unidirectional health/status updates from GCS to Drone (Schema: `uav.pqc.telemetry.v1`).
3.  **Data Tunnel (UDP)**: The actual encrypted traffic (MAVLink) encapsulated in PQC.

---

## 2. Drone Side (Controller)

The Drone is the brain of the secure tunnel operation. It runs the scheduler that rotates through cryptographic suites.

### Components

#### 1. `sscheduler/sdrone.py` (The Orchestrator)
-   **Role**: Main Controller.
-   **Job**:
    -   Selects the next crypto suite based on a policy (Linear, Random, etc.).
    -   Commands the GCS to start its proxy via TCP.
    -   Starts the local Drone proxy (`core/run_proxy.py`).
    -   Validates the tunnel using an Echo Server.
    -   Monitors GCS health via the Telemetry Listener.
-   **How it works**:
    -   Runs a state machine: `Select Suite` -> `Command GCS` -> `Start Local Proxy` -> `Wait for Handshake` -> `Monitor` -> `Stop` -> `Next Suite`.
    -   Enforces safety gates on incoming telemetry (IP allow-list, Max Size 8KB, Schema Validation).

#### 2. `core/run_proxy.py` (The Tunnel Endpoint)
-   **Role**: Cryptographic Data Plane.
-   **Job**:
    -   Establishes the actual secure channel using `liboqs` (Open Quantum Safe).
    -   Encapsulates plaintext UDP packets into PQC-secured packets.
    -   Handles key exchange and rekeying.
-   **How it works**:
    -   Launched as a subprocess by `sdrone.py`.
    -   Uses the `drone` subcommand: `python -m core.run_proxy drone ...`.
    -   Loads the GCS public key to verify the server.

#### 3. `tools/mavproxy_manager.py` (The Application Layer)
-   **Role**: MAVLink Router.
-   **Job**:
    -   Routes MAVLink traffic from the flight controller (e.g., `/dev/ttyACM0`) to the secure tunnel's plaintext port.
-   **How it works**:
    -   Wraps the standard `MAVProxy` tool.
    -   Configured to forward traffic to `127.0.0.1:DRONE_PLAINTEXT_TX`.

#### 4. `scripts/telemetry_recv_test.py` (The Doctor)
-   **Role**: Diagnostic Tool.
-   **Job**:
    -   Verifies that the Drone can receive telemetry from the GCS.
    -   Validates network firewall settings and packet integrity.
-   **How it works**:
    -   Standalone script that binds to UDP 52080.
    -   Prints "RX OK" or "DROP" based on strict safety checks (mirroring `sdrone.py`).

---

## 3. GCS Side (Follower)

The GCS acts as a passive server that responds to the Drone's requirements.

### Components

#### 1. `sscheduler/sgcs.py` (The Follower)
-   **Role**: Main Listener.
-   **Job**:
    -   Listens on a TCP port (default 48080) for commands.
    -   Starts/Stops the GCS proxy when commanded.
    -   Generates dummy traffic for bandwidth testing.
-   **How it works**:
    -   Runs a threaded TCP server (`ControlServer`).
    -   Handles JSON commands: `start_proxy`, `start_traffic`, `stop`, `prepare_rekey`.
    -   Manages the `run_proxy.py` subprocess.

#### 2. `sscheduler/gcs_metrics.py` (The Telemetry Source)
-   **Role**: Health Reporter.
-   **Job**:
    -   Collects system metrics (CPU, RAM) and MAVLink health (Heartbeat age, Drop rate).
    -   Bundles data into the `uav.pqc.telemetry.v1` JSON schema.
    -   Sends UDP packets to the Drone (Port 52080).
-   **How it works**:
    -   Runs in a background thread within `sgcs.py`.
    -   Sniffs MAVLink traffic on a local UDP port.
    -   Sends updates at ~5Hz.

#### 3. `core/run_proxy.py` (The Tunnel Endpoint)
-   **Role**: Cryptographic Data Plane.
-   **Job**:
    -   Accepts connections from the Drone.
    -   Decapsulates PQC packets back to plaintext UDP.
-   **How it works**:
    -   Launched by `sgcs.py` using the `gcs` subcommand.
    -   Uses the GCS private key to sign the handshake.

---

## 4. Shared Core Components

#### `core/suites.py`
-   **Job**: Defines the available Post-Quantum Cryptography suites (e.g., `cs-mlkem768-aesgcm-mldsa65`).
-   **Details**: Maps suite IDs to specific KEM (Key Encapsulation), AEAD (Encryption), and Signature algorithms.

#### `core/config.py`
-   **Job**: Single source of truth for configuration (IPs, Ports, Paths).
-   **Details**: Loads from environment variables or defaults (e.g., `config.remote.py`).

---

## 5. Data Flow Summary

1.  **Initialization**:
    -   **GCS**: Starts `sgcs.py`, waits on TCP 48080.
    -   **Drone**: Starts `sdrone.py`.

2.  **Suite Activation**:
    -   **Drone**: Picks a suite (e.g., `Kyber768`).
    -   **Drone**: Sends `start_proxy` command to GCS.
    -   **GCS**: Launches `core.run_proxy gcs ...`.
    -   **Drone**: Launches `core.run_proxy drone ...`.

3.  **Handshake**:
    -   The two proxies perform a Quantum-Safe handshake.
    -   Once established, a secure tunnel exists between `127.0.0.1` ports on both sides.

4.  **Operation**:
    -   **MAVLink**: Traffic flows through the tunnel.
    -   **Telemetry**: GCS sends UDP health packets to Drone (outside the tunnel) for monitoring.
    -   **Rekey**: Drone decides when to rotate keys and repeats the process.
