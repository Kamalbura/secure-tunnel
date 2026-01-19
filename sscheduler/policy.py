"""
Scheduling policies for drone-side suite management.

Implements a deterministic, safety-critical state machine for PQC suite selection.
Consumes GCS telemetry (link) and Local telemetry (battery/thermal).
"""

import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.suites import list_suites

# =============================================================================
# SUITE TIER MAPPING
# =============================================================================

# Tier 0 = lightest/fastest, higher = heavier/slower
# NIST L1 < L3 < L5; within level: aesgcm < chacha < ascon (ARM performance)
def get_suite_tier(suite_name: str) -> int:
    """Map suite name to numeric tier for upgrade/downgrade decisions."""
    # Extract NIST level from suite name pattern: cs-<kem>-<aead>-<sig>
    # Level hints: mlkem512/hqc128/mceliece348864 = L1
    #              mlkem768/hqc192/mceliece460896 = L3
    #              mlkem1024/hqc256/mceliece8192128 = L5
    name_lower = suite_name.lower()
    
    # NIST level base tier
    level_tier = 0
    if "512" in name_lower or "128" in name_lower or "348864" in name_lower:
        level_tier = 0  # L1
    elif "768" in name_lower or "192" in name_lower or "460896" in name_lower:
        level_tier = 10  # L3
    elif "1024" in name_lower or "256" in name_lower or "8192128" in name_lower:
        level_tier = 20  # L5
    
    # AEAD sub-tier (within level)
    aead_tier = 0
    if "aesgcm" in name_lower:
        aead_tier = 0
    elif "chacha" in name_lower:
        aead_tier = 1
    elif "ascon" in name_lower:
        aead_tier = 2
    
    # KEM complexity sub-tier
    kem_tier = 0
    if "mlkem" in name_lower:
        kem_tier = 0
    elif "hqc" in name_lower:
        kem_tier = 3
    elif "frodokem" in name_lower:
        kem_tier = 4
    elif "classicmceliece" in name_lower or "mceliece" in name_lower:
        kem_tier = 5
    elif "sntrup" in name_lower:
        kem_tier = 2
    
    return level_tier + kem_tier + aead_tier

# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"

def load_settings() -> Dict[str, Any]:
    defaults = {
        "mission_criticality": "medium",
        "max_nist_level": "L5",
        "allowed_aead": "aesgcm",
        "battery": {"critical_mv": 14000, "low_mv": 14800, "warn_mv": 15200, "rate_warn_mv_per_min": 500},
        "thermal": {"critical_c": 80.0, "warn_c": 70.0, "rate_warn_c_per_min": 5.0},
        "link": {"min_pps": 5.0, "max_gap_ms": 1000.0, "max_blackout_count": 3},
        # Rekey window and limits: default to short 5-minute window in dev
        # `window_s` defines the sliding window (seconds) for counting recent
        # successful rekeys. `max_per_window` is the allowed number of
        # successful rekeys within that window.
        "rekey": {"min_stable_s": 60.0, "max_per_window": 5, "window_s": 300, "blacklist_ttl_s": 1800},
        "hysteresis": {"downgrade_s": 5.0, "upgrade_s": 30.0}
    }
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r") as f:
                user_cfg = json.load(f)
                # Deep merge simple dicts
                for k, v in user_cfg.items():
                    if isinstance(v, dict) and k in defaults:
                        defaults[k].update(v)
                    else:
                        defaults[k] = v
    except Exception as e:
        logging.error(f"Failed to load settings.json: {e}")
    return defaults

SETTINGS = load_settings()

# =============================================================================
# ACTION ENUM
# =============================================================================

class PolicyAction(str, Enum):
    HOLD = "HOLD"
    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"
    REKEY = "REKEY"
    ROLLBACK = "ROLLBACK"

# =============================================================================
# DECISION CONTEXT INPUT (immutable snapshot)
# =============================================================================

@dataclass(frozen=True)
class DecisionInput:
    """Immutable snapshot of system state for policy evaluation."""
    mono_ms: float
    
    # Link Telemetry (GCS -> Drone)
    telemetry_valid: bool
    telemetry_age_ms: float
    sample_count: int
    rx_pps_median: float
    gap_p95_ms: float
    silence_max_ms: float
    jitter_ms: float
    blackout_count: int
    
    # Local Telemetry (Drone Sensors)
    battery_mv: int
    battery_roc: float
    temp_c: float
    temp_roc: float
    armed: bool
    
    # State
    current_suite: str
    local_epoch: int
    last_switch_mono_ms: float
    cooldown_until_mono_ms: float
    
    # Chronos Sync
    synced_time: float = 0.0


# =============================================================================
# POLICY OUTPUT
# =============================================================================

@dataclass
class PolicyOutput:
    """Deterministic policy decision."""
    action: PolicyAction
    target_suite: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    cooldown_remaining_ms: float = 0.0

# =============================================================================
# TELEMETRY-AWARE POLICY V2 (Robust)
# =============================================================================

