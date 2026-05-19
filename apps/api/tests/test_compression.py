"""
Memory Compression Tests (updated for V2 compression behavior)
"""

import pytest
import json
import os
from datetime import datetime
import numpy as np

from src.memory.compression import MemoryCompression


TEST_DICT_FILE = "test_compression_dict.zstd"


@pytest.fixture
def compression():
    """Create compression instance"""
    comp = MemoryCompression(
        level=3,
        dict_size=64 * 1024,  # 64KB
        min_size=256,         # 256B
        enable_dict=True
    )
    yield comp


@pytest.fixture
def test_memory():
    """Create test memory data"""
    return {
        "id": "test123",
        "text": "This is a test memory with enough content to make compression worthwhile. " * 10,
        "type": "fact",
        "salience": 0.8,
        "created_at": datetime.utcnow().isoformat(),
        "thread_id": "thread123",
        "user_id": "user123",
        "persona_id": "persona123",
        "embedding": [0.1] * 1024,
        "metadata": {
            "source": "test",
            "tags": ["test", "compression"],
            "details": "Additional metadata to increase content size " * 5
        }
    }


def test_compression_initialization():
    comp = MemoryCompression()
    assert comp.compressor is not None
    assert comp.training_data == []
    assert not comp.dict_trained
    assert comp.compression_dict is None


def test_memory_compression(compression, test_memory):
    compressed = compression.compress_memory(test_memory)

    assert compressed["id"] == test_memory["id"]
    assert compressed["_compressed"] is True
    assert compressed["_size"] < len(json.dumps(test_memory).encode())
    assert "_ratio" in compressed
    assert "_checksum" in compressed
    assert 0 < compressed["_ratio"] < 1.0


def test_memory_decompression(compression, test_memory):
    compressed = compression.compress_memory(test_memory)
    decompressed = compression.decompress_memory(compressed)
    assert decompressed == test_memory

    # Checksum tamper should raise
    compressed["_checksum"] = "invalid"
    with pytest.raises(Exception):
        compression.decompress_memory(compressed)


def test_dictionary_training(compression):
    """Train dictionary by providing >=100 samples"""
    base_text = "This is test content for dictionary training. "
    for i in range(100):
        memory = {
            "id": f"train{i}",
            "text": base_text * (i % 5 + 1),
            "type": "fact",
            "thread_id": "training",
            "user_id": "user123",
            "persona_id": "persona123"
        }
        compression.compress_memory(memory)

    assert compression.dict_trained
    assert compression.compression_dict is not None
    assert compression.dict_compressor is not None


def test_small_content_handling(compression):
    small_memory = {
        "id": "small123",
        "text": "Small content",
        "type": "fact",
        "thread_id": "test",
        "user_id": "user123",
        "persona_id": "persona123"
    }

    result = compression.compress_memory(small_memory)
    assert result["_compressed"] is False
    assert result == {**small_memory, "_compressed": False, "_size": len(json.dumps(small_memory).encode())}


def test_large_content_handling(compression):
    # Generate 1MB of random-ish text from a limited alphabet (compressible)
    rng = np.random.default_rng(123)
    alphabet = list("abcdefghijklmnopqrstuvwxyz     ")  # add spaces to increase runs
    large_text = "".join(rng.choice(alphabet, size=1_000_000))

    large_memory = {
        "id": "large123",
        "text": large_text,
        "type": "fact",
        "thread_id": "test",
        "user_id": "user123",
        "persona_id": "persona123"
    }

    compressed = compression.compress_memory(large_memory)
    assert compressed["_compressed"]
    assert compressed["_ratio"] < 0.7  # reasonably good compression

    decompressed = compression.decompress_memory(compressed)
    assert decompressed == large_memory


def test_dictionary_persistence(compression, test_memory):
    """Ensure dictionary can be saved/loaded"""
    # Train dictionary
    for _ in range(100):
        compression.compress_memory(test_memory)
    assert compression.dict_trained

    compression.save_dictionary(TEST_DICT_FILE)
    assert os.path.exists(TEST_DICT_FILE)

    new_compression = MemoryCompression()
    new_compression.load_dictionary(TEST_DICT_FILE)

    compressed = new_compression.compress_memory(test_memory)
    decompressed = new_compression.decompress_memory(compressed)
    assert decompressed == test_memory

    os.unlink(TEST_DICT_FILE)


def test_compression_stats_like(compression, test_memory):
    # Just exercise compression to ensure internals populated
    compression.compress_memory(test_memory)
    # No explicit stats method in V2; assert key attributes exist
    assert isinstance(compression.level, int)
    assert isinstance(compression.dict_size, int)
    assert isinstance(compression.min_size, int)
    assert isinstance(compression.dict_trained, bool)


def test_concurrent_operations(compression, test_memory):
    import concurrent.futures
    import copy

    def compress_decompress(memory):
        c = compression.compress_memory(memory)
        return compression.decompress_memory(c)

    memories = [copy.deepcopy(test_memory) for _ in range(10)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(compress_decompress, memories))

    for result in results:
        assert result == test_memory


def test_error_handling():
    # Corrupted compressed data
    comp = MemoryCompression(min_size=1)
    bad = {
        "id": "bad",
        "compressed_data": "corrupted",
        "_compressed": True,
    }
    with pytest.raises(Exception):
        comp.decompress_memory(bad)

    # Invalid compression level should raise at init or compress
    with pytest.raises(Exception):
        MemoryCompression(level=1000)