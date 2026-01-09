"""
Dev Tools Launcher

Entry point for running the scheduler with dev tools enabled.
This script demonstrates how to integrate dev tools without modifying
the core scheduler code.

Usage:
    python -m devtools.launcher [scheduler_args...]

The launcher:
1. Checks if dev tools are enabled in settings.json
2. Initializes dev tools components if enabled
3. Launches the scheduler with data bus integration
4. Provides clean shutdown handling
"""

import argparse
import atexit
import logging
import signal
import sys
import time
import threading
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger("devtools.launcher")


def log(msg: str):
    """Simple timestamped log."""
    print(f"[devtools.launcher] {msg}", flush=True)


def main():
    """Main launcher entry point."""
    parser = argparse.ArgumentParser(
        description="PQC Drone Scheduler with Dev Tools"
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Disable GUI even if enabled in config"
    )
    parser.add_argument(
        "--no-battery-sim",
        action="store_true",
        help="Disable battery simulation even if enabled in config"
    )
    parser.add_argument(
        "--data-bus-only",
        action="store_true",
        help="Enable data bus without GUI or battery simulation"
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run dev tools standalone (GUI only, no scheduler)"
    )
    
    # Pass remaining args to scheduler
    args, scheduler_args = parser.parse_known_args()
    
    log("=" * 60)
    log("PQC Drone Dev Tools Launcher")
    log("=" * 60)
    
    # Check dev tools availability
    try:
        import devtools
        from devtools.config import load_devtools_config, DevToolsConfig
        
        config = load_devtools_config()
        
        if not config.enabled:
            log("Dev tools DISABLED in settings.json")
            log("Set dev_tools.enabled = true to enable")
            if not args.standalone:
                log("Falling back to standard scheduler...")
                return run_standard_scheduler(scheduler_args)
            else:
                log("Standalone mode requires dev tools to be enabled")
                return 1
        
        log(f"Dev tools ENABLED")
        log(f"  Battery simulation: {config.battery_simulation.enabled}")
        log(f"  GUI dashboard: {config.gui.enabled}")
        
    except ImportError as e:
        log(f"Dev tools import error: {e}")
        log("Falling back to standard scheduler...")
        return run_standard_scheduler(scheduler_args)
    
    # Apply command-line overrides
    if args.no_gui:
        config.gui.enabled = False
        log("  GUI disabled by --no-gui")
    
    if args.no_battery_sim:
        config.battery_simulation.enabled = False
        log("  Battery simulation disabled by --no-battery-sim")
    
    if args.data_bus_only:
        config.gui.enabled = False
        config.battery_simulation.enabled = False
        log("  Data bus only mode")
    
    # Initialize dev tools
    log("\nInitializing dev tools...")
    
    data_bus = None
    battery_provider = None
    dashboard = None
    
    try:
        # Initialize data bus (always)
        from devtools.data_bus import DataBus
        data_bus = DataBus(
            history_size=config.bus_history_size,
            log_path=config.bus_log_path
        )
        log("  DataBus initialized")
        
        # Initialize battery provider if enabled
        if config.battery_simulation.enabled:
            from devtools.battery_sim import SimulatedBatteryProvider
            battery_provider = SimulatedBatteryProvider(
                config=config.battery_simulation,
                data_bus=data_bus
            )
            battery_provider.start()
            log(f"  Battery simulation started (mode={config.battery_simulation.default_mode})")
        
        # Initialize dashboard if enabled
        if config.gui.enabled:
            from devtools.dashboard import DevDashboard
            dashboard = DevDashboard(
                data_bus=data_bus,
                battery_provider=battery_provider,
                config=config.gui
            )
            dashboard.start()
            log(f"  Dashboard started (refresh={config.gui.refresh_hz} Hz)")
        
    except Exception as e:
        log(f"Dev tools initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Register cleanup
    def cleanup():
        log("\nCleaning up dev tools...")
        if dashboard:
            try:
                dashboard.stop()
            except Exception:
                pass
        if battery_provider:
            try:
                battery_provider.stop()
            except Exception:
                pass
        if data_bus:
            try:
                data_bus.stop()
            except Exception:
                pass
        log("Cleanup complete")
    
    atexit.register(cleanup)
    
    # Handle SIGINT gracefully
    def sigint_handler(sig, frame):
        log("\nInterrupted")
        cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, sigint_handler)
    
    # Standalone mode: just run GUI
    if args.standalone:
        log("\n" + "=" * 60)
        log("STANDALONE MODE - GUI only")
        log("Press Ctrl+C to exit")
        log("=" * 60)
        
        # Demo loop: generate some fake data
        demo_thread = threading.Thread(target=lambda: run_demo_data(data_bus, battery_provider), daemon=True)
        demo_thread.start()
        
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        
        return 0
    
    # Normal mode: run scheduler with dev tools integration
    log("\n" + "=" * 60)
    log("SCHEDULER MODE - Full integration")
    log("=" * 60)
    
    return run_scheduler_with_devtools(scheduler_args, data_bus, battery_provider)


