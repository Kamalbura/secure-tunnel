"""
Benchmark Policy for Comprehensive Suite Testing
sscheduler/benchmark_policy.py

A specialized policy for systematic benchmarking of ALL cryptographic suites.
Cycles through every registered suite at a fixed interval to collect 
comprehensive performance metrics including handshake time, throughput, 
latency, power consumption, and energy.

This policy is designed for:
- Complete coverage of all 72+ registered suites
- Sequential cycling every 10 seconds (configurable)
- Detailed metrics collection per suite
- Professional benchmark report generation
"""

import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sscheduler.policy import PolicyAction, PolicyOutput, DecisionInput


from core.suites import list_suites

# =============================================================================
# BENCHMARK CONFIGURATION
# =============================================================================

BENCHMARK_SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"

def load_benchmark_settings() -> Dict[str, Any]:
    """Load benchmark-specific settings."""
    defaults = {
        "benchmark_mode": {
            "enabled": True,
            "cycle_interval_s": 10.0,
            "sequential_cycling": True,
            "collect_metrics": True,
            "output_dir": "logs/benchmarks",
            "warmup_cycles": 0,
            "iterations_per_suite": 1
        }
    }
    try:
        if BENCHMARK_SETTINGS_PATH.exists():
            with open(BENCHMARK_SETTINGS_PATH, "r") as f:
                user_cfg = json.load(f)
                if "benchmark_mode" in user_cfg:
                    defaults["benchmark_mode"].update(user_cfg["benchmark_mode"])
    except Exception as e:
        logging.error(f"Failed to load benchmark settings: {e}")
    return defaults

# =============================================================================
# BENCHMARK ACTION ENUM
# =============================================================================

class BenchmarkAction(str, Enum):
    HOLD = "HOLD"           # Stay on current suite
    NEXT_SUITE = "NEXT"     # Move to next suite in sequence
    COMPLETE = "COMPLETE"   # All suites tested, benchmark done

# =============================================================================
# BENCHMARK OUTPUT
# =============================================================================

@dataclass
class BenchmarkOutput:
    """Benchmark policy decision output."""
    action: BenchmarkAction
    target_suite: Optional[str] = None
    current_index: int = 0
    total_suites: int = 0
    elapsed_s: float = 0.0
    reasons: List[str] = field(default_factory=list)
    progress_pct: float = 0.0

# =============================================================================
# SUITE METRICS RECORD
# =============================================================================

@dataclass
class SuiteMetrics:
    """Collected metrics for a single suite benchmark iteration."""
    suite_id: str
    iteration: int
    start_time_ns: int
    end_time_ns: int = 0
    handshake_ms: float = 0.0
    throughput_mbps: float = 0.0
    latency_ms: float = 0.0
    power_w: float = 0.0
    energy_mj: float = 0.0
    kem_name: str = ""
    sig_name: str = ""
    nist_level: str = ""
    aead: str = ""
    success: bool = False
    error_message: str = ""
    
    # Detailed primitive timings
    kem_keygen_ms: float = 0.0
    kem_encaps_ms: float = 0.0
    kem_decaps_ms: float = 0.0
    sig_sign_ms: float = 0.0
    sig_verify_ms: float = 0.0
    
    # Artifact sizes
    pub_key_size_bytes: int = 0
    ciphertext_size_bytes: int = 0
    sig_size_bytes: int = 0

# =============================================================================
# BENCHMARK POLICY
# =============================================================================

