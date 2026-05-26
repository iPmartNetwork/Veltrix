"""Unit tests for credential encryption module."""
import os
import pytest
from unittest.mock import patch

from outpanel.crypto import (
    _aes_cbc_encrypt,
    _aes_cbc_decrypt,
    _key_expansion,
    AES_BLOCK_SIZE,
)


class TestAESPrimitives:
    """Test the low-level AES implementation."""

    def test_encrypt_decrypt_block(self):
        """AES-CBC encrypt then decrypt returns original data."""
        key = b'\x00' * 32
        iv = b'\x01' * 16
        plaintext = b'Hello Veltrix!!\x02\x02'  # 16 bytes with PKCS7 padding

        ciphertext = _aes_cbc_encrypt(key, iv, plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) == 16

        decrypted = _aes_cbc_decrypt(key, iv, ciphertext)
        assert decrypted == plaintext

    def test_multi_block(self):
        """Multi-block encryption/decryption works."""
        key = bytes(range(32))
        iv = bytes(range(16))
        # 32 bytes = 2 blocks
        plaintext = b'A' * 32

        ciphertext = _aes_cbc_encrypt(key, iv, plaintext)
        assert len(ciphertext) == 32

        decrypted = _aes_cbc_decrypt(key, iv, ciphertext)
        assert decrypted == plaintext

    def test_key_expansion_length(self):
        """Key expansion produces correct number of round keys."""
        key = b'\x00' * 32  # AES-256
        expanded = _key_expansion(key)
        # AES-256: 14 rounds + 1 = 15 round keys, 4 words each = 60
        assert len(expanded) == 60


class TestEncryptDecrypt:
    """Test the high-level encrypt/decrypt functions."""

    def test_passthrough_without_key(self):
        """Without encryption key, values pass through unchanged."""
        with patch.dict(os.environ, {"OUTPANEL_ENCRYPTION_KEY": ""}, clear=False):
            from outpanel import crypto
            # Directly call with no key
            original_fn = crypto.get_encryption_key
            crypto.get_encryption_key = lambda: None
            try:
                assert crypto.encrypt_value("hello") == "hello"
                assert crypto.decrypt_value("hello") == "hello"
            finally:
                crypto.get_encryption_key = original_fn

    def test_encrypt_decrypt_with_key(self):
        """With encryption key, values are encrypted and decryptable."""
        from outpanel import crypto
        import hashlib

        # Mock the key
        test_key = hashlib.sha256(b"test_secret_key").digest()
        original_fn = crypto.get_encryption_key
        crypto.get_encryption_key = lambda: test_key
        try:
            original = "my_secret_password_123"
            encrypted = crypto.encrypt_value(original)

            assert encrypted != original
            assert encrypted.startswith("ENC:")
            assert crypto.decrypt_value(encrypted) == original
        finally:
            crypto.get_encryption_key = original_fn

    def test_empty_value_passthrough(self):
        """Empty values are not encrypted."""
        from outpanel import crypto
        import hashlib

        test_key = hashlib.sha256(b"key").digest()
        original_fn = crypto.get_encryption_key
        crypto.get_encryption_key = lambda: test_key
        try:
            assert crypto.encrypt_value("") == ""
            assert crypto.decrypt_value("") == ""
        finally:
            crypto.get_encryption_key = original_fn

    def test_non_encrypted_value_passthrough(self):
        """Values without ENC: prefix are returned as-is."""
        from outpanel import crypto
        import hashlib

        test_key = hashlib.sha256(b"key").digest()
        original_fn = crypto.get_encryption_key
        crypto.get_encryption_key = lambda: test_key
        try:
            assert crypto.decrypt_value("plain_text") == "plain_text"
        finally:
            crypto.get_encryption_key = original_fn

    def test_different_encryptions_differ(self):
        """Same plaintext produces different ciphertext (random IV)."""
        from outpanel import crypto
        import hashlib

        test_key = hashlib.sha256(b"key2").digest()
        original_fn = crypto.get_encryption_key
        crypto.get_encryption_key = lambda: test_key
        try:
            e1 = crypto.encrypt_value("same_value")
            e2 = crypto.encrypt_value("same_value")
            assert e1 != e2  # Different IVs
        finally:
            crypto.get_encryption_key = original_fn

    def test_tampered_ciphertext_fails(self):
        """Tampered ciphertext returns empty string."""
        from outpanel import crypto
        import hashlib

        test_key = hashlib.sha256(b"key3").digest()
        original_fn = crypto.get_encryption_key
        crypto.get_encryption_key = lambda: test_key
        try:
            encrypted = crypto.encrypt_value("secret")
            # Tamper with the ciphertext
            tampered = encrypted[:10] + "X" + encrypted[11:]
            assert crypto.decrypt_value(tampered) == ""
        finally:
            crypto.get_encryption_key = original_fn
