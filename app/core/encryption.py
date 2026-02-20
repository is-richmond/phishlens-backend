"""
AES-256 Field-Level Encryption

Provides symmetric encryption/decryption for sensitive data at rest
(e.g. third-party API keys stored in the database).

Uses Fernet (AES-128-CBC under the hood via the ``cryptography`` library).
The key is read from ``settings.api_key_encryption_key``.  If the key is
not configured, helpers degrade gracefully (plaintext pass-through) so the
application can still run in development without the key set.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Derive a valid 32-byte Fernet key from the raw config value.
# Fernet expects a URL-safe base64-encoded 32-byte key.  We hash whatever
# string the user supplies to guarantee the correct length.
# ---------------------------------------------------------------------------

_fernet: Optional[Fernet] = None


def _get_fernet() -> Optional[Fernet]:
    """Lazily initialise and cache the Fernet instance."""
    global _fernet
    if _fernet is not None:
        return _fernet

    raw_key = settings.api_key_encryption_key
    if not raw_key:
        logger.warning(
            "API_KEY_ENCRYPTION_KEY not configured – field-level encryption disabled"
        )
        return None

    # Derive a deterministic 32-byte key via SHA-256
    derived = hashlib.sha256(raw_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    _fernet = Fernet(fernet_key)
    return _fernet


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def encrypt_value(plaintext: str) -> str:
    """Encrypt *plaintext* and return a URL-safe base64 token.

    If encryption is not configured the plaintext is returned unchanged.
    """
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a previously encrypted *token* back to plaintext.

    If decryption fails (wrong key, corrupted data) the original token is
    returned so the application does not crash.  A warning is logged.
    """
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except (InvalidToken, Exception) as exc:
        logger.warning("Failed to decrypt value: %s", exc)
        return token
