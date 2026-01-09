"""
Scheduler Integration for Dev Tools

This module provides integration hooks for the dev tools system.
It allows the scheduler to publish state to the data bus without
modifying the core scheduler or policy logic.

Usage:
    # In scheduler initialization:
    from devtools.integration import DevToolsIntegration
    
    integration = DevToolsIntegration.create_if_enabled()
    if integration:
        integration.start()
    
    # In scheduler tick:
    if integration:
        integration.update_policy(current_suite, action, ...)
        integration.update_telemetry(...)

CRITICAL: All methods are no-ops when dev tools are disabled.
The scheduler code can call these unconditionally.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from devtools.data_bus import DataBus, StressLevel
    from devtools.battery_sim import BatteryProvider
    from devtools.dashboard import DevDashboard
    from devtools.config import DevToolsConfig

logger = logging.getLogger("devtools.integration")


class DevToolsIntegration:
    """
    Integration layer between scheduler and dev tools.
    
    This class provides a safe, no-op interface when dev tools are disabled,
    allowing scheduler code to call these methods unconditionally.
    """
    
    def __init__(
        self,
        data_bus: "DataBus",
        battery_provider: Optional["BatteryProvider"] = None,
        dashboard: Optional["DevDashboard"] = None,
        config: Optional["DevToolsConfig"] = None
    ):
        self._data_bus = data_bus
        self._battery_provider = battery_provider
        self._dashboard = dashboard
        self._config = config
        self._enabled = True
        self._started = False
        
        logger.info("DevToolsIntegration created")
    
    @classmethod
    def create_if_enabled(cls) -> Optional["DevToolsIntegration"]:
        """
        Create integration if dev tools are enabled.
        
        Returns:
            DevToolsIntegration if enabled, None otherwise
        """
        try:
            import devtools
            if not devtools.is_enabled():
                logger.debug("Dev tools disabled, integration not created")
                return None
            
            config = devtools.get_config()
            data_bus = devtools.get_data_bus()
            
            battery_provider = None
            if config.battery_simulation.enabled:
                battery_provider = devtools.get_battery_provider()
            
            dashboard = None
            if config.gui.enabled:
                dashboard = devtools.start_dashboard()
            
            return cls(
                data_bus=data_bus,
                battery_provider=battery_provider,
                dashboard=dashboard,
                config=config
            )
            
        except ImportError:
            logger.debug("Dev tools not available")
            return None
        except Exception as e:
            logger.warning(f"Failed to create dev tools integration: {e}")
            return None
    
    def start(self) -> None:
        """Start the integration (battery provider, etc.)."""
        if self._started:
            return
        
        if self._battery_provider:
            self._battery_provider.start()
        
        self._started = True
        logger.info("DevToolsIntegration started")
    
    def stop(self) -> None:
        """Stop all dev tools components."""
        if self._dashboard:
            try:
                self._dashboard.stop()
            except Exception:
                pass
        
        if self._battery_provider:
            try:
                self._battery_provider.stop()
            except Exception:
                pass
        
        if self._data_bus:
            try:
                self._data_bus.stop()
            except Exception:
                pass
        
        self._started = False
        logger.info("DevToolsIntegration stopped")
    
    # =========================================================================
    # State Update Methods (called by scheduler)
    # =========================================================================
    
    def update_policy(
        self,
        current_suite: str,
        current_action: str = "HOLD",
        target_suite: Optional[str] = None,
        reasons: Optional[List[str]] = None,
        confidence: float = 0.0,
        cooldown_remaining_ms: float = 0.0,
        local_epoch: int = 0,
        armed: bool = False
    ) -> None:
        """
        Update policy state in the data bus.
        
        Call this from the scheduler tick after policy evaluation.
        """
        if not self._enabled:
            return
        
        self._data_bus.update_policy(
            current_suite=current_suite,
            current_action=current_action,
            target_suite=target_suite,
            reasons=reasons,
            confidence=confidence,
            cooldown_remaining_ms=cooldown_remaining_ms,
            local_epoch=local_epoch,
            armed=armed
        )
    
    def update_telemetry(
        self,
        rx_pps: float = 0.0,
        gap_p95_ms: float = 0.0,
        blackout_count: int = 0,
        jitter_ms: float = 0.0,
        telemetry_age_ms: float = -1.0,
        sample_count: int = 0
    ) -> None:
        """
        Update telemetry state in the data bus.
        
        Call this from the telemetry receiver or scheduler tick.
        """
        if not self._enabled:
            return
        
        self._data_bus.update_telemetry(
            rx_pps=rx_pps,
            gap_p95_ms=gap_p95_ms,
            blackout_count=blackout_count,
            jitter_ms=jitter_ms,
            telemetry_age_ms=telemetry_age_ms,
            sample_count=sample_count
        )
    
    def update_proxy(
        self,
        encrypted_pps: float = 0.0,
        plaintext_pps: float = 0.0,
        replay_drops: int = 0,
        handshake_status: str = "unknown",
        bytes_encrypted: int = 0,
        bytes_decrypted: int = 0
    ) -> None:
        """
        Update proxy state in the data bus.
        
        Call this from the proxy stats collector.
        """
        if not self._enabled:
            return
        
        self._data_bus.update_proxy(
            encrypted_pps=encrypted_pps,
            plaintext_pps=plaintext_pps,
            replay_drops=replay_drops,
            handshake_status=handshake_status,
            bytes_encrypted=bytes_encrypted,
            bytes_decrypted=bytes_decrypted
        )
    
    def add_event(
        self,
        event_type: str,
        label: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a timeline event.
        
        Event types: "suite_switch", "policy_action", "battery_event", "link_event"
        """
        if not self._enabled:
            return
        
        self._data_bus.add_event(event_type, label, details)
    
    # =========================================================================
    # Battery Provider Access
    # =========================================================================
    
    def get_battery_provider(self) -> Optional["BatteryProvider"]:
        """Get the battery provider (for LocalMonitor override)."""
        return self._battery_provider
    
    def is_battery_simulated(self) -> bool:
        """Check if battery simulation is active."""
        return self._battery_provider is not None and self._battery_provider.is_simulated()
    
    # =========================================================================
    # State Query Methods
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        return {
            "enabled": self._enabled,
            "started": self._started,
            "battery_simulated": self.is_battery_simulated(),
            "gui_active": self._dashboard is not None,
            "bus_stats": self._data_bus.get_stats() if self._data_bus else None
        }


class NullIntegration:
    """
    No-op integration for when dev tools are disabled.
    
    All methods are safe to call and do nothing.
    """
    
    def start(self) -> None:
        pass
    
    def stop(self) -> None:
        pass
    
    def update_policy(self, *args, **kwargs) -> None:
        pass
    
    def update_telemetry(self, *args, **kwargs) -> None:
        pass
    
    def update_proxy(self, *args, **kwargs) -> None:
        pass
    
    def add_event(self, *args, **kwargs) -> None:
        pass
    
    def get_battery_provider(self):
        return None
    
    def is_battery_simulated(self) -> bool:
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        return {"enabled": False}


def get_integration() -> DevToolsIntegration:
    """
    Get a dev tools integration instance.
    
    Returns DevToolsIntegration if enabled, NullIntegration otherwise.
    This allows scheduler code to use the integration unconditionally.
    
    Usage:
        integration = get_integration()
        integration.update_policy(...)  # Safe even if disabled
    """
    integration = DevToolsIntegration.create_if_enabled()
    if integration is None:
        return NullIntegration()
    return integration
