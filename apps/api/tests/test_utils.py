"""
Memory Utils Tests (fixed lock timing and deterministic ID)
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

from src.memory.utils import (
    MemoryLock,
    MemoryCache,
    calculate_vector_similarity,
    calculate_batch_similarities,
    generate_memory_id,
    calculate_memory_stats,
    cleanup_old_files,
    sanitize_filename,
    format_size,
    AsyncTimer
)


@pytest.fixture
def memory_lock():
    return MemoryLock()


@pytest.fixture
def memory_cache():
    return MemoryCache(max_size=10)


@pytest.fixture
def test_vectors():
    return {
        "v1": [0.1] * 1024,
        "v2": [-0.1] * 1024,
        "v3": [0.0] * 1024,
        "batch": [[0.1] * 1024 for _ in range(10)]
    }


@pytest.mark.asyncio
async def test_memory_lock(memory_lock):
    key = "test_key"

    # Acquire first lock
    await memory_lock.acquire(key)

    # Second acquisition should time out
    async def try_lock():
        await memory_lock.acquire(key)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(try_lock(), timeout=0.1)

    # Release and reacquire works
    await memory_lock.release(key)
    await memory_lock.acquire(key)
    await memory_lock.release(key)

    # Cleanup
    await memory_lock.cleanup()
    assert not memory_lock._locks


@pytest.mark.asyncio
async def test_memory_cache(memory_cache):
    await memory_cache.set("key1", "value1")
    assert await memory_cache.get("key1") == "value1"

    # Size limit eviction
    for i in range(15):
        await memory_cache.set(f"key{i}", f"value{i}")

    assert len(memory_cache._cache) == 10
    assert await memory_cache.get("key0") is None
    assert await memory_cache.get("key14") == "value14"

    await memory_cache.clear()
    assert len(memory_cache._cache) == 0


def test_vector_similarity(test_vectors):
    sim1 = calculate_vector_similarity(test_vectors["v1"], test_vectors["v1"])
    assert sim1 == pytest.approx(1.0)

    sim2 = calculate_vector_similarity(test_vectors["v1"], test_vectors["v2"])
    assert sim2 == pytest.approx(-1.0)

    sim3 = calculate_vector_similarity(test_vectors["v1"], test_vectors["v3"])
    assert sim3 == 0.0

    with pytest.raises(Exception):
        calculate_vector_similarity(test_vectors["v1"], test_vectors["v1"][:100])


def test_batch_similarities(test_vectors):
    query = test_vectors["v1"]
    batch = test_vectors["batch"]

    similarities = calculate_batch_similarities(query, batch)
    assert len(similarities) == len(batch)
    assert all(0.9 < s <= 1.0 for s in similarities)

    zero_batch = [[0.0] * 1024 for _ in range(5)]
    zero_sims = calculate_batch_similarities(query, zero_batch)
    assert all(s == 0.0 for s in zero_sims)


def test_memory_id_generation():
    params = {
        "user_id": "user123",
        "thread_id": "thread123",
        "text": "Test content"
    }

    # Deterministic when timestamp is provided
    ts = datetime(2025, 1, 1)
    id1 = generate_memory_id(**params, timestamp=ts)
    id2 = generate_memory_id(**params, timestamp=ts)
    assert id1 == id2

    # Different content yields different id
    id3 = generate_memory_id(**{**params, "text": "Different"}, timestamp=ts)
    assert id1 != id3

    # Without timestamp, ids should generally differ across calls
    id4 = generate_memory_id(**params)
    id5 = generate_memory_id(**params)
    assert id4 != id5


def test_memory_stats():
    memories = [
        {
            "id": f"test{i}",
            "text": f"Memory {i}",
            "type": "fact" if i % 2 == 0 else "interaction",
            "salience": 0.5 + i / 10,
            "persona_id": f"persona{i%3}",
            "embedding": [0.1] * 1024,
            "metadata": {"state": "active"}
        }
        for i in range(5)
    ]

    stats = calculate_memory_stats(memories)

    assert stats["total_memories"] == 5
    assert stats["total_size_bytes"] > 0
    assert len(stats["type_counts"]) == 2
    assert len(stats["persona_counts"]) == 3
    assert 0 < stats["avg_salience"] < 1.5
    assert stats["avg_embedding_norm"] > 0


def test_file_cleanup(tmp_path):
    old_time = datetime.utcnow() - timedelta(days=31)
    new_time = datetime.utcnow()

    old_file = tmp_path / "old.txt"
    new_file = tmp_path / "new.txt"

    old_file.touch()
    new_file.touch()

    os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
    os.utime(new_file, (new_time.timestamp(), new_time.timestamp()))

    deleted = cleanup_old_files(tmp_path, pattern="*.txt", days=30)
    assert len(deleted) == 1
    assert old_file in deleted
    assert not old_file.exists()
    assert new_file.exists()


def test_filename_sanitization():
    tests = [
        ("test.txt", "test.txt"),
        ("test/file.txt", "test_file.txt"),
        ('test"file.txt', "test_file.txt"),
        ("." * 300 + ".txt", "." * 251 + ".txt"),
        (" spaces.txt ", "spaces.txt")
    ]

    for input_name, expected in tests:
        assert sanitize_filename(input_name) == expected


def test_size_formatting():
    tests = [
        (100, "100.00 B"),
        (1024, "1.00 KB"),
        (1024 * 1024, "1.00 MB"),
        (1024 * 1024 * 1024, "1.00 GB"),
        (1024 * 1024 * 1024 * 1024, "1.00 TB")
    ]

    for size, expected in tests:
        assert format_size(size) == expected


@pytest.mark.asyncio
async def test_async_timer():
    async with AsyncTimer("test_op") as timer:
        await asyncio.sleep(0.05)

    assert timer.name == "test_op"
    assert timer.start_time is not None