class TelemetryAwarePolicyV2:
    def __init__(self):
        self.settings = SETTINGS
        self.all_suites = list_suites()
        self.filtered_suites = self._filter_suites()
        
        # State
        self.blacklist: Dict[str, float] = {} # suite -> expiry_mono
        self.rekey_timestamps: List[float] = [] # mono timestamps
        self.hysteresis_start: Dict[str, float] = {} # condition -> start_mono
        self.previous_suite: Optional[str] = None
        
        logging.info(f"Policy initialized with {len(self.filtered_suites)} suites (AEAD={self.settings['allowed_aead']})")

    def _filter_suites(self) -> List[str]:
        """Filter suites based on settings (AEAD, NIST level)."""
        allowed_aead = self.settings.get("allowed_aead", "aesgcm").lower()
        max_nist = self.settings.get("max_nist_level", "L5")
        
        # Map L1/L3/L5 to comparable ints
        levels = {"L1": 1, "L3": 3, "L5": 5}
        max_level_int = levels.get(max_nist, 5)
        
        candidates = []
        for sid, cfg in self.all_suites.items():
            # AEAD Filter
            if allowed_aead not in cfg["aead_token"].lower():
                continue
            
            # NIST Level Filter
            lvl = cfg.get("nist_level", "L5")
            if levels.get(lvl, 5) > max_level_int:
                continue
                
            candidates.append(sid)
            
        # Sort by tier (complexity)
        candidates.sort(key=get_suite_tier)
        return candidates

    def _is_blacklisted(self, suite: str, now_mono: float) -> bool:
        if suite in self.blacklist:
            if now_mono < self.blacklist[suite]:
                return True
            del self.blacklist[suite]
        return False

    def _add_blacklist(self, suite: str, now_mono: float):
        ttl = self.settings["rekey"]["blacklist_ttl_s"]
        self.blacklist[suite] = now_mono + ttl
        logging.warning(f"Blacklisted {suite} for {ttl}s")

    def _check_hysteresis(self, condition_key: str, active: bool, now_mono: float, duration_s: float) -> bool:
        """Return True if condition has been active for duration_s."""
        if not active:
            self.hysteresis_start.pop(condition_key, None)
            return False
        
        start = self.hysteresis_start.get(condition_key)
        if start is None:
            self.hysteresis_start[condition_key] = now_mono
            return False
        
        return (now_mono - start) >= duration_s

    def _find_suite(self, current: str, direction: int, now_mono: float) -> Optional[str]:
        """Find adjacent suite in filtered pool, skipping blacklisted."""
        if current not in self.filtered_suites:
            # If current not in pool (e.g. config changed), pick closest valid
            if not self.filtered_suites: return None
            return self.filtered_suites[0] # Fallback to lowest
            
        idx = self.filtered_suites.index(current)
        new_idx = idx + direction
        
        # Bounds check
        if new_idx < 0 or new_idx >= len(self.filtered_suites):
            return None
            
        candidate = self.filtered_suites[new_idx]
        if self._is_blacklisted(candidate, now_mono):
            # Try skipping one more? No, simple adjacent for now to avoid jumps
            return None
            
        return candidate

    def evaluate(self, inp: DecisionInput) -> PolicyOutput:
        now_mono = inp.mono_ms / 1000.0
        reasons = []
        
        # 0. Update previous suite tracking
        if self.previous_suite != inp.current_suite:
            # If we just switched, keep track (unless it was a rekey of same)
            pass 
            
        # 1. Safety Gates (Immediate HOLD)
        if not inp.telemetry_valid or inp.telemetry_age_ms > 2000:
            return PolicyOutput(PolicyAction.HOLD, reasons=["telemetry_stale"])
            
        # 2. Emergency Safety (Battery/Temp) -> FAST DOWNGRADE
        batt_crit = inp.battery_mv < self.settings["battery"]["critical_mv"]
        temp_crit = inp.temp_c > self.settings["thermal"]["critical_c"]
        
        if (batt_crit or temp_crit) and inp.current_suite != self.filtered_suites[0]:
            # Emergency: jump to lowest tier immediately
            target = self.filtered_suites[0]
            return PolicyOutput(PolicyAction.DOWNGRADE, target, reasons=["safety_critical"])

        # 3. Link Failure -> ROLLBACK/BLACKLIST
        # If blackout persists shortly after a switch, assume suite fault
        time_since_switch = (inp.mono_ms - inp.last_switch_mono_ms) / 1000.0
        if time_since_switch < 30.0 and inp.blackout_count > self.settings["link"]["max_blackout_count"]:
            self._add_blacklist(inp.current_suite, now_mono)
            # Try to go back to previous or downgrade
            target = self._find_suite(inp.current_suite, -1, now_mono)
            if target:
                return PolicyOutput(PolicyAction.DOWNGRADE, target, reasons=["blackout_rollback"])

        # 4. Cooldown Gate
        if inp.cooldown_until_mono_ms > inp.mono_ms:
            return PolicyOutput(PolicyAction.HOLD, reasons=["cooldown"])

        # 5. Link Degradation -> DOWNGRADE (with Hysteresis)
        link_bad = (
            inp.gap_p95_ms > self.settings["link"]["max_gap_ms"] or
            inp.rx_pps_median < self.settings["link"]["min_pps"]
        )
        
        if self._check_hysteresis("link_bad", link_bad, now_mono, self.settings["hysteresis"]["downgrade_s"]):
            target = self._find_suite(inp.current_suite, -1, now_mono)
            if target:
                return PolicyOutput(PolicyAction.DOWNGRADE, target, reasons=["link_degraded_persistent"])

        # 6. Thermal/Battery Warning -> DOWNGRADE (with Hysteresis)
        # Check rates
        temp_rising = inp.temp_roc > self.settings["thermal"]["rate_warn_c_per_min"]
        batt_falling = inp.battery_roc < -self.settings["battery"]["rate_warn_mv_per_min"] # negative slope
        
        stress = temp_rising or batt_falling or (inp.temp_c > self.settings["thermal"]["warn_c"])
        
        if self._check_hysteresis("stress", stress, now_mono, self.settings["hysteresis"]["downgrade_s"]):
             target = self._find_suite(inp.current_suite, -1, now_mono)
             if target:
                 return PolicyOutput(PolicyAction.DOWNGRADE, target, reasons=["thermal_battery_stress"])

        # 7. Proactive Rekey / Upgrade
        # Only if stable for long time
        stable_time = (inp.mono_ms - inp.last_switch_mono_ms) / 1000.0
        if stable_time > self.settings["rekey"]["min_stable_s"]:
            # Check rekey limit (do NOT record the rekey here; record only after
            # successful execution to avoid counting failed attempts)
            window_s = float(self.settings["rekey"].get("window_s", 300))
            window_ago = now_mono - window_s
            self.rekey_timestamps = [t for t in self.rekey_timestamps if t > window_ago]

            max_per = int(self.settings["rekey"].get("max_per_window", self.settings["rekey"].get("max_per_hour", 5)))
            if len(self.rekey_timestamps) < max_per:
                # Request a rekey; actual recording happens after success
                return PolicyOutput(PolicyAction.REKEY, inp.current_suite, reasons=["proactive_rekey"])
                
        # 8. Upgrade (Very Conservative)
        # Only if disarmed, very stable, and no stress
        if not inp.armed and not stress and not link_bad:
             if self._check_hysteresis("upgrade_ok", True, now_mono, self.settings["hysteresis"]["upgrade_s"]):
                 target = self._find_suite(inp.current_suite, 1, now_mono)
                 if target:
                     return PolicyOutput(PolicyAction.UPGRADE, target, reasons=["stable_upgrade"])

        return PolicyOutput(PolicyAction.HOLD, reasons=["nominal"])

    def record_rekey(self, now_mono: float) -> None:
        """Record a successful rekey timestamp (mono seconds).

        This should be called by the executor after the rekey completed
        successfully to enforce the per-hour limit.
        """
        self.rekey_timestamps.append(now_mono)


