# Repository Progress Log

Date: 2026-01-28

## Scope Completed
- Generated full per-file static analysis inventory for all Python files.
- Deep-read core crypto/proxy pipeline and primary schedulers/bench runners.
- Identified missing runtime components referenced in code.

## Key Artifacts
- Full Python file analysis: text-files/full_analysis.md
- Python inventory (imports/classes/functions): text-files/_python_inventory.md
- Raw file list: text-files/_all_files.txt
- Python file list: text-files/_python_files.txt

## Critical Findings (Code-Verified)
- `core.run_proxy` module is referenced by many scripts but is missing in the main tree; only present under snapshot/.
- Core control plane includes both in-band encrypted control packets and optional TCP JSON control server.
- AES-GCM/ChaCha20-Poly1305/Ascon AEAD supported; KEM/SIG from liboqs with HKDF-based key derivation.
- Replay window + deterministic nonce scheme implemented in `core/aead.py`.

## Open Questions / Blocks
- Determine whether `snapshot/` is authoritative or archival; multiple duplicate Python modules exist there.
- Decide whether `core.run_proxy` should be restored or scripts should invoke `core.async_proxy` directly.

## Next Actions
- If needed, reconcile snapshot copies against active modules.
- Decide whether to retain both sscheduler/ and scheduler/ stacks.
