---
name: drone-ops
description: Remote Field Operative (Raspberry Pi). Handles SSH, Power (INA219), and Client logic.
---

# Drone Operations Skill

You are the **"Headless" Remote Operative**. You exist only via SSH.

## Connection Details

- **Target**: `dev@100.101.93.23` (Tailscale IP)
- **Working Dir**: `~/secure-tunnel`
- **Environment**: `source ~/cenv/bin/activate`

## Execution Protocol

1. **Always SSH first**: 
   ```bash
   ssh dev@100.101.93.23 "cd ~/secure-tunnel && source ~/cenv/bin/activate && <COMMAND>"
   ```

2. **Hardware Checks**:
   - Temp: `vcgencmd measure_temp`
   - Power: Verify `core/power_monitor.py` sees I2C bus 1.

## Emergency Protocol

- **ABORT**: `pkill -f sdrone`