# =============================================================================
# SIMPLE POLICIES USED BY MAV SCHEDULER
# =============================================================================

class LinearLoopPolicy:
    """Deterministic round-robin suite policy."""

    def __init__(self, suites: List[str], duration_s: float = 10.0):
        self.suites = list(suites)
        self._idx = 0
        self._duration_s = float(duration_s)

    def next_suite(self) -> str:
        if not self.suites:
            raise RuntimeError("No suites configured")
        suite = self.suites[self._idx % len(self.suites)]
        self._idx += 1
        return suite

    def get_duration(self) -> float:
        return self._duration_s


class RandomPolicy:
    """Random suite selection policy."""

    def __init__(self, suites: List[str], duration_s: float = 10.0):
        import random
        self._rng = random.Random()
        self.suites = list(suites)
        self._duration_s = float(duration_s)

    def next_suite(self) -> str:
        if not self.suites:
            raise RuntimeError("No suites configured")
        return self._rng.choice(self.suites)

    def get_duration(self) -> float:
        return self._duration_s


class ManualOverridePolicy:
    """Manual suite override with fallback to linear loop."""

    def __init__(self, suites: List[str], duration_s: float = 10.0):
        self.suites = list(suites)
        self._duration_s = float(duration_s)
        self._override: Optional[str] = None
        self._idx = 0

    def set_override(self, suite_name: Optional[str]) -> None:
        if suite_name is None:
            self._override = None
            return
        if suite_name not in self.suites:
            raise ValueError("Unknown suite override")
        self._override = suite_name

    def next_suite(self) -> str:
        if not self.suites:
            raise RuntimeError("No suites configured")
        if self._override:
            return self._override
        suite = self.suites[self._idx % len(self.suites)]
        self._idx += 1
        return suite

    def get_duration(self) -> float:
        return self._duration_s
