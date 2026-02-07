"""
AEAD framing for PQC drone-GCS secure proxy.

Provides authenticated encryption (AES-256-GCM) with wire header bound as AAD,
deterministic 96-bit counter IVs, sliding replay window, and epoch support for rekeys.
"""

import struct
from dataclasses import dataclass
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
except ImportError:  # pragma: no cover - ChaCha unavailable on very old crypto builds
    ChaCha20Poly1305 = None
from cryptography.exceptions import InvalidTag

try:  # pragma: no cover - native extension optional
    from core import _ascon_native as _ascon_native_module
except Exception:  # pragma: no cover - extension not built or unavailable
    _ascon_native_module = None

try:  # pragma: no cover - pure python fallback
    import pyascon as _pyascon_module  # type: ignore
except Exception:  # pragma: no cover - not available
    _pyascon_module = None

from core.config import CONFIG
from core.exceptions import SequenceOverflow, AeadError


_SUPPORTED_AEAD_TOKENS = {"aesgcm", "chacha20poly1305", "ascon128a"}
_RETIRED_AEAD_TOKENS = {
    "aes128gcm": "use aesgcm (AES-256-GCM) for final deployments",
    "ascon128": "use ascon128a (native C backend) for MTU-scale support",
}


# Exception types
class HeaderMismatch(Exception):
    """Header validation failed (version, IDs, or session_id mismatch)."""
    pass


class AeadAuthError(Exception):
    """AEAD authentication failed during decryption."""
    pass


class ReplayError(Exception):
    """Packet replay detected or outside acceptable window."""
    pass


# Constants
HEADER_STRUCT = "!BBBBB8sQB"
# Compute header length from structure to avoid drift when struct changes.
HEADER_LEN = struct.calcsize(HEADER_STRUCT)
# IV is still logically 12 bytes (1 epoch + 11 seq bytes) but is NO LONGER transmitted on wire.
# Wire format: header(22) || ciphertext+tag
IV_LEN = 0  # length of IV bytes present on wire (0 after optimization)




def _canonicalize_aead_token(token: str) -> str:
    candidate = token.lower()
    if candidate in _RETIRED_AEAD_TOKENS:
        raise ValueError(f"AEAD token '{token}' is retired: {_RETIRED_AEAD_TOKENS[candidate]}")
    if candidate not in _SUPPORTED_AEAD_TOKENS:
        raise ValueError(f"unknown AEAD token: {token}")
    return candidate


