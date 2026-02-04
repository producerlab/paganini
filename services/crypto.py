"""
Token encryption/decryption using AES-256-GCM.
Provides secure storage for sensitive data like WB API tokens.
"""
import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from services.logging import logger


# Get encryption key from environment (must be 32 bytes for AES-256)
_ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '')


def _get_key() -> bytes:
    """Get the encryption key, validating it's properly configured."""
    if not _ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not set! Tokens will be stored in plaintext.")
        return b''

    try:
        key = base64.b64decode(_ENCRYPTION_KEY)
        if len(key) != 32:
            logger.error(f"ENCRYPTION_KEY must be 32 bytes (256 bits), got {len(key)} bytes")
            return b''
        return key
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY format: {e}")
        return b''


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a token using AES-256-GCM.

    Returns: base64 encoded string: nonce (12 bytes) + ciphertext + tag (16 bytes)
    If encryption key is not configured, returns plaintext unchanged.
    """
    key = _get_key()
    if not key:
        raise ValueError("ENCRYPTION_KEY not configured - cannot store tokens securely")

    try:
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        # Combine nonce + ciphertext and encode as base64
        encrypted = base64.b64encode(nonce + ciphertext).decode('utf-8')
        return f"enc:{encrypted}"  # Prefix to identify encrypted values
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError(f"Token encryption failed: {e}")


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt a token encrypted with encrypt_token().

    If the value doesn't have 'enc:' prefix, returns it unchanged (legacy plaintext).
    """
    # Check if it's an encrypted value
    if not encrypted.startswith('enc:'):
        # Legacy plaintext token - return as-is
        return encrypted

    key = _get_key()
    if not key:
        logger.error("Cannot decrypt: ENCRYPTION_KEY not configured")
        # Return empty to prevent using encrypted blob as token
        return ''

    try:
        # Remove 'enc:' prefix and decode base64
        data = base64.b64decode(encrypted[4:])
        nonce = data[:12]
        ciphertext = data[12:]

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ''


def generate_encryption_key() -> str:
    """
    Generate a new random encryption key.
    Use this to create a key for ENCRYPTION_KEY env variable.

    Returns: base64 encoded 32-byte key
    """
    key = secrets.token_bytes(32)
    return base64.b64encode(key).decode('utf-8')


def is_token_encrypted(token: str) -> bool:
    """Check if a token is encrypted (has 'enc:' prefix)."""
    return token.startswith('enc:')
