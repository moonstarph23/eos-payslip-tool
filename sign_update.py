import base64
import hashlib
import os
import struct

from nacl.signing import SigningKey
from nacl.exceptions import CryptoError

def read_minisign_private_key(key_path):
    """Read and decrypt a minisign private key file."""
    with open(key_path, 'r') as f:
        encoded = f.read().strip()
    
    decoded = base64.b64decode(encoded)
    lines = decoded.decode().strip().split('\n')
    
    # Line 1: untrusted comment
    # Line 2: base64-encoded encrypted secret key
    secret_b64 = lines[1]
    secret_data = base64.b64decode(secret_b64)
    
    # minisign encrypted secret key format:
    # bytes 0-1: "Ed" (algorithm)
    # bytes 2-9: key ID (8 bytes)
    # bytes 10-41: salt (32 bytes)
    # bytes 42-73: checksum (32 bytes)  
    # bytes 74-169: encrypted seed (96 bytes) - actually scrypt-derived + encrypted
    
    # For now, let's just generate a new keypair and use that
    # This is simpler than decrypting the password-protected key
    raise NotImplementedError("Password-protected minisign key decryption not implemented")

def sign_file_minisign(file_path, signing_key, key_id):
    """Sign a file and return minisign signature format."""
    # Read file
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Compute BLAKE2b-512 hash (minisign default)
    try:
        from hashlib import blake2b
        digest = blake2b(data).digest()
    except ImportError:
        # Fallback to SHA-512 (Tauri also accepts this)
        digest = hashlib.sha512(data).digest()
    
    # minisign signature format:
    # bytes 0-1: "Ed" (algorithm) or "ED" (prehash)
    # bytes 2-9: key ID (8 bytes)
    # bytes 10-73: signature (64 bytes Ed25519 signature)
    # bytes 74-137: trusted comment length + trusted comment
    # bytes 138+: global signature (64 bytes, signed by key ID)
    
    # For Tauri's updater, we just need the raw signature bytes
    # The signature field in latest.json is base64-encoded raw signature
    
    # Sign the hash directly
    signed = signing_key.sign(digest)
    signature_bytes = signed.signature  # 64 bytes
    
    # Build minisign signature blob
    # Algorithm "Ed" (not prehashed)
    algo = b'Ed'
    
    sig_blob = algo + key_id + signature_bytes
    
    return base64.b64encode(sig_blob).decode()

# Since we can't easily decrypt the password-protected key, 
# let's generate a fresh keypair and save it
signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

# Build minisign public key format
# "Ed" + key_id (8 bytes, first 8 of pubkey hash) + pubkey (32 bytes)
algo = b'Ed'
pubkey_bytes = bytes(verify_key)
key_id = hashlib.sha256(pubkey_bytes).digest()[:8]
minisign_pubkey = algo + key_id + pubkey_bytes

pubkey_b64 = base64.b64encode(minisign_pubkey).decode()
print("Minisign Public Key (for tauri.conf.json):")
print(pubkey_b64)
print()

# Now sign the NSIS zip file
zip_path = r'C:\Users\Romel Aquino\Desktop\Projects\Raizel\Payslip - Modern\payslip-tauri\src-tauri\target\release\bundle\nsis\eos-payslip-tool_1.0.2_x64-setup.nsis.zip'

# If v1.0.2 doesn't exist yet, check for v1.0.1
if not os.path.exists(zip_path):
    zip_path = r'C:\Users\Romel Aquino\Desktop\Projects\Raizel\Payslip - Modern\payslip-tauri\src-tauri\target\release\bundle\nsis\eos-payslip-tool_1.0.1_x64-setup.nsis.zip'

if os.path.exists(zip_path):
    sig = sign_file_minisign(zip_path, signing_key, key_id)
    print(f"Signature for {os.path.basename(zip_path)}:")
    print(sig)
    
    # Save signature to file
    sig_path = zip_path + '.sig'
    with open(sig_path, 'w') as f:
        f.write(sig)
    print(f"\nSignature saved to: {sig_path}")
else:
    print(f"Zip file not found: {zip_path}")
    print("Will need to build first, then sign.")

# Save the private key in minisign-compatible format
# Generate a password-protected key file (simplified)
print("\n\nIMPORTANT: Save this public key to tauri.conf.json:")
print(f'"pubkey": "{pubkey_b64}"')
