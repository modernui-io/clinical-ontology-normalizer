"""Field-level PHI encryption for HIPAA compliance.

Provides:
- encrypt_phi() / decrypt_phi(): Fernet-based symmetric encryption for PHI fields
- encrypt_phi_deterministic(): AES-SIV for searchable encrypted fields (e.g., patient_id)

The encryption key is loaded from settings.phi_encryption_key.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from app.core.config import settings

logger = logging.getLogger(__name__)


class PHIEncryptionError(Exception):
    """Raised when PHI encryption/decryption fails."""
    pass


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Get cached Fernet instance from settings key."""
    key = settings.phi_encryption_key
    if not key:
        raise PHIEncryptionError("PHI_ENCRYPTION_KEY is not configured")
    # Accept raw Fernet key (44-char base64) or derive from arbitrary passphrase
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # Derive a Fernet-compatible key from the passphrase
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(key.encode()).digest()
        )
        return Fernet(derived)


@lru_cache(maxsize=1)
def _get_siv_key() -> bytes:
    """Derive a 512-bit key for AES-SIV from the PHI encryption key."""
    key = settings.phi_encryption_key
    if not key:
        raise PHIEncryptionError("PHI_ENCRYPTION_KEY is not configured")
    # AES-SIV requires 256 or 512-bit key. Derive 512-bit from passphrase.
    h1 = hashlib.sha256((key + ":siv:1").encode()).digest()
    h2 = hashlib.sha256((key + ":siv:2").encode()).digest()
    return h1 + h2  # 64 bytes = 512 bits


def encrypt_phi(plaintext: str) -> str:
    """Encrypt a PHI field using Fernet (random IV, not searchable).

    Args:
        plaintext: The PHI value to encrypt.

    Returns:
        Base64-encoded ciphertext string.
    """
    if not plaintext:
        return plaintext
    try:
        fernet = _get_fernet()
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")
    except PHIEncryptionError:
        raise
    except Exception as e:
        raise PHIEncryptionError(f"Failed to encrypt PHI: {e}") from e


def decrypt_phi(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted PHI field.

    Args:
        ciphertext: Base64-encoded Fernet token.

    Returns:
        Decrypted plaintext string.
    """
    if not ciphertext:
        return ciphertext
    try:
        fernet = _get_fernet()
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise PHIEncryptionError("Invalid ciphertext or wrong key")
    except PHIEncryptionError:
        raise
    except Exception as e:
        raise PHIEncryptionError(f"Failed to decrypt PHI: {e}") from e


def encrypt_phi_deterministic(plaintext: str) -> str:
    """Encrypt PHI deterministically using AES-SIV for searchable fields.

    Same plaintext always produces the same ciphertext, enabling
    equality searches on encrypted columns (e.g., WHERE encrypted_patient_id = ?).

    Args:
        plaintext: The PHI value to encrypt.

    Returns:
        Base64-encoded deterministic ciphertext.
    """
    if not plaintext:
        return plaintext
    try:
        siv_key = _get_siv_key()
        aessiv = AESSIV(siv_key)
        ct = aessiv.encrypt(plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(ct).decode("utf-8")
    except PHIEncryptionError:
        raise
    except Exception as e:
        raise PHIEncryptionError(f"Failed to deterministic-encrypt PHI: {e}") from e


def decrypt_phi_deterministic(ciphertext: str) -> str:
    """Decrypt an AES-SIV encrypted PHI field.

    Args:
        ciphertext: Base64-encoded AES-SIV ciphertext.

    Returns:
        Decrypted plaintext string.
    """
    if not ciphertext:
        return ciphertext
    try:
        siv_key = _get_siv_key()
        aessiv = AESSIV(siv_key)
        ct = base64.urlsafe_b64decode(ciphertext.encode("utf-8"))
        return aessiv.decrypt(ct, None).decode("utf-8")
    except PHIEncryptionError:
        raise
    except Exception as e:
        raise PHIEncryptionError(f"Failed to decrypt deterministic PHI: {e}") from e


def is_encryption_configured() -> bool:
    """Check if PHI encryption is properly configured."""
    return bool(settings.phi_encryption_key)
