"""Credential encryption at rest for Veltrix.

Encrypts sensitive fields (x-ui passwords, API tokens) before storing in SQLite.
Uses AES-256-CBC with HMAC-SHA256 for authenticated encryption.
Key is derived from OUTPANEL_ENCRYPTION_KEY environment variable.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Any


# AES block size
AES_BLOCK_SIZE = 16
AES_KEY_SIZE = 32
HMAC_SIZE = 32


def get_encryption_key() -> bytes | None:
    """Get the encryption key from environment. Returns None if not configured."""
    raw = os.getenv("OUTPANEL_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    # Derive a 32-byte key using SHA-256
    return hashlib.sha256(raw.encode("utf-8")).digest()


def is_encryption_enabled() -> bool:
    """Check if encryption is configured."""
    return get_encryption_key() is not None


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext with IV and HMAC.

    Format: ENC:base64(iv + ciphertext + hmac)

    If encryption is not configured, returns plaintext as-is.
    """
    if not plaintext:
        return plaintext

    key = get_encryption_key()
    if not key:
        return plaintext

    # Split key: first 32 bytes for AES, derive another 32 for HMAC
    aes_key = key[:AES_KEY_SIZE]
    hmac_key = hashlib.sha256(key + b"hmac-key").digest()

    # Generate random IV
    iv = secrets.token_bytes(AES_BLOCK_SIZE)

    # Pad plaintext (PKCS7)
    data = plaintext.encode("utf-8")
    pad_len = AES_BLOCK_SIZE - (len(data) % AES_BLOCK_SIZE)
    padded = data + bytes([pad_len] * pad_len)

    # AES-256-CBC encryption (pure Python implementation)
    ciphertext = _aes_cbc_encrypt(aes_key, iv, padded)

    # HMAC for authentication
    mac = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()

    # Combine: IV + ciphertext + HMAC
    combined = iv + ciphertext + mac
    encoded = base64.b64encode(combined).decode("ascii")

    return f"ENC:{encoded}"


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value. Returns plaintext.

    If value doesn't start with 'ENC:', returns as-is (backward compatible).
    """
    if not stored or not stored.startswith("ENC:"):
        return stored or ""

    key = get_encryption_key()
    if not key:
        # Can't decrypt without key — return empty to avoid exposing garbled data
        return ""

    aes_key = key[:AES_KEY_SIZE]
    hmac_key = hashlib.sha256(key + b"hmac-key").digest()

    try:
        combined = base64.b64decode(stored[4:])
    except Exception:
        return ""

    if len(combined) < AES_BLOCK_SIZE + AES_BLOCK_SIZE + HMAC_SIZE:
        return ""

    # Extract parts
    iv = combined[:AES_BLOCK_SIZE]
    mac = combined[-HMAC_SIZE:]
    ciphertext = combined[AES_BLOCK_SIZE:-HMAC_SIZE]

    # Verify HMAC
    expected_mac = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        return ""

    # Decrypt
    try:
        padded = _aes_cbc_decrypt(aes_key, iv, ciphertext)
    except Exception:
        return ""

    # Remove PKCS7 padding
    if not padded:
        return ""
    pad_len = padded[-1]
    if pad_len < 1 or pad_len > AES_BLOCK_SIZE:
        return ""
    if padded[-pad_len:] != bytes([pad_len] * pad_len):
        return ""

    return padded[:-pad_len].decode("utf-8", errors="replace")


def encrypt_server_credentials(server: dict[str, Any]) -> dict[str, Any]:
    """Encrypt sensitive fields in a server dict before storage."""
    result = dict(server)
    if "password" in result and result["password"]:
        result["password"] = encrypt_value(result["password"])
    return result


def decrypt_server_credentials(server: dict[str, Any]) -> dict[str, Any]:
    """Decrypt sensitive fields in a server dict after retrieval."""
    if not server:
        return server
    result = dict(server)
    if "password" in result and result["password"]:
        result["password"] = decrypt_value(result["password"])
    return result


# ---------------------------------------------------------------------------
# Pure-Python AES-256-CBC (for environments without cryptography package)
# ---------------------------------------------------------------------------
# This is a compact AES implementation for portability.
# For high-throughput production, install the `cryptography` package.

# AES S-Box
_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i

_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _mix_column(col: list[int]) -> list[int]:
    t = col[0] ^ col[1] ^ col[2] ^ col[3]
    u = col[0]
    col[0] ^= _xtime(col[0] ^ col[1]) ^ t
    col[1] ^= _xtime(col[1] ^ col[2]) ^ t
    col[2] ^= _xtime(col[2] ^ col[3]) ^ t
    col[3] ^= _xtime(col[3] ^ u) ^ t
    return col


def _inv_mix_column(col: list[int]) -> list[int]:
    u = _xtime(_xtime(col[0] ^ col[2]))
    v = _xtime(_xtime(col[1] ^ col[3]))
    col[0] ^= u
    col[1] ^= v
    col[2] ^= u
    col[3] ^= v
    return _mix_column(col)


def _key_expansion(key: bytes) -> list[list[int]]:
    nk = len(key) // 4
    nr = nk + 6
    w: list[list[int]] = []
    for i in range(nk):
        w.append(list(key[4*i:4*i+4]))
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i-1])
        if i % nk == 0:
            temp = [_SBOX[temp[1]] ^ _RCON[i//nk - 1], _SBOX[temp[2]], _SBOX[temp[3]], _SBOX[temp[0]]]
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i-nk][j] ^ temp[j] for j in range(4)])
    return w


def _aes_encrypt_block(state: list[int], round_keys: list[list[int]], nr: int) -> list[int]:
    # AddRoundKey
    for i in range(16):
        state[i] ^= round_keys[i // 4][i % 4]

    for rnd in range(1, nr + 1):
        # SubBytes
        state = [_SBOX[b] for b in state]
        # ShiftRows
        state = [
            state[0], state[5], state[10], state[15],
            state[4], state[9], state[14], state[3],
            state[8], state[13], state[2], state[7],
            state[12], state[1], state[6], state[11],
        ]
        # MixColumns (skip last round)
        if rnd < nr:
            for c in range(4):
                col = [state[c*4+r] for r in range(4)]
                col = _mix_column(col)
                for r in range(4):
                    state[c*4+r] = col[r]
        # AddRoundKey
        rk_offset = rnd * 4
        for i in range(16):
            state[i] ^= round_keys[rk_offset + i // 4][i % 4]

    return state


def _aes_decrypt_block(state: list[int], round_keys: list[list[int]], nr: int) -> list[int]:
    # AddRoundKey
    rk_offset = nr * 4
    for i in range(16):
        state[i] ^= round_keys[rk_offset + i // 4][i % 4]

    for rnd in range(nr - 1, -1, -1):
        # InvShiftRows
        state = [
            state[0], state[13], state[10], state[7],
            state[4], state[1], state[14], state[11],
            state[8], state[5], state[2], state[15],
            state[12], state[9], state[6], state[3],
        ]
        # InvSubBytes
        state = [_INV_SBOX[b] for b in state]
        # AddRoundKey
        rk_offset = rnd * 4
        for i in range(16):
            state[i] ^= round_keys[rk_offset + i // 4][i % 4]
        # InvMixColumns (skip round 0)
        if rnd > 0:
            for c in range(4):
                col = [state[c*4+r] for r in range(4)]
                col = _inv_mix_column(col)
                for r in range(4):
                    state[c*4+r] = col[r]

    return state


def _aes_cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    round_keys = _key_expansion(key)
    nr = len(key) // 4 + 6
    prev = list(iv)
    result = bytearray()

    for i in range(0, len(data), AES_BLOCK_SIZE):
        block = list(data[i:i+AES_BLOCK_SIZE])
        # XOR with previous ciphertext (or IV)
        xored = [block[j] ^ prev[j] for j in range(AES_BLOCK_SIZE)]
        encrypted = _aes_encrypt_block(xored, round_keys, nr)
        result.extend(encrypted)
        prev = encrypted

    return bytes(result)


def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    round_keys = _key_expansion(key)
    nr = len(key) // 4 + 6
    prev = list(iv)
    result = bytearray()

    for i in range(0, len(data), AES_BLOCK_SIZE):
        block = list(data[i:i+AES_BLOCK_SIZE])
        decrypted = _aes_decrypt_block(list(block), round_keys, nr)
        # XOR with previous ciphertext (or IV)
        plaintext = [decrypted[j] ^ prev[j] for j in range(AES_BLOCK_SIZE)]
        result.extend(plaintext)
        prev = block

    return bytes(result)
