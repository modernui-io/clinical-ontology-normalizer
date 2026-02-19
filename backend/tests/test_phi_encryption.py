"""Tests for PHI encryption service.

Tests Fernet encryption/decryption round-trips, deterministic encryption
consistency, and error handling for the HIPAA-compliant PHI encryption module.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clear_encryption_caches():
    """Clear lru_cache between tests to avoid stale key state."""
    from app.core.phi_encryption import _get_fernet, _get_siv_key

    _get_fernet.cache_clear()
    _get_siv_key.cache_clear()
    yield
    _get_fernet.cache_clear()
    _get_siv_key.cache_clear()


class TestFernetEncryption:
    """Tests for Fernet-based PHI encryption."""

    @patch("app.core.phi_encryption.settings")
    def test_encrypt_decrypt_roundtrip(self, mock_settings) -> None:
        """Test that encrypt then decrypt returns original plaintext."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import decrypt_phi, encrypt_phi

        plaintext = "Patient John Doe, DOB 1990-01-15"
        ciphertext = encrypt_phi(plaintext)

        assert ciphertext != plaintext
        assert decrypt_phi(ciphertext) == plaintext

    @patch("app.core.phi_encryption.settings")
    def test_encrypt_produces_different_ciphertexts(self, mock_settings) -> None:
        """Test that Fernet produces different ciphertexts for same input (random IV)."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import encrypt_phi

        ct1 = encrypt_phi("same input")
        ct2 = encrypt_phi("same input")
        # Fernet uses random IV, so same plaintext produces different ciphertext
        assert ct1 != ct2

    @patch("app.core.phi_encryption.settings")
    def test_empty_string_passthrough(self, mock_settings) -> None:
        """Test that empty strings pass through unchanged."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import decrypt_phi, encrypt_phi

        assert encrypt_phi("") == ""
        assert decrypt_phi("") == ""

    @patch("app.core.phi_encryption.settings")
    def test_none_passthrough(self, mock_settings) -> None:
        """Test that None values pass through unchanged."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import decrypt_phi, encrypt_phi

        assert encrypt_phi(None) is None  # type: ignore[arg-type]
        assert decrypt_phi(None) is None  # type: ignore[arg-type]

    def test_encrypt_raises_without_key(self) -> None:
        """Test that encryption raises when key is not configured."""
        from app.core.phi_encryption import PHIEncryptionError, encrypt_phi

        with patch("app.core.phi_encryption.settings") as mock_settings:
            mock_settings.phi_encryption_key = None
            with pytest.raises(PHIEncryptionError, match="not configured"):
                encrypt_phi("test data")

    @patch("app.core.phi_encryption.settings")
    def test_decrypt_with_wrong_key_raises(self, mock_settings) -> None:
        """Test that decryption with wrong key raises error."""
        from app.core.phi_encryption import (
            PHIEncryptionError,
            _get_fernet,
            decrypt_phi,
            encrypt_phi,
        )

        # Encrypt with one key
        mock_settings.phi_encryption_key = "encryption-key-one"
        _get_fernet.cache_clear()
        ciphertext = encrypt_phi("secret data")

        # Try decrypt with different key
        mock_settings.phi_encryption_key = "different-key-two"
        _get_fernet.cache_clear()
        with pytest.raises(PHIEncryptionError):
            decrypt_phi(ciphertext)

    @patch("app.core.phi_encryption.settings")
    def test_encrypt_unicode_content(self, mock_settings) -> None:
        """Test encryption of Unicode content."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import decrypt_phi, encrypt_phi

        plaintext = "Diagnóstico: diabetes mellitus tipo 2 — café"
        assert decrypt_phi(encrypt_phi(plaintext)) == plaintext

    @patch("app.core.phi_encryption.settings")
    def test_encrypt_long_content(self, mock_settings) -> None:
        """Test encryption of long content (clinical notes)."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import decrypt_phi, encrypt_phi

        plaintext = "Clinical note: " + "x" * 10000
        assert decrypt_phi(encrypt_phi(plaintext)) == plaintext


class TestDeterministicEncryption:
    """Tests for AES-SIV deterministic encryption."""

    @patch("app.core.phi_encryption.settings")
    def test_deterministic_roundtrip(self, mock_settings) -> None:
        """Test deterministic encrypt then decrypt returns original."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import (
            decrypt_phi_deterministic,
            encrypt_phi_deterministic,
        )

        plaintext = "P001"
        ciphertext = encrypt_phi_deterministic(plaintext)
        assert decrypt_phi_deterministic(ciphertext) == plaintext

    @patch("app.core.phi_encryption.settings")
    def test_deterministic_produces_same_ciphertext(self, mock_settings) -> None:
        """Test that same plaintext always produces same ciphertext."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import encrypt_phi_deterministic

        ct1 = encrypt_phi_deterministic("P001")
        ct2 = encrypt_phi_deterministic("P001")
        assert ct1 == ct2

    @patch("app.core.phi_encryption.settings")
    def test_different_inputs_produce_different_ciphertext(self, mock_settings) -> None:
        """Test that different plaintexts produce different ciphertexts."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import encrypt_phi_deterministic

        ct1 = encrypt_phi_deterministic("P001")
        ct2 = encrypt_phi_deterministic("P002")
        assert ct1 != ct2

    @patch("app.core.phi_encryption.settings")
    def test_deterministic_empty_passthrough(self, mock_settings) -> None:
        """Test that empty strings pass through."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import encrypt_phi_deterministic

        assert encrypt_phi_deterministic("") == ""

    @patch("app.core.phi_encryption.settings")
    def test_deterministic_enables_equality_search(self, mock_settings) -> None:
        """Test the core use case: encrypted values can be compared for equality."""
        mock_settings.phi_encryption_key = "test-passphrase-for-unit-tests-only"

        from app.core.phi_encryption import encrypt_phi_deterministic

        # Simulate encrypting at write time and searching at query time
        stored = encrypt_phi_deterministic("P001")
        search = encrypt_phi_deterministic("P001")
        assert stored == search  # This enables WHERE encrypted_id = ?


class TestIsEncryptionConfigured:
    """Tests for the is_encryption_configured helper."""

    @patch("app.core.phi_encryption.settings")
    def test_configured_when_key_set(self, mock_settings) -> None:
        mock_settings.phi_encryption_key = "some-key"
        from app.core.phi_encryption import is_encryption_configured

        assert is_encryption_configured() is True

    @patch("app.core.phi_encryption.settings")
    def test_not_configured_when_key_none(self, mock_settings) -> None:
        mock_settings.phi_encryption_key = None
        from app.core.phi_encryption import is_encryption_configured

        assert is_encryption_configured() is False

    @patch("app.core.phi_encryption.settings")
    def test_not_configured_when_key_empty(self, mock_settings) -> None:
        mock_settings.phi_encryption_key = ""
        from app.core.phi_encryption import is_encryption_configured

        assert is_encryption_configured() is False
