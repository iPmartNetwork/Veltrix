"""Unit tests for credential encryption module."""
import os
import pytest
from unittest.mock import patch


class TestEncryption:
    def test_passthrough_without_key(self):
        """Without encryption key, values pass through unchanged."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": ""}):
            from outpanel.crypto import encrypt_value, decrypt_value
            assert encrypt_value("hello") == "hello"
            assert decrypt_value("hello") == "hello"

    def test_encrypt_decrypt_with_key(self):
        """With encryption key, values are encrypted and decryptable."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": "test_secret_key_for_unit_tests"}):
            # Force reimport to pick up new env
            import importlib
            import outpanel.crypto
            importlib.reload(outpanel.crypto)
            from outpanel.crypto import encrypt_value, decrypt_value

            original = "my_secret_password_123"
            encrypted = encrypt_value(original)

            assert encrypted != original
            assert encrypted.startswith("ENC:")
            assert decrypt_value(encrypted) == original

    def test_empty_value_passthrough(self):
        """Empty values are not encrypted."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": "some_key"}):
            import importlib
            import outpanel.crypto
            importlib.reload(outpanel.crypto)
            from outpanel.crypto import encrypt_value, decrypt_value

            assert encrypt_value("") == ""
            assert decrypt_value("") == ""

    def test_non_encrypted_value_passthrough(self):
        """Values without ENC: prefix are returned as-is."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": "some_key"}):
            import importlib
            import outpanel.crypto
            importlib.reload(outpanel.crypto)
            from outpanel.crypto import decrypt_value

            assert decrypt_value("plain_text") == "plain_text"

    def test_different_encryptions_differ(self):
        """Same plaintext produces different ciphertext (random IV)."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": "test_key_123"}):
            import importlib
            import outpanel.crypto
            importlib.reload(outpanel.crypto)
            from outpanel.crypto import encrypt_value

            e1 = encrypt_value("same_value")
            e2 = encrypt_value("same_value")
            assert e1 != e2  # Different IVs

    def test_tampered_ciphertext_fails(self):
        """Tampered ciphertext returns empty string."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": "test_key_456"}):
            import importlib
            import outpanel.crypto
            importlib.reload(outpanel.crypto)
            from outpanel.crypto import encrypt_value, decrypt_value

            encrypted = encrypt_value("secret")
            # Tamper with the ciphertext
            tampered = encrypted[:10] + "X" + encrypted[11:]
            assert decrypt_value(tampered) == ""