def run_standard_scheduler(args: list) -> int:
    """Run the standard scheduler without dev tools."""
    log("Running standard scheduler...")
    
    # Import and run the scheduler
    try:
        from sscheduler import sdrone
        sys.argv = ["sdrone.py"] + args
        return sdrone.main()
    except Exception as e:
        log(f"Scheduler error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_scheduler_with_devtools(args: list, data_bus, battery_provider) -> int:
    """Run the scheduler with dev tools integration."""
    log("Running scheduler with dev tools integration...")
    
    try:
        # Import scheduler components
        from sscheduler.sdrone import DroneScheduler, main as scheduler_main
        from devtools.battery_bridge import LocalMonitorBridge
        
        # The scheduler will use LocalMonitorBridge.create_with_devtools()
        # which automatically picks up the dev tools configuration
        
        # Run scheduler
        sys.argv = ["sdrone.py"] + args
        return scheduler_main()
        
    except Exception as e:
        log(f"Scheduler error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_demo_data(data_bus, battery_provider):
    """Generate demo data for standalone mode."""
    import random
    
    log("Starting demo data generation...")
    
    epoch = 0
    suite_names = [
        "cs-mlkem512-aesgcm-mldsa44",
        "cs-mlkem768-aesgcm-mldsa65",
        "cs-mlkem1024-aesgcm-mldsa87",
    ]
    current_suite = suite_names[0]
    
    while True:
        try:
            now = time.monotonic()
            
            # Update telemetry
            data_bus.update_telemetry(
                rx_pps=random.uniform(8.0, 12.0),
                gap_p95_ms=random.uniform(50, 150),
                blackout_count=random.randint(0, 2),
                jitter_ms=random.uniform(5, 20),
                telemetry_age_ms=random.uniform(50, 200),
                sample_count=random.randint(40, 60),
            )
            
            # Update policy
            action = "HOLD"
            if random.random() < 0.02:  # Occasional action
                action = random.choice(["DOWNGRADE", "UPGRADE", "REKEY"])
                if action in ("DOWNGRADE", "UPGRADE"):
                    idx = suite_names.index(current_suite)
                    if action == "UPGRADE" and idx < len(suite_names) - 1:
                        current_suite = suite_names[idx + 1]
                    elif action == "DOWNGRADE" and idx > 0:
                        current_suite = suite_names[idx - 1]
                epoch += 1
            
            data_bus.update_policy(
                current_suite=current_suite,
                current_action=action,
                target_suite=current_suite if action != "HOLD" else None,
                reasons=["demo_mode"],
                confidence=random.uniform(0.7, 1.0),
                cooldown_remaining_ms=random.uniform(0, 5000) if action != "HOLD" else 0,
                local_epoch=epoch,
                armed=random.random() < 0.1,
            )
            
            # Update proxy
            data_bus.update_proxy(
                encrypted_pps=random.uniform(80, 120),
                plaintext_pps=random.uniform(80, 120),
                replay_drops=random.randint(0, 5),
                handshake_status="ok",
                bytes_encrypted=int(random.uniform(1e6, 1e9)),
                bytes_decrypted=int(random.uniform(1e6, 1e9)),
            )
            
            time.sleep(0.2)  # 5 Hz
            
        except Exception as e:
            log(f"Demo data error: {e}")
            time.sleep(1.0)


if __name__ == "__main__":
    sys.exit(main())
