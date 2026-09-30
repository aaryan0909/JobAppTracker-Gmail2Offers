#!/usr/bin/env python3
"""crypto.py — AES-GCM payload encryption for the private phone deployment.

The dashboard payload is encrypted client-side-style: the public URL only
ever serves an encrypted blob, which decrypts in the browser with a password
(Web Crypto API). Plaintext never leaves the machine.

KDF: PBKDF2-SHA256, 200k iterations. Cipher: AES-256-GCM.
Requires the `cryptography` package (optional — local plaintext always works).
"""
import base64
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PASSFILE = os.path.join(HERE, ".passphrase")
ITERATIONS = 200_000


def get_passphrase(path=None):
    """Read the passphrase from file, creating a default on first run."""
    path = path or os.environ.get("CAREERBOARD_PASSPHRASE_FILE", PASSFILE)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    pw = "changeme-careerboard"
    with open(path, "w") as f:
        f.write(pw)
    os.chmod(path, 0o600)
    return pw


def encrypt_payload(payload, passphrase):
    """Encrypt a JSON-serializable payload. Returns a JSON-serializable blob."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt = os.urandom(16)
    iv = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=ITERATIONS)
    key = kdf.derive(passphrase.encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(payload).encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS,
            "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def decrypt_payload(blob, passphrase):
    """Inverse of encrypt_payload (used by tests / tooling)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    b64d = lambda s: base64.b64decode(s.encode())
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=b64d(blob["salt"]), iterations=blob["iter"])
    key = kdf.derive(passphrase.encode())
    pt = AESGCM(key).decrypt(b64d(blob["iv"]), b64d(blob["ct"]), None)
    return json.loads(pt.decode())
