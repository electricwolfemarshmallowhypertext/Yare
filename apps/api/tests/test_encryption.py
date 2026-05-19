"""
Memory Encryption Tests (updated to align with V2 encryption API)
"""

import pytest
import os
from datetime import datetime
from cryptography.fernet import InvalidToken

from src.memory.encryption import MemoryEncryption


TEST_FILE = "test_key.key"
TEST_PASSWORD = "test-encryption-password"
TEST_SALT = b"0123456789abcdef"  # 16 bytes


@pytest.fixture
def encryption():
    """Create encryption instance using password+salt derivation."""
    enc = MemoryEncryption(password=TEST_PASSWORD, salt=TEST_SALT)
    yield enc


@pytest.fixture
def test_memory():
    """Create test memory data"""
    return {
        "id": "test123",
        "text": "Test memory content",
        "type": "fact",
        "salience": 0.8,
        "created_at": datetime.utcnow().isoformat(),
        "thread_id": "thread123",
        "user_id": "user123",
        "persona_id": "persona123",
        "embedding": [0.1] * 1024,
        "metadata": {
            "source": "test",
            "tags": ["test", "memory"]
        }
    }


def test_encryption_initialization():
    """Test various initialization modes"""
    # Password+salt
    enc = MemoryEncryption(password=TEST_PASSWORD, salt=TEST_SALT)
    assert isinstance(enc.key, (bytes, bytearray))

    # File-based initialization via save/load
    enc.save_key(TEST_FILE)
    assert os.path.exists(TEST_FILE)
    enc2 = MemoryEncryption.load_key(TEST_FILE)
    assert enc2.key == enc.key
    os.unlink(TEST_FILE)

    # New random key generation
    enc3 = MemoryEncryption()
    assert isinstance(enc3.key, (bytes, bytearray))
    assert enc3.key != enc.key


def test_memory_encryption(encryption, test_memory):
    """Test memory encryption"""
    encrypted = encryption.encrypt_memory(test_memory)

    assert encrypted["id"] == test_memory["id"]
    assert encrypted["text"] != test_memory["text"]
    assert "embedding" in encrypted
    assert encrypted["embedding"] != test_memory["embedding"]

    # Verify metadata encryption
    assert "metadata" in encrypted
    assert encrypted["metadata"] != test_memory["metadata"]

    # Test without metadata
    encrypted_no_meta = encryption.encrypt_memory(
        test_memory,
        include_metadata=False
    )
    assert "metadata" not in encrypted_no_meta


def test_memory_decryption(encryption, test_memory):
    """Test memory decryption"""
    encrypted = encryption.encrypt_memory(test_memory)
    decrypted = encryption.decrypt_memory(encrypted)

    assert decrypted["id"] == test_memory["id"]
    assert decrypted["text"] == test_memory["text"]
    assert decrypted["embedding"] == test_memory["embedding"]
    assert decrypted["metadata"] == test_memory["metadata"]

    # Test without metadata
    decrypted_no_meta = encryption.decrypt_memory(encrypted, include_metadata=False)
    assert "metadata" not in decrypted_no_meta


def test_key_rotation(encryption, test_memory):
    """Test encryption key rotation"""
    encrypted = encryption.encrypt_memory(test_memory)

    # Rotate to new random key; keep old for migration
    old_key = encryption.rotate_key()

    # Decrypting with new key should fail
    with pytest.raises(InvalidToken):
        encryption.decrypt_memory(encrypted)

    # Decrypt with old key succeeds
    old_encryption = MemoryEncryption(key=old_key)
    decrypted = old_encryption.decrypt_memory(encrypted)
    assert decrypted["text"] == test_memory["text"]

    # Encrypt with new key and decrypt with new key
    new_encrypted = encryption.encrypt_memory(test_memory)
    new_decrypted = encryption.decrypt_memory(new_encrypted)
    assert new_decrypted["text"] == test_memory["text"]


def test_key_file_operations(encryption, test_memory):
    """Test key file save/load operations"""
    encryption.save_key(TEST_FILE)
    assert os.path.exists(TEST_FILE)

    new_encryption = MemoryEncryption.load_key(TEST_FILE)

    encrypted = encryption.encrypt_memory(test_memory)
    decrypted = new_encryption.decrypt_memory(encrypted)
    assert decrypted["text"] == test_memory["text"]

    os.unlink(TEST_FILE)


def test_invalid_token(encryption, test_memory):
    """Test invalid encryption token handling"""
    encrypted = encryption.encrypt_memory(test_memory)

    # Corrupt the ciphertext
    encrypted["text"] = encrypted["text"][:-10] + "invalid"

    with pytest.raises(InvalidToken):
        encryption.decrypt_memory(encrypted)


def test_large_content(encryption):
    """Test encryption of large content"""
    large_memory = {
        "id": "large123",
        "text": "x" * 1_000_000,  # 1MB text
        "type": "fact",
        "salience": 0.5,
        "created_at": datetime.utcnow().isoformat(),
        "thread_id": "thread123",
        "user_id": "user123",
        "persona_id": "persona123"
    }

    encrypted = encryption.encrypt_memory(large_memory)
    decrypted = encryption.decrypt_memory(encrypted)
    assert decrypted["text"] == large_memory["text"]


def test_encryption_error_handling():
    """Test error handling for invalid key sources"""
    # Load from invalid path
    with pytest.raises(FileNotFoundError):
        MemoryEncryption.load_key("nonexistent.key")

    # Invalid key format
    with pytest.raises(ValueError):
        MemoryEncryption(key=b"invalid")

    # Save to invalid location
    enc = MemoryEncryption()
    with pytest.raises(Exception):
        enc.save_key("/invalid/path/key.key")


def test_concurrent_operations(encryption, test_memory):
    """Test concurrent encryption operations"""
    import concurrent.futures
    import copy

    def encrypt_decrypt(memory):
        encrypted = encryption.encrypt_memory(memory)
        return encryption.decrypt_memory(encrypted)

    memories = [copy.deepcopy(test_memory) for _ in range(10)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(encrypt_decrypt, memories))

    for result in results:
        assert result["text"] == test_memory["text"]
        assert result["embedding"] == test_memory["embedding"]


def test_memory_cleanup(encryption, test_memory):
    """Test decryption fails after key rotation without old key"""
    encrypted = encryption.encrypt_memory(test_memory)

    # Rotate key multiple times
    for _ in range(3):
        encryption.rotate_key()

    with pytest.raises(InvalidToken):
        encryption.decrypt_memory(encrypted)