# MAVProxy Bidirectional Port Flow - VERIFIED

## Configuration (from core/config.py)
```
PORTS:
  UDP_DRONE_RX: 46012       # Drone receives encrypted from GCS
  UDP_GCS_RX: 46011         # GCS receives encrypted from Drone
  DRONE_PLAINTEXT_TX: 47003 # Drone proxy receives plaintext from app (MAVProxy)
  DRONE_PLAINTEXT_RX: 47004 # Drone proxy sends decrypted to app (MAVProxy)
  GCS_PLAINTEXT_TX: 47001   # GCS proxy receives plaintext from app (MAVProxy)
  GCS_PLAINTEXT_RX: 47002   # GCS proxy sends decrypted to app (MAVProxy)
  
HOSTS:
  DRONE_PLAINTEXT_HOST: 127.0.0.1
  GCS_PLAINTEXT_HOST: 127.0.0.1
  DRONE_HOST: 192.168.0.103
  GCS_HOST: 192.168.0.104
```

## Proxy Socket Bindings (from core/async_proxy.py)

### Drone Proxy:
```
BINDS:
  - encrypted: 0.0.0.0:46012      (receives encrypted from GCS)
  - plaintext_in: 127.0.0.1:47003 (receives plaintext from MAVProxy)
  
SENDS TO:
  - encrypted_peer: 192.168.0.104:46011 (GCS encrypted RX)
  - plaintext_peer: 127.0.0.1:47004     (MAVProxy for decrypted commands)
```

### GCS Proxy:
```
BINDS:
  - encrypted: 0.0.0.0:46011      (receives encrypted from Drone)
  - plaintext_in: 127.0.0.1:47001 (receives plaintext from MAVProxy)
  
SENDS TO:
  - encrypted_peer: 192.168.0.103:46012 (Drone encrypted RX)
  - plaintext_peer: 127.0.0.1:47002     (MAVProxy for decrypted telemetry)
```

## MAVProxy Configuration (FIXED)

### Drone MAVProxy (sdrone_bench.py):
```
--master=/dev/ttyACM0            # Pixhawk flight controller (telemetry source)
--master=udpin:0.0.0.0:47004     # LISTEN for decrypted commands FROM proxy  ← ADDED
--out=udp:127.0.0.1:47003        # SEND telemetry TO proxy for encryption
--out=udp:127.0.0.1:47005        # Sniff port for metrics collector
```

### GCS MAVProxy (sgcs_bench.py):
```
--master=udpin:0.0.0.0:47002     # LISTEN for decrypted telemetry FROM proxy  ← FIXED (was udp:)
--out=udp:127.0.0.1:47001        # SEND commands TO proxy for encryption      ← ADDED
--out=udp:127.0.0.1:14552        # Sniff port for metrics collector
--out=udp:127.0.0.1:14550        # QGC/local tools
```

## Complete Bidirectional Flow

### TELEMETRY CHANNEL (Drone → GCS):
```
Pixhawk (/dev/ttyACM0)
    │
    ▼ Serial/USB
┌─────────────────────────────────┐
│  Drone MAVProxy                 │
│  --master=/dev/ttyACM0          │
│  --out=udp:127.0.0.1:47003      │──────┐
└─────────────────────────────────┘      │
                                         ▼ UDP plaintext
┌─────────────────────────────────┐
│  Drone Proxy                    │
│  bind: 127.0.0.1:47003          │◀─────┘ receives from MAVProxy
│  ENCRYPT with session key       │
│  sendto: 192.168.0.104:46011    │──────┐
└─────────────────────────────────┘      │
                                         ▼ UDP encrypted (LAN)
┌─────────────────────────────────┐
│  GCS Proxy                      │
│  bind: 0.0.0.0:46011            │◀─────┘ receives encrypted
│  DECRYPT with session key       │
│  sendto: 127.0.0.1:47002        │──────┐
└─────────────────────────────────┘      │
                                         ▼ UDP plaintext
┌─────────────────────────────────┐
│  GCS MAVProxy                   │
│  --master=udpin:0.0.0.0:47002   │◀─────┘ LISTENS for telemetry
│  --out=udp:127.0.0.1:14552      │──────► Sniff/Metrics
│  --out=udp:127.0.0.1:14550      │──────► QGC
└─────────────────────────────────┘
```

### COMMAND CHANNEL (GCS → Drone):
```
GCS MAVProxy (user commands/heartbeat)
    │
    ▼ --out=udp:127.0.0.1:47001
┌─────────────────────────────────┐
│  GCS Proxy                      │
│  bind: 127.0.0.1:47001          │◀─────┐ receives from MAVProxy
│  ENCRYPT with session key       │      │
│  sendto: 192.168.0.103:46012    │──────┤
└─────────────────────────────────┘      │
                                         ▼ UDP encrypted (LAN)
┌─────────────────────────────────┐
│  Drone Proxy                    │
│  bind: 0.0.0.0:46012            │◀─────┘ receives encrypted
│  DECRYPT with session key       │
│  sendto: 127.0.0.1:47004        │──────┐
└─────────────────────────────────┘      │
                                         ▼ UDP plaintext
┌─────────────────────────────────┐
│  Drone MAVProxy                 │
│  --master=udpin:0.0.0.0:47004   │◀─────┘ LISTENS for commands
│  --master=/dev/ttyACM0          │──────► Pixhawk (executes command)
└─────────────────────────────────┘
```

## Critical Fixes Applied

| Component | Issue | Fix |
|-----------|-------|-----|
| GCS MAVProxy | `--master=udp:` (client/sender mode) | `--master=udpin:` (server/listener mode) |
| GCS MAVProxy | Missing command output | Added `--out=udp:127.0.0.1:47001` |
| Drone MAVProxy | Missing command input | Added `--master=udpin:0.0.0.0:47004` |

## Key Insight

MAVProxy `--master` modes:
- `udp:HOST:PORT` = **CLIENT** mode: MAVProxy SENDS to HOST:PORT
- `udpin:HOST:PORT` = **SERVER** mode: MAVProxy LISTENS on HOST:PORT

The proxies SEND decrypted data TO the MAVProxy ports, so MAVProxy must LISTEN (udpin:), not send (udp:).

## Files Modified
1. `sscheduler/sgcs_bench.py` - Fixed 4 instances of MAVProxy master configuration
2. `sscheduler/sdrone_bench.py` - Added bidirectional command channel support

## Verification Commands

On GCS (after restart):
```powershell
# Check MAVProxy is listening on 47002
netstat -an | findstr "47002"
# Should show: UDP 0.0.0.0:47002 *:*
```

On Drone:
```bash
# Check MAVProxy is listening on 47004
ss -lun | grep 47004
# Should show: udp UNCONN 0 0 0.0.0.0:47004
```