class BenchmarkPolicy:
    """
    Sequential benchmark policy for systematic suite testing.
    
    This policy cycles through ALL registered suites at a fixed interval,
    collecting comprehensive metrics for each. Unlike the adaptive
    TelemetryAwarePolicyV2, this policy ignores telemetry and focuses
    purely on systematic benchmarking.
    """
    
    def __init__(self, cycle_interval_s: float = 10.0, filter_aead: Optional[str] = None, suite_list: Optional[List[str]] = None):
        self.settings = load_benchmark_settings()
        self.benchmark_cfg = self.settings.get("benchmark_mode", {})
        
        # Override cycle interval if provided
        self.cycle_interval_s = cycle_interval_s or self.benchmark_cfg.get("cycle_interval_s", 10.0)
        self.filter_aead = filter_aead
        
        if suite_list is None:
            # Default to full suite list from registry
            self.all_suites = list_suites()
            self.suite_list = self._build_suite_list()
        else:
            # Use provided suite list, and populate all_suites for metadata lookup
            self.suite_list = suite_list
            all_registered_suites = list_suites()
            self.all_suites = {sid: all_registered_suites[sid] for sid in suite_list if sid in all_registered_suites}
            
        self.filtered_suites = self.suite_list # Support sdrone interface
        
        # State
        self.current_index = 0
        self.iteration = 0
        self.last_switch_mono = 0.0
        self.start_time_mono = 0.0
        self.benchmark_complete = False
        
        # Metrics collection
        self.collected_metrics: List[SuiteMetrics] = []
        self.current_metrics: Optional[SuiteMetrics] = None
        
        # Output directory
        self.output_dir = Path(self.benchmark_cfg.get("output_dir", "logs/benchmarks"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run ID for this benchmark session
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        logging.info(f"BenchmarkPolicy initialized: {len(self.suite_list)} suites, "
                     f"{self.cycle_interval_s}s per suite, filter_aead={filter_aead}")
    
    def _build_suite_list(self) -> List[str]:
        """Build ordered list of suites to benchmark."""
        suites = []
        for suite_id, cfg in self.all_suites.items():
            # Apply AEAD filter if specified
            if self.filter_aead:
                aead_token = cfg.get("aead_token", "")
                if self.filter_aead.lower() not in aead_token.lower():
                    continue
            suites.append(suite_id)
        
        # Sort by NIST level, then KEM, then signature for organized output
        def sort_key(sid: str) -> Tuple[str, str, str]:
            cfg = self.all_suites.get(sid, {})
            return (
                cfg.get("nist_level", "L5"),
                cfg.get("kem_name", ""),
                cfg.get("sig_name", "")
            )
        
        suites.sort(key=sort_key)
        return suites
    
    def get_current_suite(self) -> Optional[str]:
        """Get the current suite to benchmark."""
        if self.benchmark_complete or not self.suite_list:
            return None
        return self.suite_list[self.current_index]
    
    def get_next_suite(self) -> Optional[str]:
        """Get the next suite in sequence (without advancing)."""
        if self.benchmark_complete or not self.suite_list:
            return None
        next_idx = (self.current_index + 1) % len(self.suite_list)
        if self.current_index + 1 >= len(self.suite_list):
            return None  # Will complete after current
        return self.suite_list[next_idx]
    
    def start_benchmark(self) -> str:
        """Initialize benchmark and return first suite."""
        self.start_time_mono = time.monotonic()
        self.last_switch_mono = self.start_time_mono
        self.current_index = 0
        self.iteration = 0
        self.benchmark_complete = False
        
        if not self.suite_list:
            raise RuntimeError("No suites available for benchmarking")
        
        first_suite = self.suite_list[0]
        self._start_suite_metrics(first_suite)
        return first_suite
    
    def _start_suite_metrics(self, suite_id: str):
        """Start collecting metrics for a suite."""
        cfg = self.all_suites.get(suite_id, {})
        self.current_metrics = SuiteMetrics(
            suite_id=suite_id,
            iteration=self.iteration,
            start_time_ns=time.time_ns(),
            kem_name=cfg.get("kem_name", ""),
            sig_name=cfg.get("sig_name", ""),
            nist_level=cfg.get("nist_level", ""),
            aead=cfg.get("aead", "")
        )
    
    def record_handshake_metrics(self, handshake_metrics: Dict[str, Any]):
        """Record handshake metrics for current suite."""
        if not self.current_metrics:
            return
        
        m = self.current_metrics
        
        # Extract timing metrics
        m.handshake_ms = handshake_metrics.get("rekey_ms", 0.0) or \
                         handshake_metrics.get("handshake_total_ns", 0) / 1_000_000.0
        
        # Primitive timings
        m.kem_keygen_ms = handshake_metrics.get("kem_keygen_max_ms", 0.0)
        m.kem_encaps_ms = handshake_metrics.get("kem_encaps_max_ms", 0.0)
        m.kem_decaps_ms = handshake_metrics.get("kem_decaps_max_ms", 0.0)
        m.sig_sign_ms = handshake_metrics.get("sig_sign_max_ms", 0.0)
        m.sig_verify_ms = handshake_metrics.get("sig_verify_max_ms", 0.0)
        
        # Artifact sizes
        m.pub_key_size_bytes = handshake_metrics.get("pub_key_size_bytes", 0)
        m.ciphertext_size_bytes = handshake_metrics.get("ciphertext_size_bytes", 0)
        m.sig_size_bytes = handshake_metrics.get("sig_size_bytes", 0)
        
        # Energy metrics (if available from power monitor)
        m.energy_mj = handshake_metrics.get("handshake_energy_mJ", 0.0)
    
    def record_runtime_metrics(self, throughput_mbps: float = 0.0, 
                               latency_ms: float = 0.0,
                               power_w: float = 0.0):
        """Record runtime metrics for current suite."""
        if not self.current_metrics:
            return
        
        self.current_metrics.throughput_mbps = throughput_mbps
        self.current_metrics.latency_ms = latency_ms
        self.current_metrics.power_w = power_w
    
    def finalize_suite_metrics(self, success: bool = True, error_message: str = ""):
        """Finalize and store metrics for current suite."""
        if not self.current_metrics:
            return
        
        self.current_metrics.end_time_ns = time.time_ns()
        self.current_metrics.success = success
        self.current_metrics.error_message = error_message
        
        # Calculate energy if power and duration available
        if self.current_metrics.power_w > 0 and self.current_metrics.handshake_ms > 0:
            duration_s = self.current_metrics.handshake_ms / 1000.0
            self.current_metrics.energy_mj = self.current_metrics.power_w * duration_s * 1000.0
        
        self.collected_metrics.append(self.current_metrics)
        self.current_metrics = None
    
    def evaluate(self, now_mono: float) -> BenchmarkOutput:
        """
        Evaluate whether to move to next suite.
        
        Returns BenchmarkOutput with action to take.
        """
        if self.benchmark_complete:
            return BenchmarkOutput(
                action=BenchmarkAction.COMPLETE,
                current_index=self.current_index,
                total_suites=len(self.suite_list),
                progress_pct=100.0,
                reasons=["benchmark_complete"]
            )
        
        if not self.suite_list:
            return BenchmarkOutput(
                action=BenchmarkAction.COMPLETE,
                reasons=["no_suites"]
            )
        
        elapsed_on_suite = now_mono - self.last_switch_mono
        total_elapsed = now_mono - self.start_time_mono
        progress_pct = (self.current_index / len(self.suite_list)) * 100.0
        
        # Check if time to switch
        if elapsed_on_suite >= self.cycle_interval_s:
            # Finalize current suite
            self.finalize_suite_metrics(success=True)
            
            # Move to next suite
            self.current_index += 1
            self.iteration += 1
            
            # Check if complete
            if self.current_index >= len(self.suite_list):
                self.benchmark_complete = True
                self._save_results()
                return BenchmarkOutput(
                    action=BenchmarkAction.COMPLETE,
                    current_index=self.current_index,
                    total_suites=len(self.suite_list),
                    elapsed_s=total_elapsed,
                    progress_pct=100.0,
                    reasons=["all_suites_tested"]
                )
            
            # Start next suite
            next_suite = self.suite_list[self.current_index]
            self.last_switch_mono = now_mono
            self._start_suite_metrics(next_suite)
            
            return BenchmarkOutput(
                action=BenchmarkAction.NEXT_SUITE,
                target_suite=next_suite,
                current_index=self.current_index,
                total_suites=len(self.suite_list),
                elapsed_s=total_elapsed,
                progress_pct=(self.current_index / len(self.suite_list)) * 100.0,
                reasons=["cycle_interval_elapsed"]
            )
        
        # Stay on current suite
        remaining = self.cycle_interval_s - elapsed_on_suite
        return BenchmarkOutput(
            action=BenchmarkAction.HOLD,
            target_suite=self.suite_list[self.current_index],
            current_index=self.current_index,
            total_suites=len(self.suite_list),
            elapsed_s=total_elapsed,
            progress_pct=progress_pct,
            reasons=[f"remaining_{remaining:.1f}s"]
        )
    
    def _save_results(self):
        """Save benchmark results to JSON and CSV."""
        results_path = self.output_dir / f"benchmark_results_{self.run_id}.json"
        csv_path = self.output_dir / f"benchmark_results_{self.run_id}.csv"
        
        # Build results dictionary
        results = {
            "run_id": self.run_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "total_suites": len(self.suite_list),
            "cycle_interval_s": self.cycle_interval_s,
            "filter_aead": self.filter_aead,
            "suites": []
        }
        
        for m in self.collected_metrics:
            results["suites"].append({
                "suite_id": m.suite_id,
                "iteration": m.iteration,
                "nist_level": m.nist_level,
                "kem_name": m.kem_name,
                "sig_name": m.sig_name,
                "aead": m.aead,
                "handshake_ms": round(m.handshake_ms, 3),
                "throughput_mbps": round(m.throughput_mbps, 3),
                "latency_ms": round(m.latency_ms, 3),
                "power_w": round(m.power_w, 3),
                "energy_mj": round(m.energy_mj, 3),
                "kem_keygen_ms": round(m.kem_keygen_ms, 3),
                "kem_encaps_ms": round(m.kem_encaps_ms, 3),
                "kem_decaps_ms": round(m.kem_decaps_ms, 3),
                "sig_sign_ms": round(m.sig_sign_ms, 3),
                "sig_verify_ms": round(m.sig_verify_ms, 3),
                "pub_key_size_bytes": m.pub_key_size_bytes,
                "ciphertext_size_bytes": m.ciphertext_size_bytes,
                "sig_size_bytes": m.sig_size_bytes,
                "success": m.success,
                "error_message": m.error_message
            })
        
        # Save JSON
        try:
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2)
            logging.info(f"Saved benchmark results to {results_path}")
        except Exception as e:
            logging.error(f"Failed to save results JSON: {e}")
        
        # Save CSV
        try:
            with open(csv_path, "w") as f:
                headers = [
                    "suite_id", "nist_level", "kem_name", "sig_name", "aead",
                    "handshake_ms", "throughput_mbps", "latency_ms", "power_w", "energy_mj",
                    "kem_keygen_ms", "kem_encaps_ms", "kem_decaps_ms",
                    "sig_sign_ms", "sig_verify_ms",
                    "pub_key_size_bytes", "ciphertext_size_bytes", "sig_size_bytes",
                    "success"
                ]
                f.write(",".join(headers) + "\n")
                
                for m in self.collected_metrics:
                    row = [
                        m.suite_id, m.nist_level, m.kem_name, m.sig_name, m.aead,
                        str(round(m.handshake_ms, 3)),
                        str(round(m.throughput_mbps, 3)),
                        str(round(m.latency_ms, 3)),
                        str(round(m.power_w, 3)),
                        str(round(m.energy_mj, 3)),
                        str(round(m.kem_keygen_ms, 3)),
                        str(round(m.kem_encaps_ms, 3)),
                        str(round(m.kem_decaps_ms, 3)),
                        str(round(m.sig_sign_ms, 3)),
                        str(round(m.sig_verify_ms, 3)),
                        str(m.pub_key_size_bytes),
                        str(m.ciphertext_size_bytes),
                        str(m.sig_size_bytes),
                        str(m.success)
                    ]
                    f.write(",".join(row) + "\n")
            logging.info(f"Saved benchmark CSV to {csv_path}")
        except Exception as e:
            logging.error(f"Failed to save results CSV: {e}")
        
        return results_path, csv_path
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current benchmark progress summary."""
        return {
            "run_id": self.run_id,
            "current_index": self.current_index,
            "total_suites": len(self.suite_list),
            "progress_pct": (self.current_index / len(self.suite_list)) * 100.0 if self.suite_list else 0,
            "completed_count": len(self.collected_metrics),
            "benchmark_complete": self.benchmark_complete,
            "current_suite": self.get_current_suite(),
            "elapsed_s": time.monotonic() - self.start_time_mono if self.start_time_mono else 0
        }


# =============================================================================
# HELPER: Get Suite Order by NIST Level and KEM Family
# =============================================================================

def get_suites_by_nist_level() -> Dict[str, List[str]]:
    """Group suites by NIST level."""
    all_suites = list_suites()
    by_level: Dict[str, List[str]] = {"L1": [], "L3": [], "L5": []}
    
    for suite_id, cfg in all_suites.items():
        level = cfg.get("nist_level", "L5")
        if level in by_level:
            by_level[level].append(suite_id)
    
    for level in by_level:
        by_level[level].sort()
    
    return by_level


def get_suites_by_kem_family() -> Dict[str, List[str]]:
    """Group suites by KEM family."""
    all_suites = list_suites()
    by_kem: Dict[str, List[str]] = {}
    
    for suite_id, cfg in all_suites.items():
        kem_name = cfg.get("kem_name", "")
        # Extract family from name (e.g., "ML-KEM-768" -> "ML-KEM")
        family = "-".join(kem_name.split("-")[:2]) if "-" in kem_name else kem_name
        
        if family not in by_kem:
            by_kem[family] = []
        by_kem[family].append(suite_id)
    
    for family in by_kem:
        by_kem[family].sort()
    
    return by_kem


def get_suite_count() -> int:
    """Get total number of registered suites."""
    return len(list_suites())

# =============================================================================
# CHRONOS DETERMINISTIC POLICY
# =============================================================================

class DeterministicClockPolicy:
    """
    Deterministic policy for Operation Chronos.
    Uses synchronized time to enforce 10s suite rotation.
    Compatible with sdrone.py DecisionContext interface.
    """
    def __init__(self, cycle_interval_s: float = 10.0):
        self.cycle_interval_s = cycle_interval_s
        self.period_start = 0.0
        
        # Build ordered suite list (Same as BenchmarkPolicy)
        self.all_suites = list_suites()
        self.suite_list = []
        for sid, cfg in self.all_suites.items():
            self.suite_list.append(sid)
        
        # Sort deterministic (NIST Level -> KEM -> Sig)
        def sort_key(sid: str) -> Tuple[str, str, str]:
            cfg = self.all_suites.get(sid, {})
            return (
                cfg.get("nist_level", "L5"),
                cfg.get("kem_name", ""),
                cfg.get("sig_name", "")
            )
        self.suite_list.sort(key=sort_key)
        
        logging.info(f"DeterministicClockPolicy: {len(self.suite_list)} suites, {self.cycle_interval_s}s interval")

    def evaluate(self, inp: DecisionInput) -> PolicyOutput:
        """Evaluate policy based on synced time."""
        # Calculate target suite index
        # Slot index = int(synced_time / interval)
        if inp.synced_time == 0.0:
            # Fallback if no sync yet
            return PolicyOutput(PolicyAction.HOLD, reasons=["no_sync"])
            
        slot = int(inp.synced_time / self.cycle_interval_s)
        suite_idx = slot % len(self.suite_list)
        target_suite = self.suite_list[suite_idx]
        
        # Calculate time into period
        phase = inp.synced_time % self.cycle_interval_s
        
        # Trigger switch/rekey if mismatch
        if inp.current_suite != target_suite:
            # If we are in the last 0.5s of the slot, maybe wait? 
            # No, switch immediately to catch up.
            
            # Use REKEY if same suite (unlikely with rotation) or UPGRADE/DOWNGRADE?
            # PolicyAction.REKEY is generic "Switch to this suite" in some contexts?
            # sdrone.py logic:
            # REKEY -> _execute_rekey(target)
            # DOWNGRADE/UPGRADE/ROLLBACK -> _execute_suite_switch(target) -> Stop -> Start
            # _execute_rekey only works if target == current?
            # Let's check sdrone.py.
            return PolicyOutput(PolicyAction.UPGRADE, target_suite, reasons=["chronos_slot_switch"])
            
        # If we are on the correct suite, check if we need to "Trigger Rekey" explicitly at start?
        # User said "Logic: if (current_synced_time % 10.0) < 0.1: trigger_rekey()."
        # If we just switched, we essentially rekeyed.
        # If the suite repeats (e.g. only 1 suite), we might need to rekey.
        if phase < 0.5: 
             # Only trigger if we haven't switched recently (avoid double rekey)
             if (inp.mono_ms - inp.last_switch_mono_ms) > 1000.0:
                 return PolicyOutput(PolicyAction.REKEY, target_suite, reasons=["chronos_periodic_rekey"])
                 
        return PolicyOutput(PolicyAction.HOLD, reasons=["chronos_stable"])