class _AsconAdapter:
    """Ascon adapter backing the 'ascon128a' token with native C fallbacks."""

    def __init__(self, key: bytes, variant: str):
        if len(key) < 16:
            raise ValueError("Ascon requires at least 16 bytes of key material")
        strict = bool(CONFIG.get("ASCON_STRICT_KEY_SIZE", False))
        if strict and len(key) != 16:
            raise ValueError("ASCON_STRICT_KEY_SIZE enabled: key must be exactly 16 bytes")
        self._key = key[:16]
        algo_map = {
            "ascon128": "Ascon-AEAD128",  # legacy alias retained for internal callers
            "ascon128a": "Ascon-AEAD128a",
        }
        self._algo_str = algo_map.get(variant, "Ascon-AEAD128")
        self._fallback_variant = {
            "Ascon-AEAD128": "Ascon-128",
            "Ascon-AEAD128a": "Ascon-128a",
        }.get(self._algo_str, "Ascon-128")
        variant_name = self._algo_str

        if _ascon_native_module is not None and hasattr(_ascon_native_module, "encrypt") and hasattr(_ascon_native_module, "decrypt"):
            def _native_encrypt(
                key_bytes: bytes,
                nonce_bytes: bytes,
                aad_bytes: bytes,
                plaintext_bytes: bytes,
                algo: str = variant_name,
            ) -> bytes:
                return _ascon_native_module.encrypt(
                    key_bytes, nonce_bytes, aad_bytes, plaintext_bytes, algo
                )

            def _native_decrypt(
                key_bytes: bytes,
                nonce_bytes: bytes,
                aad_bytes: bytes,
                ciphertext_bytes: bytes,
                algo: str = variant_name,
            ) -> bytes:
                result = _ascon_native_module.decrypt(
                    key_bytes, nonce_bytes, aad_bytes, ciphertext_bytes, algo
                )
                if result is None:
                    raise InvalidTag("Ascon authentication failed")
                return result

            self._enc = _native_encrypt
            self._dec = _native_decrypt
        elif _pyascon_module is not None:
            # pyascon uses legacy variant names ("Ascon-128a"), not NIST names
            fallback_name = self._fallback_variant
            def _py_encrypt(
                key_bytes: bytes,
                nonce_bytes: bytes,
                aad_bytes: bytes,
                plaintext_bytes: bytes,
                algo: str = fallback_name,
            ) -> bytes:
                return _pyascon_module.ascon_encrypt(key_bytes, nonce_bytes, aad_bytes, plaintext_bytes, algo)

            def _py_decrypt(
                key_bytes: bytes,
                nonce_bytes: bytes,
                aad_bytes: bytes,
                ciphertext_bytes: bytes,
                algo: str = fallback_name,
            ) -> bytes:
                result = _pyascon_module.ascon_decrypt(key_bytes, nonce_bytes, aad_bytes, ciphertext_bytes, algo)
                if result is None:
                    raise InvalidTag("Ascon authentication failed")
                return result

            self._enc = _py_encrypt
            self._dec = _py_decrypt
        else:
            raise ImportError("No Ascon backend available (native module missing and pyascon not importable)")

    def encrypt(self, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
        if len(nonce) < 16:
            nonce = nonce + b"\x00" * (16 - len(nonce))
        # Do NOT pass algo explicitly — closures capture the correct variant
        # name at init time (NIST name for native, legacy name for pyascon).
        return self._enc(self._key, nonce[:16], aad, plaintext)

    def decrypt(self, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        if len(nonce) < 16:
            nonce = nonce + b"\x00" * (16 - len(nonce))
        pt = self._dec(self._key, nonce[:16], aad, ciphertext)
        if pt is None:
            raise InvalidTag("Ascon authentication failed")
        return pt


def _instantiate_aead(token: str, key: bytes) -> Tuple[object, int]:
    """Return AEAD primitive and required nonce length for the suite token."""

    normalized = _canonicalize_aead_token(token)

    if normalized == "aesgcm":
        if len(key) != 32:
            raise ValueError("AES-256-GCM requires 32-byte key material")
        return AESGCM(key), 12

    if normalized == "chacha20poly1305":
        if ChaCha20Poly1305 is None:
            raise ImportError("ChaCha20-Poly1305 not available in cryptography build")
        if len(key) != 32:
            raise ValueError("ChaCha20-Poly1305 requires 32-byte key material")
        return ChaCha20Poly1305(key), 12

    if normalized == "ascon128a":
        return _AsconAdapter(key, normalized), 16

    raise AeadError(f"unsupported AEAD token: {token}")


def _build_nonce(epoch: int, seq: int, nonce_len: int) -> bytes:
    base = bytes([epoch & 0xFF]) + seq.to_bytes(11, "big")
    if nonce_len == 12:
        return base
    if nonce_len > 12:
        return base + b"\x00" * (nonce_len - 12)
    raise ValueError("nonce length must be >= 12 bytes")


@dataclass(frozen=True)
class AeadIds:
    kem_id: int
    kem_param: int
    sig_id: int
    sig_param: int

    def __post_init__(self):
        for field_name, value in [("kem_id", self.kem_id), ("kem_param", self.kem_param), 
                                  ("sig_id", self.sig_id), ("sig_param", self.sig_param)]:
            if not isinstance(value, int) or not (0 <= value <= 255):
                raise ValueError(f"{field_name} must be int in range 0-255")


@dataclass
class Sender:
    version: int
    ids: AeadIds
    session_id: bytes
    epoch: int
    key_send: bytes
    aead_token: str = "aesgcm"
    _seq: int = 0

    def __post_init__(self):
        if not isinstance(self.version, int) or self.version != CONFIG["WIRE_VERSION"]:
            raise ValueError(f"version must equal CONFIG WIRE_VERSION ({CONFIG['WIRE_VERSION']})")
        
        if not isinstance(self.ids, AeadIds):
            raise TypeError("ids must be AeadIds instance")
        
        if not isinstance(self.session_id, bytes) or len(self.session_id) != 8:
            raise ValueError("session_id must be exactly 8 bytes")
        
        if not isinstance(self.epoch, int) or not (0 <= self.epoch <= 255):
            raise ValueError("epoch must be int in range 0-255")
        
        if not isinstance(self.key_send, bytes):
            raise TypeError("key_send must be bytes")
        
        if not isinstance(self._seq, int) or self._seq < 0:
            raise ValueError("_seq must be non-negative int")

        self._aead_token = _canonicalize_aead_token(self.aead_token)
        self._cipher, self._nonce_len = _instantiate_aead(self._aead_token, self.key_send)

    @property
    def seq(self):
        """Current sequence number."""
        return self._seq

    def pack_header(self, seq: int) -> bytes:
        """Pack header with given sequence number."""
        if not isinstance(seq, int) or seq < 0:
            raise ValueError("seq must be non-negative int")
        
        return struct.pack(
            HEADER_STRUCT,
            self.version,
            self.ids.kem_id,
            self.ids.kem_param, 
            self.ids.sig_id,
            self.ids.sig_param,
            self.session_id,
            seq,
            self.epoch
        )

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext returning: header || ciphertext + tag.

        Deterministic IV (epoch||seq) is derived locally and NOT sent on wire to
        reduce overhead (saves 12 bytes per packet). Receiver reconstructs it.
        """
        if not isinstance(plaintext, bytes):
            raise TypeError("plaintext must be bytes")
        
        # Proactive rekey threshold to avoid IV exhaustion.
        # Default threshold is 2^63 if not configured; this gives operators time to rekey.
        try:
            threshold = int(CONFIG.get("REKEY_SEQ_THRESHOLD", 1 << 63))
        except Exception:
            threshold = 1 << 63
        if self._seq >= threshold:
            raise SequenceOverflow("approaching IV exhaustion; trigger rekey")
        
        # Pack header with current sequence
        header = self.pack_header(self._seq)

        iv = _build_nonce(self.epoch, self._seq, self._nonce_len)

        try:
            ciphertext = self._cipher.encrypt(iv, plaintext, header)
        except Exception as e:
            raise AeadError(f"AEAD encryption failed: {e}")
        
        # Increment sequence on success
        self._seq += 1
        
        # Return optimized wire format: header || ciphertext+tag (IV omitted)
        return header + ciphertext

    def bump_epoch(self) -> None:
        """Increase epoch and reset sequence.

        Safety policy: forbid wrapping 255->0 with the same key to avoid IV reuse.
        Callers should perform a new handshake to rotate keys before wrap.
        """
        if self.epoch == 255:
            raise AeadError("epoch wrap forbidden without rekey; perform handshake to rotate keys")
        self.epoch += 1
        self._seq = 0


@dataclass
class Receiver:
    version: int
    ids: AeadIds
    session_id: bytes
    epoch: int
    key_recv: bytes
    window: int
    strict_mode: bool = False  # True = raise exceptions, False = return None
    aead_token: str = "aesgcm"
    _high: int = -1
    _mask: int = 0

    def __post_init__(self):
        if not isinstance(self.version, int) or self.version != CONFIG["WIRE_VERSION"]:
            raise ValueError(f"version must equal CONFIG WIRE_VERSION ({CONFIG['WIRE_VERSION']})")
        
        if not isinstance(self.ids, AeadIds):
            raise TypeError("ids must be AeadIds instance")
        
        if not isinstance(self.session_id, bytes) or len(self.session_id) != 8:
            raise ValueError("session_id must be exactly 8 bytes")
        
        if not isinstance(self.epoch, int) or not (0 <= self.epoch <= 255):
            raise ValueError("epoch must be int in range 0-255")
        
        if not isinstance(self.key_recv, bytes):
            raise TypeError("key_recv must be bytes")
        
        if not isinstance(self.window, int) or self.window < 64:
            raise ValueError(f"window must be int >= 64")
        
        if not isinstance(self._high, int):
            raise TypeError("_high must be int")
        
        if not isinstance(self._mask, int) or self._mask < 0:
            raise ValueError("_mask must be non-negative int")

        self._aead_token = _canonicalize_aead_token(self.aead_token)
        self._cipher, self._nonce_len = _instantiate_aead(self._aead_token, self.key_recv)
        self._last_error: Optional[str] = None

    def _check_replay(self, seq: int) -> None:
        """Check if sequence number should be accepted (anti-replay)."""
        if seq > self._high:
            # Future packet - shift window forward
            shift = seq - self._high
            if shift >= self.window:
                # Window completely shifts: reset mask to only include the newest packet
                # Mask bit 0 corresponds to the current highest sequence number
                self._mask = 1
            else:
                # Partial shift
                self._mask = (self._mask << shift) | 1
                # Mask to window size to prevent overflow
                self._mask &= (1 << self.window) - 1
            self._high = seq
        elif seq > self._high - self.window:
            # Within window - check if already seen
            offset = self._high - seq
            bit_pos = offset
            if self._mask & (1 << bit_pos):
                raise ReplayError(f"duplicate packet seq={seq}")
            # Mark as seen
            self._mask |= (1 << bit_pos)
        else:
            # Too old - outside window
            raise ReplayError(f"packet too old seq={seq}, high={self._high}, window={self.window}")

    def decrypt(self, wire: bytes) -> Optional[bytes]:
        """Validate header, perform anti-replay, reconstruct IV, decrypt.

        Returns plaintext bytes or None (silent mode) on failure.
        """
        if not isinstance(wire, bytes):
            raise ValueError("wire must be bytes")
        
        if len(wire) < HEADER_LEN:
            raise ValueError("wire too short for header")
        
        # Extract header
        header = wire[:HEADER_LEN]
        
        # Unpack and validate header
        try:
            fields = struct.unpack(HEADER_STRUCT, header)
            version, kem_id, kem_param, sig_id, sig_param, session_id, seq, epoch = fields
        except struct.error as e:
            raise ValueError(f"header unpack failed: {e}")
        
        # Validate header fields
        if version != self.version:
            self._last_error = "header"
            if self.strict_mode:
                raise HeaderMismatch(f"version mismatch: expected {self.version}, got {version}")
            return None
        
        if (kem_id, kem_param, sig_id, sig_param) != (self.ids.kem_id, self.ids.kem_param, self.ids.sig_id, self.ids.sig_param):
            self._last_error = "header"
            if self.strict_mode:
                raise HeaderMismatch(f"crypto ID mismatch")
            return None
        
        if session_id != self.session_id:
            self._last_error = "session"
            return None  # Wrong session - always fail silently for security
        
        if epoch != self.epoch:
            self._last_error = "session"
            return None  # Wrong epoch - always fail silently for rekeying
        
        # Check replay protection
        try:
            self._check_replay(seq)
        except ReplayError:
            self._last_error = "replay"
            if self.strict_mode:
                raise
            return None
        
        # Reconstruct deterministic IV instead of reading from wire
        iv = _build_nonce(epoch, seq, self._nonce_len)
        ciphertext = wire[HEADER_LEN:]
        
        # Decrypt with header as AAD
        try:
            plaintext = self._cipher.decrypt(iv, ciphertext, header)
        except InvalidTag:
            self._last_error = "auth"
            if self.strict_mode:
                raise AeadAuthError("AEAD authentication failed")
            return None
        except Exception as e:
            raise AeadError(f"AEAD decryption failed: {e}")
        self._last_error = None
        return plaintext

    def reset_replay(self) -> None:
        """Clear replay protection state."""
        self._high = -1
        self._mask = 0

    def bump_epoch(self) -> None:
        """Increase epoch and reset replay state.
        
        Safety policy: forbid wrapping 255->0 with the same key to avoid IV reuse.
        Callers should perform a new handshake to rotate keys before wrap.
        """
        if self.epoch == 255:
            raise AeadError("epoch wrap forbidden without rekey; perform handshake to rotate keys")
        self.epoch += 1
        self.reset_replay()

    def last_error_reason(self) -> Optional[str]:
        return getattr(self, "_last_error", None)