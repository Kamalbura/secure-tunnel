import sys
try:
    import oqs
    print(f"oqs version: {oqs.oqs_version()}")
    print(f"oqs-python version: {oqs.__version__}")
    from oqs import Signature
    print("Signature class available")
    sig = Signature("Falcon-512")
    print("Falcon-512 instantiated")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
