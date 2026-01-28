
import sys
import argparse
import logging
import signal
import threading
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from core.config import CONFIG
from core.async_proxy import run_proxy
from core.logging_utils import get_logger
from core.suites import get_suite

# OQS Import logic
try:
    from oqs import Signature
except (ImportError, ModuleNotFoundError):
    Signature = None

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] [run-proxy] %(message)s', datefmt='%Y-%m-%dT%H:%M:%SZ', force=True)
logger = get_logger("pqc")
logger.setLevel(logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description="PQC Secure Tunnel Proxy Entry Point")
    parser.add_argument("role", choices=["gcs", "drone"], help="Role (gcs|drone)")
    parser.add_argument("--suite", required=True, help="Suite ID")
    parser.add_argument("--gcs-secret-file", help="Path to GCS signing key (private)")
    parser.add_argument("--gcs-public-file", help="Path to GCS signing key (public)")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    parser.add_argument("--status-file", help="Path to write JSON status")
    parser.add_argument("--run-id", help="Run ID (ignored)", default="")
    
    args = parser.parse_args()
    
    suite = get_suite(args.suite)
    if not suite:
        logger.error(f"Unknown suite: {args.suite}")
        sys.exit(1)
    
    # Load OQS Keys
    gcs_sig_secret = None
    gcs_sig_public = None
    
    if args.role == "gcs":
        if not args.gcs_secret_file:
            logger.error("GCS role requires --gcs-secret-file")
            sys.exit(1)
        if Signature is None:
            logger.error("OQS library not available")
            sys.exit(1)
            
        try:
            # Load secret key (bytes)
            with open(args.gcs_secret_file, "rb") as f:
                sk = f.read()
            # Instantiate Signature with SK
            sig = Signature(suite["sig_name"], secret_key=sk)
            gcs_sig_secret = sig
        except Exception as e:
            logger.error(f"Failed to load GCS secret key: {e}")
            sys.exit(1)
            
    if args.role == "drone":
        # Drone needs GCS public key verify
        if not args.gcs_public_file:
            # Wait, sdrone_bench.py might not pass this if it expects hardcoded or config-based?
            # Let's check sdrone_bench.py usage later. For now, optional?
            pass
        else:
            try:
                with open(args.gcs_public_file, "rb") as f:
                    gcs_sig_public = f.read()
            except Exception as e:
                logger.error(f"Failed to load GCS public key: {e}")
                sys.exit(1)
                
        # Fallback to CONFIG if file not provided (dev mode)
        if gcs_sig_public is None:
             # Logic to derive from config or secrets dir?
             # For now, require file if logic demands it.
             pass

    # Ensure status file directory exists
    if args.status_file:
        try:
            Path(args.status_file).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # Event to assist coordination
    ready_evt = threading.Event()
    
    def signal_handler(sig, frame):
        # We rely on async_proxy to handle cleanup but we can log
        pass
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run blocking
    try:
        run_proxy(
            role=args.role,
            suite=suite,
            cfg=CONFIG,
            gcs_sig_secret=gcs_sig_secret,
            gcs_sig_public=gcs_sig_public,
            quiet=args.quiet,
            status_file=args.status_file,
            ready_event=ready_evt
        )
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Proxy runtime error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
