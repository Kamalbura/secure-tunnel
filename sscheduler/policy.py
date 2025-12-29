"""
Scheduling policies for drone-side suite management.

Policies consume DecisionContext summaries and return deterministic actions.
All time values use monotonic clock to avoid wall-clock jumps.
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# THRESHOLD CONSTANTS (tune here, not in code)
# =============================================================================

# Telemetry freshness: stale if age exceeds this (ms)
TH_TELEMETRY_STALE_MS = 1500.0

# Minimum samples in window for confidence
TH_MIN_SAMPLES = 3

# Link stability thresholds
TH_GAP_P95_MS = 200.0        # p95 inter-arrival gap limit
TH_SILENCE_MAX_MS = 300.0    # max silence before link_unstable
TH_JITTER_MS = 50.0          # jitter threshold for stability

# Receiver health thresholds
TH_GCS_CPU_MEDIAN = 85.0     # median CPU too high -> receiver_stressed
TH_GCS_CPU_P95 = 95.0        # p95 CPU too high -> severe_stress

# Heartbeat / failsafe thresholds (from telemetry packet)
TH_HEARTBEAT_AGE_MS = 2000.0 # MAVLink heartbeat age limit

# Cooldown durations (seconds)
COOLDOWN_SWITCH_S = 5.0      # after suite switch
COOLDOWN_REKEY_S = 10.0      # after rekey
COOLDOWN_DOWNGRADE_S = 8.0   # after downgrade

# Dwell requirements for upgrade (seconds of stable link)
DWELL_UPGRADE_S = 30.0       # stable duration required before upgrade
DWELL_REKEY_S = 60.0         # stable duration required before proactive rekey

# Confidence thresholds
TH_CONFIDENCE_LOW = 0.5      # below this -> HOLD
TH_CONFIDENCE_UPGRADE = 0.8  # above this -> allow upgrade


# =============================================================================
# ACTION ENUM
# =============================================================================

class PolicyAction(str, Enum):
    HOLD = "HOLD"
    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"
    REKEY = "REKEY"


# =============================================================================
# DECISION CONTEXT INPUT (immutable snapshot)
# =============================================================================

@dataclass(frozen=True)
class DecisionInput:
    """Immutable snapshot of system state for policy evaluation."""
    mono_ms: float
    
    # Telemetry window stats
    telemetry_valid: bool
    telemetry_age_ms: float
    sample_count: int
    rx_pps_median: float
    gap_p95_ms: float
    silence_max_ms: float
    jitter_ms: float
    gcs_cpu_median: float
    gcs_cpu_p95: float
    telemetry_last_seq: int
    
    # Receiver health (from latest telemetry packet)
    mavproxy_alive: bool = True
    collector_alive: bool = True
    
    # Flight safety (from latest telemetry or local sensors)
    heartbeat_age_ms: float = 0.0
    failsafe_active: bool = False
    armed: bool = False
    armed_duration_s: float = 0.0
    
    # Synchronization (from telemetry epoch/suite fields)
    remote_suite: Optional[str] = None
    remote_epoch: int = 0
    
    # Current state
    expected_suite: str = ""
    current_tier: int = 0
    local_epoch: int = 0
    
    # Cooldowns
    last_switch_mono_ms: float = 0.0
    cooldown_until_mono_ms: float = 0.0


# =============================================================================
# POLICY OUTPUT
# =============================================================================

@dataclass
class PolicyOutput:
    """Deterministic policy decision."""
    action: PolicyAction
    target_suite: Optional[str] = None
    target_tier: Optional[int] = None
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    cooldown_remaining_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "target_suite": self.target_suite,
            "target_tier": self.target_tier,
            "reasons": self.reasons,
            "confidence": round(self.confidence, 3),
            "cooldown_remaining_ms": round(self.cooldown_remaining_ms, 1),
        }


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


def find_adjacent_suite(current_suite: str, suites: List[str], direction: int) -> Optional[str]:
    """Find next suite in tier order. direction: -1 for downgrade, +1 for upgrade."""
    if not suites:
        return None
    
    current_tier = get_suite_tier(current_suite)
    candidates: List[Tuple[int, str]] = []
    
    for s in suites:
        tier = get_suite_tier(s)
        if direction < 0 and tier < current_tier:
            candidates.append((tier, s))
        elif direction > 0 and tier > current_tier:
            candidates.append((tier, s))
    
    if not candidates:
        return None
    
    # Sort by tier and pick closest
    candidates.sort(key=lambda x: abs(x[0] - current_tier))
    return candidates[0][1]


# =============================================================================
# TELEMETRY-AWARE POLICY V1
# =============================================================================

class TelemetryAwarePolicyV1:
    """
    Deterministic policy that consumes DecisionInput and produces PolicyOutput.
    
    Invariant evaluation order (short-circuit on first HOLD):
    A) Telemetry stale OR low confidence -> HOLD
    B) Receiver not healthy (mavproxy_alive=False OR collector_alive=False) -> HOLD
    C) Flight safety gate (heartbeat_age too high OR failsafe) -> HOLD
    D) Desync (remote_suite/epoch mismatch) -> HOLD + reconcile hook
    E) Cooldown active -> HOLD
    
    Then reactive:
    F) Severe link degradation persisting -> DOWNGRADE (if possible)
    
    Then proactive:
    G) Stable for DWELL_REKEY_S and conditions met -> REKEY
    H) Stable for DWELL_UPGRADE_S and conditions met -> UPGRADE
    
    Otherwise HOLD.
    """
    
    def __init__(self, suites: List[str]):
        self.suites = list(suites)
        self._stable_since_mono_ms: float = 0.0
        self._link_degraded_since_mono_ms: float = 0.0
    
    def evaluate(self, inp: DecisionInput) -> PolicyOutput:
        """Evaluate policy against input snapshot. Pure function (no side effects)."""
        reasons: List[str] = []
        now_ms = inp.mono_ms
        
        # Compute confidence from sample count
        expected_samples = max(1, int(5.0 * 5))  # 5s window at ~5 Hz
        confidence = min(1.0, inp.sample_count / expected_samples) if inp.telemetry_valid else 0.0
        
        # Cooldown remaining
        cooldown_remaining_ms = max(0.0, inp.cooldown_until_mono_ms - now_ms)
        
        def hold(reason: str) -> PolicyOutput:
            reasons.append(reason)
            return PolicyOutput(
                action=PolicyAction.HOLD,
                reasons=reasons,
                confidence=confidence,
                cooldown_remaining_ms=cooldown_remaining_ms,
            )
        
        # --- A) Telemetry freshness gate ---
        if not inp.telemetry_valid or inp.telemetry_age_ms < 0:
            return hold("telemetry_invalid")
        
        if inp.telemetry_age_ms > TH_TELEMETRY_STALE_MS:
            return hold("telemetry_stale")
        
        if inp.sample_count < TH_MIN_SAMPLES:
            return hold("insufficient_samples")
        
        if confidence < TH_CONFIDENCE_LOW:
            return hold("low_confidence")
        
        # --- B) Receiver health gate ---
        if not inp.mavproxy_alive:
            return hold("mavproxy_dead")
        
        if not inp.collector_alive:
            return hold("collector_dead")
        
        # --- C) Flight safety gate ---
        if inp.heartbeat_age_ms > TH_HEARTBEAT_AGE_MS:
            return hold("heartbeat_stale")
        
        if inp.failsafe_active:
            return hold("failsafe_active")
        
        # --- D) Desync gate ---
        if inp.remote_suite and inp.remote_suite != inp.expected_suite:
            reasons.append("suite_desync")
            return PolicyOutput(
                action=PolicyAction.HOLD,
                reasons=reasons + [f"remote={inp.remote_suite},local={inp.expected_suite}"],
                confidence=confidence,
                cooldown_remaining_ms=cooldown_remaining_ms,
            )
        
        if inp.remote_epoch != 0 and inp.remote_epoch != inp.local_epoch:
            reasons.append("epoch_desync")
            return PolicyOutput(
                action=PolicyAction.HOLD,
                reasons=reasons + [f"remote_epoch={inp.remote_epoch},local={inp.local_epoch}"],
                confidence=confidence,
                cooldown_remaining_ms=cooldown_remaining_ms,
            )
        
        # --- E) Cooldown gate ---
        if cooldown_remaining_ms > 0:
            return hold("cooldown_active")
        
        # --- Assess link quality ---
        link_stable = (
            inp.gap_p95_ms <= TH_GAP_P95_MS and
            inp.silence_max_ms <= TH_SILENCE_MAX_MS and
            inp.jitter_ms <= TH_JITTER_MS
        )
        
        receiver_ok = inp.gcs_cpu_median < TH_GCS_CPU_MEDIAN
        severe_stress = inp.gcs_cpu_p95 >= TH_GCS_CPU_P95
        
        # --- F) Reactive downgrade ---
        if not link_stable or severe_stress:
            # Check if degradation is persistent (would need tracking over time)
            # For now, immediate downgrade if severe
            if severe_stress or inp.silence_max_ms > TH_SILENCE_MAX_MS * 1.5:
                target = find_adjacent_suite(inp.expected_suite, self.suites, direction=-1)
                if target:
                    return PolicyOutput(
                        action=PolicyAction.DOWNGRADE,
                        target_suite=target,
                        target_tier=get_suite_tier(target),
                        reasons=["link_degraded", f"cpu_p95={inp.gcs_cpu_p95:.1f}", f"silence={inp.silence_max_ms:.0f}ms"],
                        confidence=confidence,
                        cooldown_remaining_ms=0.0,
                    )
                else:
                    return hold("degraded_no_lower_tier")
        
        # --- G) Proactive rekey (rare) ---
        # Rekey if stable for a long time, not armed or armed stable
        stable_duration_ms = now_ms - inp.last_switch_mono_ms
        if stable_duration_ms > DWELL_REKEY_S * 1000.0:
            if link_stable and receiver_ok and confidence >= TH_CONFIDENCE_UPGRADE:
                if not inp.armed or inp.armed_duration_s > 60.0:
                    return PolicyOutput(
                        action=PolicyAction.REKEY,
                        target_suite=inp.expected_suite,  # same suite
                        reasons=["proactive_rekey", f"stable_for={stable_duration_ms/1000:.0f}s"],
                        confidence=confidence,
                        cooldown_remaining_ms=0.0,
                    )
        
        # --- H) Proactive upgrade (very conservative) ---
        if stable_duration_ms > DWELL_UPGRADE_S * 1000.0:
            if link_stable and receiver_ok and confidence >= TH_CONFIDENCE_UPGRADE:
                if not inp.armed:  # only upgrade when disarmed
                    target = find_adjacent_suite(inp.expected_suite, self.suites, direction=+1)
                    if target:
                        return PolicyOutput(
                            action=PolicyAction.UPGRADE,
                            target_suite=target,
                            target_tier=get_suite_tier(target),
                            reasons=["stable_upgrade", f"stable_for={stable_duration_ms/1000:.0f}s"],
                            confidence=confidence,
                            cooldown_remaining_ms=0.0,
                        )
        
        # --- Default: HOLD (all is well) ---
        return PolicyOutput(
            action=PolicyAction.HOLD,
            reasons=["nominal"],
            confidence=confidence,
            cooldown_remaining_ms=cooldown_remaining_ms,
        )


# =============================================================================
# LEGACY POLICIES (backward compatibility)
# =============================================================================

class SchedulingPolicy:
    """Base class for all scheduling logic."""
    def __init__(self, suites):
        self.suites = list(suites)
        self.current_index = -1

    def next_suite(self):
        """Returns the next suite name to run."""
        raise NotImplementedError("Must implement next_suite")

    def get_duration(self):
        """Returns duration in seconds for the current run."""
        return 10.0  # Default


class LinearLoopPolicy(SchedulingPolicy):
    """Cycles through suites 0 to N, then restarts."""
    def next_suite(self):
        self.current_index = (self.current_index + 1) % len(self.suites)
        return self.suites[self.current_index]


class RandomPolicy(SchedulingPolicy):
    """Picks a random suite every time."""
    def next_suite(self):
        return random.choice(self.suites)


class ManualOverridePolicy(SchedulingPolicy):
    """Runs a specific index repeatedly."""
    def __init__(self, suites, fixed_index=0):
        super().__init__(suites)
        self.fixed_index = fixed_index

    def next_suite(self):
        safe_index = self.fixed_index % len(self.suites)
        return self.suites[safe_index]

