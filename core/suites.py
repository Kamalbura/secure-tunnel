"""PQC cryptographic suite registry and algorithm ID mapping.

Provides a composable {KEM × AEAD × SIG} registry with synonym resolution and
helpers for querying oqs availability.

NIST Security Level Reference (per liboqs / FIPS 203/204/205):
- L1: ~AES-128 equivalent security
- L3: ~AES-192 equivalent security  
- L5: ~AES-256 equivalent security

Note: ML-DSA-44 is claimed as L2 by liboqs (FIPS 204), but we map it to L1
for practical pairing with L1 KEMs (ML-KEM-512, etc.).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Dict, Iterable, Tuple
from core.logging_utils import get_logger
from core.config import CONFIG
import os

_logger = get_logger("pqc")


# Default bootstrap suite used when callers do not specify a suite.
# Keep suite IDs centralized in this module.
DEFAULT_SUITE_ID = "cs-mlkem768-aesgcm-mldsa65"


def _normalize_alias(value: str) -> str:
    """Normalize alias strings for case- and punctuation-insensitive matching."""

    return "".join(ch for ch in value.lower() if ch.isalnum())


# =============================================================================
# KEM Registry - NIST Levels per liboqs/FIPS203
# ML-KEM-512: L1, ML-KEM-768: L3, ML-KEM-1024: L5
# Classic-McEliece-348864: L1, -460896: L3, -8192128: L5
# HQC-128: L1, HQC-192: L3, HQC-256: L5
# =============================================================================
_KEM_REGISTRY = {
    "mlkem512": {
        "oqs_name": "ML-KEM-512",
        "token": "mlkem512",
        "nist_level": "L1",
        "kem_id": 1,
        "kem_param_id": 1,
        "aliases": (
            "ML-KEM-512",
            "ml-kem-512",
            "mlkem512",
            "kyber512",
            "kyber-512",
            "kyber_512",
            "Kyber512",
        ),
    },
    "mlkem768": {
        "oqs_name": "ML-KEM-768",
        "token": "mlkem768",
        "nist_level": "L3",
        "kem_id": 1,
        "kem_param_id": 2,
        "aliases": (
            "ML-KEM-768",
            "ml-kem-768",
            "mlkem768",
            "kyber768",
            "kyber-768",
            "kyber_768",
            "Kyber768",
        ),
    },
    "mlkem1024": {
        "oqs_name": "ML-KEM-1024",
        "token": "mlkem1024",
        "nist_level": "L5",
        "kem_id": 1,
        "kem_param_id": 3,
        "aliases": (
            "ML-KEM-1024",
            "ml-kem-1024",
            "mlkem1024",
            "kyber1024",
            "kyber-1024",
            "kyber_1024",
            "Kyber1024",
        ),
    },
    "classicmceliece348864": {
        "oqs_name": "Classic-McEliece-348864",
        "token": "classicmceliece348864",
        "nist_level": "L1",
        "kem_id": 3,
        "kem_param_id": 1,
        "aliases": (
            "Classic-McEliece-348864",
            "classicmceliece-348864",
            "classicmceliece348864",
            "mceliece348864",
        ),
    },
    "classicmceliece460896": {
        "oqs_name": "Classic-McEliece-460896",
        "token": "classicmceliece460896",
        "nist_level": "L3",
        "kem_id": 3,
        "kem_param_id": 2,
        "aliases": (
            "Classic-McEliece-460896",
            "classicmceliece-460896",
            "classicmceliece460896",
            "mceliece460896",
        ),
    },
    "classicmceliece8192128": {
        "oqs_name": "Classic-McEliece-8192128",
        "token": "classicmceliece8192128",
        "nist_level": "L5",
        "kem_id": 3,
        "kem_param_id": 3,
        "aliases": (
            "Classic-McEliece-8192128",
            "classicmceliece-8192128",
            "classicmceliece8192128",
            "mceliece8192128",
        ),
    },
    "hqc128": {
        "oqs_name": "HQC-128",
        "token": "hqc128",
        "nist_level": "L1",
        "kem_id": 5,
        "kem_param_id": 1,
        "aliases": (
            "HQC-128",
            "hqc-128",
            "hqc128",
        ),
    },
    "hqc192": {
        "oqs_name": "HQC-192",
        "token": "hqc192",
        "nist_level": "L3",
        "kem_id": 5,
        "kem_param_id": 2,
        "aliases": (
            "HQC-192",
            "hqc-192",
            "hqc192",
        ),
    },
    "hqc256": {
        "oqs_name": "HQC-256",
        "token": "hqc256",
        "nist_level": "L5",
        "kem_id": 5,
        "kem_param_id": 3,
        "aliases": (
            "HQC-256",
            "hqc-256",
            "hqc256",
        ),
    },
}


# =============================================================================
# Signature Registry - NIST Levels per liboqs/FIPS204/FIPS205
# ML-DSA-44: L2 (liboqs), but we use L1 for practical pairing with ML-KEM-512
# ML-DSA-65: L3, ML-DSA-87: L5
# Falcon-512: L1, Falcon-1024: L5 (no L3 variant exists in NIST standards)
# SPHINCS+-128s: L1, SPHINCS+-192s: L3, SPHINCS+-256s: L5
# =============================================================================
_SIG_REGISTRY = {
    "mldsa44": {
        "oqs_name": "ML-DSA-44",
        "token": "mldsa44",
        "nist_level": "L1",  # Practical: pairs with L1 KEMs; liboqs claims L2
        "sig_id": 1,
        "sig_param_id": 1,
        "aliases": (
            "ML-DSA-44",
            "ml-dsa-44",
            "mldsa44",
            "dilithium2",
            "dilithium-2",
            "Dilithium2",
        ),
    },
    "mldsa65": {
        "oqs_name": "ML-DSA-65",
        "token": "mldsa65",
        "nist_level": "L3",
        "sig_id": 1,
        "sig_param_id": 2,
        "aliases": (
            "ML-DSA-65",
            "ml-dsa-65",
            "mldsa65",
            "dilithium3",
            "dilithium-3",
            "Dilithium3",
        ),
    },
    "mldsa87": {
        "oqs_name": "ML-DSA-87",
        "token": "mldsa87",
        "nist_level": "L5",
        "sig_id": 1,
        "sig_param_id": 3,
        "aliases": (
            "ML-DSA-87",
            "ml-dsa-87",
            "mldsa87",
            "dilithium5",
            "dilithium-5",
            "Dilithium5",
        ),
    },
    # Falcon signatures - NTRU-lattice based, compact signatures
    # Falcon-512: L1, Falcon-1024: L5 (no L3 variant per NIST)
    "falcon512": {
        "oqs_name": "Falcon-512",
        "token": "falcon512",
        "nist_level": "L1",
        "sig_id": 2,
        "sig_param_id": 1,
        "aliases": (
            "Falcon-512",
            "falcon-512",
            "falcon512",
            "Falcon512",
        ),
    },
    "falcon1024": {
        "oqs_name": "Falcon-1024",
        "token": "falcon1024",
        "nist_level": "L5",
        "sig_id": 2,
        "sig_param_id": 2,
        "aliases": (
            "Falcon-1024",
            "falcon-1024",
            "falcon1024",
            "Falcon1024",
        ),
    },
    # SPHINCS+ hash-based signatures (stateless)
    "sphincs128s": {
        "oqs_name": "SPHINCS+-SHA2-128s-simple",
        "token": "sphincs128s",
        "nist_level": "L1",
        "sig_id": 3,
        "sig_param_id": 1,
        "aliases": (
            "SLH-DSA-SHA2-128s",
            "SPHINCS+-SHA2-128s-simple",
            "sphincs+-sha2-128s-simple",
            "sphincs128s",
            "sphincs128s_sha2",
            # Fast variant aliases (f vs s - both map to our s variant)
            "sphincs128f",
            "sphincs128fsha2",
            "sphincs128f_sha2",
            "SPHINCS+128s",
        ),
    },
    "sphincs192s": {
        "oqs_name": "SPHINCS+-SHA2-192s-simple",
        "token": "sphincs192s",
        "nist_level": "L3",
        "sig_id": 3,
        "sig_param_id": 2,
        "aliases": (
            "SLH-DSA-SHA2-192s",
            "SPHINCS+-SHA2-192s-simple",
            "sphincs+-sha2-192s-simple",
            "sphincs192s",
            "sphincs192s_sha2",
            "sphincs192f",
            "sphincs192fsha2",
            "sphincs192f_sha2",
            "SPHINCS+192s",
        ),
    },
    "sphincs256s": {
        "oqs_name": "SPHINCS+-SHA2-256s-simple",
        "token": "sphincs256s",
        "nist_level": "L5",
        "sig_id": 3,
        "sig_param_id": 3,
        "aliases": (
            "SLH-DSA-SHA2-256s",
            "SPHINCS+-SHA2-256s-simple",
            "sphincs+-sha2-256s-simple",
            "sphincs256s",
            "sphincs256s_sha2",
            # Fast variant aliases
            "sphincs256f",
            "sphincs256fsha2",
            "sphincs256f_sha2",
            "SPHINCS+256s",
        ),
    },
}


_AEAD_REGISTRY = {
    "aesgcm": {
        "display_name": "AES-256-GCM",
        "token": "aesgcm",
        "kdf": "HKDF-SHA256",
        "aliases": (
            "AES-256-GCM",
            "aes-256-gcm",
            "aesgcm",
            "aes256gcm",
            "aes-gcm",
            "AESGCM",
        ),
    },
    "chacha20poly1305": {
        "display_name": "ChaCha20-Poly1305",
        "token": "chacha20poly1305",
        "kdf": "HKDF-SHA256",
        "aliases": (
            "ChaCha20-Poly1305",
            "chacha20poly1305",
            "chacha20-poly1305",
            "chacha20",
            "ChaCha20Poly1305",
        ),
    },
    "ascon128a": {
        "display_name": "Ascon-128a",
        "token": "ascon128a",
        "kdf": "HKDF-SHA256",
        "aliases": (
            "Ascon-128a",
            "ascon128a",
            "ascon-128a",
            "ascona",
            "Ascon128a",
        ),
    },
}


def _probe_aead_support() -> Tuple[Tuple[str, ...], Dict[str, str]]:
    """Detect AEAD algorithm support available in the current runtime.

    Note: the suite registry always includes Ascon-128a; this probe reports whether the
    current runtime can actually instantiate that AEAD.

    Ascon-128a may be provided either by the compiled `core._ascon_native` module or by
    the pure-Python `pyascon` fallback.
    Returns (available_tokens, missing_reason_map).
    """

    available: list[str] = ["aesgcm"]
    missing: Dict[str, str] = {}

    # ChaCha20-Poly1305 is optional
    try:  # pragma: no cover - build dependent
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # type: ignore
        if ChaCha20Poly1305 is None:  # type: ignore[truthy-bool]
            raise ImportError("ChaCha20Poly1305 unavailable in cryptography")
    except Exception as exc:  # pragma: no cover
        missing["chacha20poly1305"] = str(exc)
    else:
        available.append("chacha20poly1305")

    # Ascon-128a: may be disabled via config; native preferred; pure-python fallback acceptable.
    if not bool(CONFIG.get("ENABLE_ASCON", True)) or not bool(CONFIG.get("ENABLE_ASCON128A", True)):
        missing["ascon128a"] = "disabled_by_config"
        return tuple(available), missing

    ascon_available = False
    native_reason: str | None = None
    py_reason: str | None = None

    try:  # pragma: no cover - build/runtime dependent
        from core import _ascon_native as _ascon  # type: ignore
    except Exception as exc:  # pragma: no cover
        native_reason = f"core._ascon_native unavailable: {exc}"
    else:
        if not hasattr(_ascon, "encrypt") or not hasattr(_ascon, "decrypt"):
            native_reason = "core._ascon_native missing encrypt/decrypt exports"
        else:
            ascon_available = True

    if not ascon_available:
        try:  # pragma: no cover - optional dependency
            import pyascon as _pyascon  # type: ignore
        except Exception as exc:  # pragma: no cover
            py_reason = f"pyascon unavailable: {exc}"
        else:
            if hasattr(_pyascon, "ascon_encrypt") and hasattr(_pyascon, "ascon_decrypt"):
                ascon_available = True
            else:
                py_reason = "pyascon missing ascon_encrypt/ascon_decrypt"

    if ascon_available:
        available.append("ascon128a")
    else:
        missing["ascon128a"] = "; ".join(
            [reason for reason in (native_reason, py_reason) if reason]
        ) or "ascon backend unavailable"

    return tuple(available), missing


def available_aead_tokens() -> Tuple[str, ...]:
    """Return the AEAD tokens supported by this runtime."""

    supported, _ = _probe_aead_support()
    return supported


def unavailable_aead_reasons() -> Dict[str, str]:
    """Return descriptive reasons for AEAD algorithms that are unavailable."""

    _, missing = _probe_aead_support()
    return dict(missing)


def _build_alias_map(registry: Dict[str, Dict]) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for key, entry in registry.items():
        for alias in entry["aliases"]:
            normalized = _normalize_alias(alias)
            alias_map[normalized] = key
        alias_map[_normalize_alias(entry["oqs_name"]) if "oqs_name" in entry else _normalize_alias(entry["display_name"])] = key
        alias_map[_normalize_alias(entry["token"])] = key
    return alias_map


_KEM_ALIASES = _build_alias_map(_KEM_REGISTRY)
_SIG_ALIASES = _build_alias_map(_SIG_REGISTRY)
_AEAD_ALIASES = _build_alias_map(_AEAD_REGISTRY)


def _resolve_kem_key(name: str) -> str:
    lookup = _KEM_ALIASES.get(_normalize_alias(name))
    if lookup is None:
        raise ValueError(f"unknown KEM: {name}")
    return lookup


def _resolve_sig_key(name: str) -> str:
    lookup = _SIG_ALIASES.get(_normalize_alias(name))
    if lookup is None:
        raise ValueError(f"unknown signature: {name}")
    return lookup


def _resolve_aead_key(name: str) -> str:
    lookup = _AEAD_ALIASES.get(_normalize_alias(name))
    if lookup is None:
        raise ValueError(f"unknown AEAD: {name}")
    return lookup


def build_suite_id(kem: str, aead: str, sig: str) -> str:
    """Build canonical suite identifier from component aliases."""

    kem_key = _resolve_kem_key(kem)
    aead_key = _resolve_aead_key(aead)
    sig_key = _resolve_sig_key(sig)

    kem_entry = _KEM_REGISTRY[kem_key]
    aead_entry = _AEAD_REGISTRY[aead_key]
    sig_entry = _SIG_REGISTRY[sig_key]

    return f"cs-{kem_entry['token']}-{aead_entry['token']}-{sig_entry['token']}"


_SUITE_ALIASES = {
    # Kyber -> ML-KEM aliases with Dilithium -> ML-DSA
    "cs-kyber512-aesgcm-dilithium2": "cs-mlkem512-aesgcm-mldsa44",
    "cs-kyber768-aesgcm-dilithium3": "cs-mlkem768-aesgcm-mldsa65",
    "cs-kyber1024-aesgcm-dilithium5": "cs-mlkem1024-aesgcm-mldsa87",
    # Kyber + Falcon suites
    "cs-kyber512-aesgcm-falcon512": "cs-mlkem512-aesgcm-falcon512",
    "cs-kyber768-aesgcm-falcon512": "cs-mlkem768-aesgcm-falcon512",
    "cs-kyber1024-aesgcm-falcon1024": "cs-mlkem1024-aesgcm-falcon1024",
    # SPHINCS+ f/s variant aliases (fast -> small)
    "cs-kyber512-aesgcm-sphincs128f_sha2": "cs-mlkem512-aesgcm-sphincs128s",
    "cs-kyber512-aesgcm-sphincs128fsha2": "cs-mlkem512-aesgcm-sphincs128s",
    "cs-kyber1024-aesgcm-sphincs256f_sha2": "cs-mlkem1024-aesgcm-sphincs256s",
    "cs-kyber1024-aesgcm-sphincs256fsha2": "cs-mlkem1024-aesgcm-sphincs256s",
    # Classic-McEliece + SPHINCS+ f variant
    "cs-classicmceliece348864-aesgcm-sphincs128fsha2": "cs-classicmceliece348864-aesgcm-sphincs128s",
    "cs-classicmceliece348864-chacha20poly1305-sphincs128fsha2": "cs-classicmceliece348864-chacha20poly1305-sphincs128s",
    "cs-classicmceliece8192128-aesgcm-sphincs256fsha2": "cs-classicmceliece8192128-aesgcm-sphincs256s",
    "cs-classicmceliece8192128-chacha20poly1305-sphincs256fsha2": "cs-classicmceliece8192128-chacha20poly1305-sphincs256s",
    # HQC + SPHINCS+ f variant
    "cs-hqc128-aesgcm-sphincs128fsha2": "cs-hqc128-aesgcm-sphincs128s",
    "cs-hqc128-chacha20poly1305-sphincs128fsha2": "cs-hqc128-chacha20poly1305-sphincs128s",
    "cs-hqc256-aesgcm-sphincs256fsha2": "cs-hqc256-aesgcm-sphincs256s",
    "cs-hqc256-chacha20poly1305-sphincs256fsha2": "cs-hqc256-chacha20poly1305-sphincs256s",
}


def _compose_suite(kem_key: str, aead_key: str, sig_key: str) -> Dict[str, object]:
    kem_entry = _KEM_REGISTRY[kem_key]
    aead_entry = _AEAD_REGISTRY[aead_key]
    sig_entry = _SIG_REGISTRY[sig_key]

    if kem_entry["nist_level"] != sig_entry["nist_level"]:
        raise NotImplementedError(
            f"NIST level mismatch for {kem_entry['oqs_name']} / {sig_entry['oqs_name']}"
        )

    suite_id = f"cs-{kem_entry['token']}-{aead_entry['token']}-{sig_entry['token']}"

    return {
        "suite_id": suite_id,
        "kem_name": kem_entry["oqs_name"],
        "kem_id": kem_entry["kem_id"],
        "kem_param_id": kem_entry["kem_param_id"],
        "sig_name": sig_entry["oqs_name"],
        "sig_id": sig_entry["sig_id"],
        "sig_param_id": sig_entry["sig_param_id"],
        "nist_level": kem_entry["nist_level"],
        "aead": aead_entry["display_name"],
        "kdf": aead_entry["kdf"],
        "aead_token": aead_entry["token"],
    }

def _generate_level_consistent_matrix() -> Tuple[Tuple[str, str], ...]:
    """Generate matrix of (kem_key, sig_key) pairs sharing identical NIST level.

    This expands prior static matrix to all level-aligned combinations while
    preserving backward compatibility (legacy combos remain valid subset).
    """
    # Allow runtime ignore lists for KEMs/AEADs: keep registry entries,
    # but avoid generating suites that include ignored primitives.
    _DEFAULT_IGNORED_KEMS = ()

    # Environment overrides (comma-separated keys matching registry keys)
    ignored_kems_env = os.getenv("SUITES_IGNORE_KEMS", "").strip()
    ignored_aeads_env = os.getenv("SUITES_IGNORE_AEADS", "").strip()

    ignored_kems = set(_DEFAULT_IGNORED_KEMS)
    ignored_aeads = set()
    if ignored_kems_env:
        ignored_kems.update(k.strip() for k in ignored_kems_env.split(",") if k.strip())
    if ignored_aeads_env:
        ignored_aeads.update(a.strip() for a in ignored_aeads_env.split(",") if a.strip())

    pairs: list[Tuple[str, str]] = []
    for kem_key, kem_entry in _KEM_REGISTRY.items():
        if kem_key in ignored_kems:
            # skip composing suites with ignored KEMs
            continue
        kem_level = kem_entry.get("nist_level")
        for sig_key, sig_entry in _SIG_REGISTRY.items():
            if sig_entry.get("nist_level") == kem_level:
                pairs.append((kem_key, sig_key))
    # Deterministic order: sort by kem token then signature token
    pairs.sort(key=lambda t: (t[0], t[1]))
    return tuple(pairs)

_SUITE_MATRIX: Tuple[Tuple[str, str], ...] = _generate_level_consistent_matrix()

_AEAD_ORDER: Tuple[str, ...] = ("aesgcm", "chacha20poly1305", "ascon128a")

def valid_nist_levels() -> Tuple[str, ...]:
    """Return distinct NIST security levels present in the registry."""
    levels = {entry["nist_level"] for entry in _KEM_REGISTRY.values()} | {entry["nist_level"] for entry in _SIG_REGISTRY.values()}
    ordered = sorted(levels)
    return tuple(ordered)

def list_suites_for_level(level: str) -> Dict[str, Dict]:
    """List suites restricted to a single NIST level.

    Raises ValueError if level is not present. Returns mapping of suite_id->suite dict copy.
    """
    if level not in {e["nist_level"] for e in _KEM_REGISTRY.values()}:
        raise ValueError(f"unknown NIST level: {level}")
    result: Dict[str, Dict] = {}
    for sid, cfg in SUITES.items():
        if cfg.get("nist_level") == level:
            result[sid] = dict(cfg)
    return result

def filter_suites_by_levels(levels: Iterable[str]) -> Tuple[str, ...]:
    """Return tuple of suite_ids whose nist_level is in provided iterable.

    Invalid levels raise ValueError.
    """
    level_set = set(levels)
    known = {e["nist_level"] for e in _KEM_REGISTRY.values()}
    if not level_set.issubset(known):
        unknown = level_set - known
        raise ValueError(f"unknown NIST levels requested: {sorted(unknown)}")
    return tuple(sid for sid, cfg in SUITES.items() if cfg.get("nist_level") in level_set)


def _canonicalize_suite_id(suite_id: str) -> str:
    if not suite_id:
        raise ValueError("suite_id cannot be empty")

    candidate = suite_id.strip()
    if candidate in _SUITE_ALIASES:
        return _SUITE_ALIASES[candidate]

    if not candidate.startswith("cs-"):
        raise NotImplementedError(f"unknown suite_id: {suite_id}")

    parts = candidate[3:].split("-")
    if len(parts) < 3:
        raise NotImplementedError(f"unknown suite_id: {suite_id}")

    kem_part = parts[0]
    aead_part = parts[1]
    sig_part = "-".join(parts[2:])

    try:
        return build_suite_id(kem_part, aead_part, sig_part)
    except ValueError as exc:
        raise ValueError(f"unknown suite_id: {suite_id}") from exc


def _generate_suite_registry() -> MappingProxyType:
    suites: Dict[str, MappingProxyType] = {}
    for kem_key, sig_key in _SUITE_MATRIX:
        if kem_key not in _KEM_REGISTRY:
            raise ValueError(f"unknown KEM in suite matrix: {kem_key}")
        if sig_key not in _SIG_REGISTRY:
            raise ValueError(f"unknown signature in suite matrix: {sig_key}")
        # Skip suites that use ignored AEAD tokens
        # Resolve ignored AEADs from environment if provided (see _generate_level_consistent_matrix)
        ignored_aeads_env = os.getenv("SUITES_IGNORE_AEADS", "").strip()
        # Ignore list keeps optional AEADs out unless enabled.
        ignored_aeads: set[str] = set()
        if ignored_aeads_env:
            ignored_aeads.update(a.strip() for a in ignored_aeads_env.split(",") if a.strip())

        for aead_key in _AEAD_ORDER:
            if aead_key in ignored_aeads:
                continue
            suite_dict = _compose_suite(kem_key, aead_key, sig_key)
            suites[suite_dict["suite_id"]] = MappingProxyType(suite_dict)
    return MappingProxyType(suites)


SUITES = _generate_suite_registry()


def list_suites() -> Dict[str, Dict]:
    """Return all available suites as immutable mapping."""

    return {suite_id: dict(config) for suite_id, config in SUITES.items()}


def get_suite(suite_id: str) -> Dict:
    """Get suite configuration by ID, resolving legacy aliases and synonyms."""

    canonical_id = _canonicalize_suite_id(suite_id)

    if canonical_id not in SUITES:
        raise NotImplementedError(f"unknown suite_id: {suite_id}")

    suite = SUITES[canonical_id]

    required_fields = {"kem_name", "sig_name", "aead", "kdf", "nist_level"}
    missing_fields = required_fields - set(suite.keys())
    if missing_fields:
        raise ValueError(f"malformed suite {suite_id}: missing fields {missing_fields}")

    return dict(suite)


def _safe_get_enabled_kem_mechanisms() -> Iterable[str]:
    try:
        from oqs.oqs import get_enabled_KEM_mechanisms as kem_loader  # type: ignore[attr-defined]
    except ImportError:
        from oqs.oqs import get_enabled_kem_mechanisms as kem_loader  # type: ignore[attr-defined]
    except AttributeError:
        from oqs.oqs import get_enabled_kem_mechanisms as kem_loader  # type: ignore[attr-defined]

    return kem_loader()


def _safe_get_enabled_sig_mechanisms() -> Iterable[str]:
    try:
        from oqs.oqs import get_enabled_sig_mechanisms as sig_loader  # type: ignore[attr-defined]
    except ImportError:
        from oqs.oqs import get_enabled_sig_mechanisms as sig_loader  # type: ignore[attr-defined]
    except AttributeError:
        from oqs.oqs import get_enabled_sig_mechanisms as sig_loader  # type: ignore[attr-defined]

    return sig_loader()


def enabled_kems() -> Tuple[str, ...]:
    """Return tuple of oqs KEM mechanism names supported by the runtime."""

    mechanisms = {_normalize_alias(name) for name in _safe_get_enabled_kem_mechanisms()}
    result = [
        entry["oqs_name"]
        for entry in _KEM_REGISTRY.values()
        if _normalize_alias(entry["oqs_name"]) in mechanisms
    ]
    return tuple(result)


def enabled_sigs() -> Tuple[str, ...]:
    """Return tuple of oqs signature mechanism names supported by the runtime."""

    mechanisms = {_normalize_alias(name) for name in _safe_get_enabled_sig_mechanisms()}
    result = [
        entry["oqs_name"]
        for entry in _SIG_REGISTRY.values()
        if _normalize_alias(entry["oqs_name"]) in mechanisms
    ]
    return tuple(result)


def _prune_suites_for_runtime() -> None:
    """Filter suites by signature availability, preserving registry immutability."""

    global SUITES
    try:
        available = set(enabled_sigs())
    except Exception:
        return
    if not available:
        return

    filtered: Dict[str, MappingProxyType] = {}
    removed: list[str] = []
    for suite_id, config in SUITES.items():
        if config.get("sig_name") in available:
            filtered[suite_id] = config
        else:
            removed.append(suite_id)

    if not removed:
        return

    _logger.warning(
        "Pruning suites with unsupported signature algorithms",
        extra={"removed_suites": removed},
    )
    from types import MappingProxyType as _MP

    SUITES = _MP(filtered)  # type: ignore[assignment]


def header_ids_for_suite(suite: Dict) -> Tuple[int, int, int, int]:
    """Return embedded header ID bytes for provided suite dict copy."""

    try:
        return (
            suite["kem_id"],
            suite["kem_param_id"],
            suite["sig_id"],
            suite["sig_param_id"],
        )
    except KeyError as e:
        raise ValueError(f"suite missing embedded id field: {e}")


def header_ids_from_names(kem_name: str, sig_name: str) -> Tuple[int, int, int, int]:
    """Return header IDs from algorithm names.
    
    Used by async_proxy.py for runtime header ID resolution when
    kem_name and sig_name are returned from the handshake.
    """
    kem_key = _resolve_kem_key(kem_name)
    sig_key = _resolve_sig_key(sig_name)
    kem_entry = _KEM_REGISTRY[kem_key]
    sig_entry = _SIG_REGISTRY[sig_key]
    return (
        kem_entry["kem_id"],
        kem_entry["kem_param_id"],
        sig_entry["sig_id"],
        sig_entry["sig_param_id"],
    )


def suite_bytes_for_hkdf(suite: Dict) -> bytes:
    """Generate deterministic bytes from suite for HKDF info parameter."""

    if "suite_id" in suite:
        return suite["suite_id"].encode("utf-8")

    try:
        suite_id = build_suite_id(suite["kem_name"], suite["aead"], suite["sig_name"])
    except (KeyError, ValueError) as exc:
        raise ValueError("Suite configuration not found in registry") from exc

    return suite_id.encode("utf-8")


_prune_suites_for_runtime()