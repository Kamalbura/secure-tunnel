"""
Development-Only Tooling for PQC Drone-GCS Secure Proxy

THIS MODULE IS FOR LAB / LAPTOP TESTING ONLY.
When disabled, production behavior remains IDENTICAL to the baseline codebase.

Architecture:
    devtools/
    ├── __init__.py           # Enable/disable logic, safe imports
    ├── config.py             # Dev tools configuration loader
    ├── data_bus.py           # Thread-safe observability bus (single source of truth)
    ├── battery_sim.py        # Battery provider abstraction + simulation modes
    ├── battery_bridge.py     # Non-invasive injection bridge for LocalMonitor
    ├── dashboard.py          # Tkinter GUI dashboard
    └── launcher.py           # Entry point for dev mode

Safety Guarantees:
    1. All features controlled via settings.json["dev_tools"]["enabled"]
    2. When disabled, NO dev code paths execute
    3. Production scheduler/policy logic is NEVER modified
    4. GUI cannot affect policy decisions
    5. Battery simulation only active when explicitly enabled

Usage:
    # In settings.json:
    {
        "dev_tools": {
            "enabled": true,
            "battery_simulation": {"enabled": true, "default_mode": "stable"},
            "gui": {"enabled": true, "refresh_hz": 5}
        }
    }
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

# Lazy imports to avoid loading heavy modules when disabled
if TYPE_CHECKING:
    from devtools.config import DevToolsConfig
    from devtools.data_bus import DataBus
    from devtools.battery_sim import BatteryProvider
    from devtools.dashboard import DevDashboard

__version__ = "1.0.0"
__all__ = [
    "is_enabled",
    "get_config",
    "get_data_bus",
    "get_battery_provider",
    "start_dashboard",
    "stop_all",
]

# Module-level singletons (lazy init)
_config: Optional["DevToolsConfig"] = None
_data_bus: Optional["DataBus"] = None
_battery_provider: Optional["BatteryProvider"] = None
_dashboard: Optional["DevDashboard"] = None
_initialized: bool = False

logger = logging.getLogger("devtools")


def _load_config() -> "DevToolsConfig":
    """Load dev tools configuration from settings.json."""
    global _config
    if _config is None:
        from devtools.config import load_devtools_config
        _config = load_devtools_config()
    return _config


def is_enabled() -> bool:
    """
    Check if dev tools are enabled.
    
    Returns False if:
    - dev_tools.enabled is False or missing in settings.json
    - Any import error occurs (graceful degradation)
    """
    try:
        config = _load_config()
        return config.enabled
    except Exception as e:
        logger.debug(f"Dev tools disabled due to: {e}")
        return False


def get_config() -> "DevToolsConfig":
    """
    Get dev tools configuration.
    
    Raises:
        RuntimeError: If dev tools are disabled
    """
    if not is_enabled():
        raise RuntimeError("Dev tools are disabled. Enable in settings.json")
    return _load_config()


def get_data_bus() -> "DataBus":
    """
    Get the shared data bus singleton.
    
    The data bus is the SINGLE SOURCE OF TRUTH for all dev tool consumers.
    It is updated by production components and read by the GUI.
    
    Raises:
        RuntimeError: If dev tools are disabled
    """
    global _data_bus
    if not is_enabled():
        raise RuntimeError("Dev tools are disabled")
    
    if _data_bus is None:
        from devtools.data_bus import DataBus
        _data_bus = DataBus()
        logger.info("DataBus initialized")
    
    return _data_bus


def get_battery_provider() -> "BatteryProvider":
    """
    Get the battery provider based on configuration.
    
    Returns:
        SimulatedBatteryProvider if battery_simulation.enabled
        RealBatteryProvider otherwise (pass-through to MAVLink)
    
    Raises:
        RuntimeError: If dev tools are disabled
    """
    global _battery_provider
    if not is_enabled():
        raise RuntimeError("Dev tools are disabled")
    
    if _battery_provider is None:
        from devtools.battery_sim import create_battery_provider
        config = _load_config()
        _battery_provider = create_battery_provider(config)
        logger.info(f"BatteryProvider initialized: {type(_battery_provider).__name__}")
    
    return _battery_provider


def start_dashboard() -> Optional["DevDashboard"]:
    """
    Start the Tkinter dashboard if enabled.
    
    The dashboard runs in a separate thread and is non-blocking.
    
    Returns:
        DevDashboard instance if started, None if GUI disabled
    
    Raises:
        RuntimeError: If dev tools are disabled
    """
    global _dashboard
    if not is_enabled():
        raise RuntimeError("Dev tools are disabled")
    
    config = _load_config()
    if not config.gui.enabled:
        logger.info("GUI disabled in configuration")
        return None
    
    if _dashboard is None:
        from devtools.dashboard import DevDashboard
        data_bus = get_data_bus()
        battery_provider = get_battery_provider() if config.battery_simulation.enabled else None
        _dashboard = DevDashboard(data_bus, battery_provider, config.gui)
        _dashboard.start()
        logger.info("Dashboard started")
    
    return _dashboard


def stop_all() -> None:
    """
    Stop all dev tools components gracefully.
    
    Safe to call even if dev tools are disabled.
    """
    global _dashboard, _data_bus, _battery_provider, _initialized
    
    logger.info("Stopping dev tools...")
    
    if _dashboard is not None:
        try:
            _dashboard.stop()
        except Exception as e:
            logger.warning(f"Dashboard stop error: {e}")
        _dashboard = None
    
    if _data_bus is not None:
        try:
            _data_bus.stop()
        except Exception as e:
            logger.warning(f"DataBus stop error: {e}")
        _data_bus = None
    
    _battery_provider = None
    _initialized = False
    logger.info("Dev tools stopped")


def initialize() -> bool:
    """
    Initialize all enabled dev tools components.
    
    Returns:
        True if dev tools are enabled and initialized
        False if disabled or initialization failed
    """
    global _initialized
    
    if not is_enabled():
        logger.info("Dev tools are disabled in configuration")
        return False
    
    if _initialized:
        return True
    
    try:
        config = _load_config()
        logger.info(f"Initializing dev tools v{__version__}")
        
        # Always initialize data bus when enabled
        get_data_bus()
        
        # Initialize battery provider if simulation enabled
        if config.battery_simulation.enabled:
            get_battery_provider()
        
        # Start dashboard if enabled
        if config.gui.enabled:
            start_dashboard()
        
        _initialized = True
        logger.info("Dev tools initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Dev tools initialization failed: {e}")
        return False
