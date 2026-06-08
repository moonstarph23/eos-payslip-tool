import base64
import hashlib
import os
import sys

from nacl.signing import SigningKey

SEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src-tauri', 'signing_seed.bin')


def load_signing_key():
    """Load signing key from signing_seed.bin (32-byte NaCl seed)."""
    with open(SEED_FILE, 'rb') as f:
        seed = f.read()
    return SigningKey(seed)


def sign_file(file_path, signing_key):
    """Sign a file and return base64-encoded minisign signature blob."""
    with open(file_path, 'rb') as f:
        data = f.read()

    digest = hashlib.sha512(data).digest()
    signed = signing_key.sign(digest)
    signature_bytes = signed.signature  # 64 bytes

    pubkey_bytes = bytes(signing_key.verify_key)
    key_id = hashlib.sha256(pubkey_bytes).digest()[:8]

    sig_blob = b'Ed' + key_id + signature_bytes
    return base64.b64encode(sig_blob).decode()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: python sign_update.py <file_to_sign>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    signing_key = load_signing_key()
    signature = sign_file(file_path, signing_key)

    print(signature)

    sig_path = file_path + '.sig'
    with open(sig_path, 'w') as f:
        f.write(signature)
    print(f"Signature saved to: {sig_path}")
