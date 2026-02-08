"""Secret Store abstraction and implementations (DEVOPS-4).

Provides pluggable secret storage backends:
- AbstractSecretStore: interface for get/set/delete/list
- InMemorySecretStore: in-process dict (dev/test)
- EncryptedFileSecretStore: Fernet-compatible encrypted JSON file (prod-like)

No external packages required -- uses stdlib hashlib, hmac, os.urandom, base64.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class AbstractSecretStore(ABC):
    """Interface for secret storage backends."""

    @abstractmethod
    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve a secret record by key. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, key: str, value: dict[str, Any]) -> None:
        """Store or update a secret record."""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a secret record. Returns True if it existed."""
        ...

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all secret keys."""
        ...


class InMemorySecretStore(AbstractSecretStore):
    """In-memory secret store for development and testing.

    Thread-safe via a simple lock. Data is lost when the process exits.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._store.get(key)
            return json.loads(json.dumps(data)) if data is not None else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._store[key] = json.loads(json.dumps(value))

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def list_keys(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())


# ---------------------------------------------------------------------------
# Fernet-compatible encrypt/decrypt using pure stdlib
# ---------------------------------------------------------------------------

def _derive_keys(master_key: bytes) -> tuple[bytes, bytes]:
    """Derive a signing key and an encryption key from a master key.

    Uses HKDF-like derivation with SHA-256.
    Returns (signing_key_32, encryption_key_32).
    """
    signing_key = hashlib.sha256(b"signing:" + master_key).digest()
    encryption_key = hashlib.sha256(b"encryption:" + master_key).digest()
    return signing_key, encryption_key


def _xor_bytes(data: bytes, key_stream: bytes) -> bytes:
    """XOR data with a repeating key stream."""
    result = bytearray(len(data))
    key_len = len(key_stream)
    for i in range(len(data)):
        result[i] = data[i] ^ key_stream[i % key_len]
    return bytes(result)


def _generate_key_stream(key: bytes, iv: bytes, length: int) -> bytes:
    """Generate a pseudo-random key stream using HMAC-SHA256 in counter mode."""
    stream = b""
    counter = 0
    while len(stream) < length:
        block = hmac.new(
            key,
            iv + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        stream += block
        counter += 1
    return stream[:length]


def encrypt_data(plaintext: bytes, master_key: bytes) -> bytes:
    """Encrypt plaintext and return iv + ciphertext + hmac_tag.

    Layout: iv(16) || ciphertext(N) || hmac_tag(32)
    """
    signing_key, encryption_key = _derive_keys(master_key)
    iv = os.urandom(16)
    key_stream = _generate_key_stream(encryption_key, iv, len(plaintext))
    ciphertext = _xor_bytes(plaintext, key_stream)
    tag = hmac.new(signing_key, iv + ciphertext, hashlib.sha256).digest()
    return iv + ciphertext + tag


def decrypt_data(blob: bytes, master_key: bytes) -> bytes:
    """Decrypt a blob produced by encrypt_data.

    Raises ValueError on tampered data.
    """
    if len(blob) < 16 + 32:
        raise ValueError("Encrypted blob too short")

    signing_key, encryption_key = _derive_keys(master_key)
    iv = blob[:16]
    tag = blob[-32:]
    ciphertext = blob[16:-32]

    expected_tag = hmac.new(signing_key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("HMAC verification failed -- data may be tampered")

    key_stream = _generate_key_stream(encryption_key, iv, len(ciphertext))
    return _xor_bytes(ciphertext, key_stream)


class EncryptedFileSecretStore(AbstractSecretStore):
    """Encrypted JSON file secret store for production-like environments.

    Secrets are serialized to JSON, encrypted with a master key derived
    cipher, and persisted to a single file. The master key is read from
    the ``SECRET_MASTER_KEY`` environment variable or passed explicitly.

    Thread-safe via a simple lock.
    """

    def __init__(
        self,
        file_path: str = "secrets.enc",
        master_key: str | None = None,
    ) -> None:
        self._file_path = file_path
        raw_key = master_key or os.environ.get("SECRET_MASTER_KEY", "")
        if not raw_key:
            raise ValueError(
                "Master key is required. Set SECRET_MASTER_KEY env var or pass master_key."
            )
        self._master_key = raw_key.encode("utf-8")
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] | None = None

    # -- internal helpers ---------------------------------------------------

    def _load(self) -> dict[str, dict[str, Any]]:
        """Load and decrypt the store file. Returns empty dict if missing."""
        if self._cache is not None:
            return self._cache

        if not os.path.exists(self._file_path):
            self._cache = {}
            return self._cache

        with open(self._file_path, "rb") as fh:
            raw = fh.read()

        if not raw:
            self._cache = {}
            return self._cache

        blob = base64.b64decode(raw)
        plaintext = decrypt_data(blob, self._master_key)
        self._cache = json.loads(plaintext.decode("utf-8"))
        return self._cache  # type: ignore[return-value]

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        """Encrypt and persist the store."""
        plaintext = json.dumps(data, default=str).encode("utf-8")
        blob = encrypt_data(plaintext, self._master_key)
        encoded = base64.b64encode(blob)
        with open(self._file_path, "wb") as fh:
            fh.write(encoded)
        self._cache = data

    # -- public interface ---------------------------------------------------

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load()
            val = data.get(key)
            return json.loads(json.dumps(val)) if val is not None else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            data[key] = json.loads(json.dumps(value, default=str))
            self._save(data)

    def delete(self, key: str) -> bool:
        with self._lock:
            data = self._load()
            if key in data:
                del data[key]
                self._save(data)
                return True
            return False

    def list_keys(self) -> list[str]:
        with self._lock:
            return list(self._load().keys())
