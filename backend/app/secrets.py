"""Encryption for broker credentials, and hashing for account keys.

Storing a Fyers access token is what lets a scheduled job value a portfolio at
2am. It is also the one place in this codebase that holds a credential capable
of reading someone's real brokerage account, so the rules here are strict:

* **No key, no storage.** If `TOKEN_ENCRYPTION_KEY` is unset, `encrypt` raises.
  It does not fall back to base64, or to plaintext with a warning — a fallback
  that "works" is how a plaintext token ends up in a database dump.
* **Account keys are hashed, never stored.** The browser holds the key; the
  database holds SHA-256 of it. A leaked table therefore yields no working
  credentials.

The key is a Fernet key (`Fernet.generate_key()`, base64, 32 bytes of entropy),
which gives AES-128-CBC with an HMAC-SHA256 authentication tag and a
timestamp — authenticated encryption, so a tampered ciphertext fails loudly
rather than decrypting to garbage.

Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import hashlib
import logging
import os
import secrets as stdlib_secrets
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

ENV_KEY = "TOKEN_ENCRYPTION_KEY"


class EncryptionUnavailable(RuntimeError):
    """Raised when a secret must be stored but cannot be encrypted."""


@lru_cache(maxsize=1)
def _fernet():
    key = (os.getenv(ENV_KEY) or "").strip()
    if not key:
        raise EncryptionUnavailable(
            f"{ENV_KEY} is not set, so broker tokens cannot be stored. "
            "Generate one with: python -c \"from cryptography.fernet import "
            "Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise EncryptionUnavailable(
            "The 'cryptography' package is required to store broker tokens."
        ) from exc

    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise EncryptionUnavailable(f"{ENV_KEY} is not a valid Fernet key: {exc}") from exc


def encryption_available() -> bool:
    """Whether token storage is possible in this environment."""
    try:
        _fernet()
        return True
    except EncryptionUnavailable:
        return False


def encrypt(plaintext: str) -> str:
    """Encrypt a secret for storage. Raises rather than degrading."""
    if not plaintext:
        raise ValueError("Refusing to encrypt an empty secret.")
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored secret.

    An `InvalidToken` here means the ciphertext was written under a different
    key (rotated, or a different environment) — it is not recoverable, and the
    caller should re-authenticate rather than retry.
    """
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionUnavailable(
            "Stored credential could not be decrypted with the current "
            f"{ENV_KEY}. Re-authenticate to store a fresh token."
        ) from exc


# ---- account keys --------------------------------------------------------


def new_access_key() -> str:
    """A fresh opaque account key for the browser to keep. 256 bits, URL-safe."""
    return stdlib_secrets.token_urlsafe(32)


def hash_access_key(key: str) -> str:
    """SHA-256 hex of an account key.

    Plain SHA-256 rather than a password hash on purpose: this is a 256-bit
    random token, not a human-chosen password, so there is no dictionary to
    slow an attacker down against and bcrypt's cost would only tax the lookup
    on every request.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    """Compare two secrets without leaking their common prefix through timing."""
    return stdlib_secrets.compare_digest(left, right)


def admin_token() -> Optional[str]:
    """Shared secret guarding the job-trigger endpoints, if configured."""
    return (os.getenv("ADMIN_TOKEN") or "").strip() or None
