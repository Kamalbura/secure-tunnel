"""
Dev Tools Configuration Loader

Loads dev_tools configuration from settings.json.
Provides strongly-typed configuration dataclasses.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("devtools.config")

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"


@dataclass
class BatterySimConfig:
    """Battery simulation configuration."""
    enabled: bool = False
    default_mode: str = "stable"
    start_mv: int = 16000
    min_mv: int = 13000
    max_mv: int = 17000
    
    # Mode-specific defaults
    slow_drain_mv_per_sec: float = 5.0      # ~300 mV/min
    fast_drain_mv_per_sec: float = 20.0     # ~1200 mV/min  
    throttle_drain_factor: float = 2.0      # Multiplier under load
    step_drop_mv: int = 2000                # Sudden voltage drop
    recovery_mv_per_sec: float = 10.0       # Recovery rate
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BatterySimConfig":
        return cls(
            enabled=d.get("enabled", False),
            default_mode=d.get("default_mode", "stable"),
            start_mv=d.get("start_mv", 16000),
            min_mv=d.get("min_mv", 13000),
            max_mv=d.get("max_mv", 17000),
            slow_drain_mv_per_sec=d.get("slow_drain_mv_per_sec", 5.0),
            fast_drain_mv_per_sec=d.get("fast_drain_mv_per_sec", 20.0),
            throttle_drain_factor=d.get("throttle_drain_factor", 2.0),
            step_drop_mv=d.get("step_drop_mv", 2000),
            recovery_mv_per_sec=d.get("recovery_mv_per_sec", 10.0),
        )


@dataclass
class GuiConfig:
    """GUI dashboard configuration."""
    enabled: bool = False
    refresh_hz: float = 5.0
    window_width: int = 1200
    window_height: int = 800
    timeline_points: int = 300  # ~60 seconds at 5Hz
    graph_update_hz: float = 2.0  # Graph update rate (can be slower than data)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GuiConfig":
        return cls(
            enabled=d.get("enabled", False),
            refresh_hz=d.get("refresh_hz", 5.0),
            window_width=d.get("window_width", 1200),
            window_height=d.get("window_height", 800),
            timeline_points=d.get("timeline_points", 300),
            graph_update_hz=d.get("graph_update_hz", 2.0),
        )


@dataclass
class DevToolsConfig:
    """Root dev tools configuration."""
    enabled: bool = False
    battery_simulation: BatterySimConfig = field(default_factory=BatterySimConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    
    # Data bus settings
    bus_history_size: int = 1000  # Samples to retain
    bus_log_enabled: bool = False
    bus_log_path: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DevToolsConfig":
        return cls(
            enabled=d.get("enabled", False),
            battery_simulation=BatterySimConfig.from_dict(d.get("battery_simulation", {})),
            gui=GuiConfig.from_dict(d.get("gui", {})),
            bus_history_size=d.get("bus_history_size", 1000),
            bus_log_enabled=d.get("bus_log_enabled", False),
            bus_log_path=d.get("bus_log_path"),
        )


def load_devtools_config() -> DevToolsConfig:
    """
    Load dev tools configuration from settings.json.
    
    Returns:
        DevToolsConfig with enabled=False if section missing or error
    """
    try:
        if not SETTINGS_PATH.exists():
            logger.debug(f"settings.json not found at {SETTINGS_PATH}")
            return DevToolsConfig(enabled=False)
        
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        dev_tools_section = data.get("dev_tools", {})
        
        if not dev_tools_section:
            logger.debug("No dev_tools section in settings.json")
            return DevToolsConfig(enabled=False)
        
        config = DevToolsConfig.from_dict(dev_tools_section)
        logger.info(f"Loaded dev_tools config: enabled={config.enabled}, "
                   f"battery_sim={config.battery_simulation.enabled}, "
                   f"gui={config.gui.enabled}")
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in settings.json: {e}")
        return DevToolsConfig(enabled=False)
    except Exception as e:
        logger.error(f"Failed to load dev_tools config: {e}")
        return DevToolsConfig(enabled=False)


def save_devtools_config(config: DevToolsConfig) -> bool:
    """
    Save dev tools configuration back to settings.json.
    
    Preserves all other settings in the file.
    
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Load existing settings
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        
        # Update dev_tools section
        data["dev_tools"] = {
            "enabled": config.enabled,
            "battery_simulation": {
                "enabled": config.battery_simulation.enabled,
                "default_mode": config.battery_simulation.default_mode,
                "start_mv": config.battery_simulation.start_mv,
                "min_mv": config.battery_simulation.min_mv,
                "max_mv": config.battery_simulation.max_mv,
                "slow_drain_mv_per_sec": config.battery_simulation.slow_drain_mv_per_sec,
                "fast_drain_mv_per_sec": config.battery_simulation.fast_drain_mv_per_sec,
                "throttle_drain_factor": config.battery_simulation.throttle_drain_factor,
                "step_drop_mv": config.battery_simulation.step_drop_mv,
                "recovery_mv_per_sec": config.battery_simulation.recovery_mv_per_sec,
            },
            "gui": {
                "enabled": config.gui.enabled,
                "refresh_hz": config.gui.refresh_hz,
                "window_width": config.gui.window_width,
                "window_height": config.gui.window_height,
                "timeline_points": config.gui.timeline_points,
                "graph_update_hz": config.gui.graph_update_hz,
            },
            "bus_history_size": config.bus_history_size,
            "bus_log_enabled": config.bus_log_enabled,
            "bus_log_path": config.bus_log_path,
        }
        
        # Write back
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        logger.info("Saved dev_tools configuration")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save dev_tools config: {e}")
        return False
