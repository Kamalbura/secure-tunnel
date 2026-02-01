#!/usr/bin/env python3
"""PQC Verification Script - Tests OQS library functionality."""

import sys

def main():
    try:
        from oqs.oqs import KeyEncapsulation, Signature
        import oqs.oqs as oqs
    except ImportError:
        print("ERROR: Cannot import oqs.oqs - liboqs-python not installed correctly")
        sys.exit(1)

    print("=" * 60)
    print("PQC VERIFICATION")
    print("=" * 60)

    print(f"OQS Version: {oqs.oqs_version()}")
    print(f"OQS Python Version: {oqs.oqs_python_version()}")

    kems = oqs.get_enabled_kem_mechanisms()
    print(f"Enabled KEM mechanisms: {len(kems)}")

    sigs = oqs.get_enabled_sig_mechanisms()
    print(f"Enabled Signature mechanisms: {len(sigs)}")

    # Test ML-KEM
    print("\n" + "=" * 60)
    print("TEST: ML-KEM-768 Key Encapsulation")
    print("=" * 60)
    kem = KeyEncapsulation("ML-KEM-768")
    pub = kem.generate_keypair()
    print(f"Public key size: {len(pub)} bytes")
    ct, ss_enc = kem.encap_secret(pub)
    print(f"Ciphertext size: {len(ct)} bytes")
    ss_dec = kem.decap_secret(ct)
    match1 = ss_enc == ss_dec
    print(f"Encap/Decap match: {match1}")

    # Test ML-DSA
    print("\n" + "=" * 60)
    print("TEST: ML-DSA-65 Signature")
    print("=" * 60)
    sig = Signature("ML-DSA-65")
    pub = sig.generate_keypair()
    print(f"Public key size: {len(pub)} bytes")
    msg = b"Test message for PQC"
    signature = sig.sign(msg)
    print(f"Signature size: {len(signature)} bytes")
    is_valid1 = sig.verify(msg, signature, pub)
    print(f"Signature valid: {is_valid1}")

    # Test Falcon
    print("\n" + "=" * 60)
    print("TEST: Falcon-512 Signature")
    print("=" * 60)
    sig_f = Signature("Falcon-512")
    pub_f = sig_f.generate_keypair()
    print(f"Public key size: {len(pub_f)} bytes")
    signature_f = sig_f.sign(msg)
    print(f"Signature size: {len(signature_f)} bytes")
    is_valid2 = sig_f.verify(msg, signature_f, pub_f)
    print(f"Signature valid: {is_valid2}")

    # Test Classic McEliece
    print("\n" + "=" * 60)
    print("TEST: Classic-McEliece-348864 Key Encapsulation")
    print("=" * 60)
    kem_cm = KeyEncapsulation("Classic-McEliece-348864")
    pub_cm = kem_cm.generate_keypair()
    print(f"Public key size: {len(pub_cm)} bytes")
    ct_cm, ss_enc_cm = kem_cm.encap_secret(pub_cm)
    print(f"Ciphertext size: {len(ct_cm)} bytes")
    ss_dec_cm = kem_cm.decap_secret(ct_cm)
    match2 = ss_enc_cm == ss_dec_cm
    print(f"Encap/Decap match: {match2}")

    # Summary
    print("\n" + "=" * 60)
    all_pass = match1 and is_valid1 and is_valid2 and match2
    if all_pass:
        print("PQC VERIFICATION: ALL TESTS PASSED")
    else:
        print("PQC VERIFICATION: SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
