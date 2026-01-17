from oqs import Signature
import os

sig = Signature("ML-DSA-65")
pub = sig.generate_keypair()
sec = sig.export_secret_key()

os.makedirs("secrets/localtest", exist_ok=True)
with open("secrets/localtest/gcs_signing.key", "wb") as f:
    f.write(sec)
with open("secrets/localtest/gcs_signing.pub", "wb") as f:
    f.write(pub)
print("Keys generated")
