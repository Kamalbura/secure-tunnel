"""
Security utilities for the control plane.
"""
import hmac
import hashlib
import os
import json
import time
from core.config import CONFIG

def get_drone_psk() -> bytes:
    """Retrieve the Drone PSK from config."""
    psk_hex = CONFIG.get("DRONE_PSK", "")
    if not psk_hex:
        # Fallback for dev environments if allowed, otherwise raise
        if os.getenv("ENV", "dev") == "dev":
            return b"dev_insecure_psk_padding_32bytes"
        raise ValueError("DRONE_PSK not configured")
    try:
        return bytes.fromhex(psk_hex)
    except ValueError:
        # If not hex, use bytes directly if length is sufficient (legacy compat)
        if len(psk_hex) >= 32:
            return psk_hex.encode("utf-8")[:32]
        raise ValueError("DRONE_PSK must be 32 bytes hex")

def create_challenge() -> bytes:
    """Generate a random 32-byte challenge."""
    return os.urandom(32)

def compute_response(challenge: bytes, psk: bytes) -> str:
    """Compute HMAC-SHA256 response for a given challenge."""
    return hmac.new(psk, challenge, hashlib.sha256).hexdigest()

def verify_response(challenge: bytes, response: str, psk: bytes) -> bool:
    """Verify the response against the challenge."""
    expected = compute_response(challenge, psk)
    return hmac.compare_digest(response, expected)
