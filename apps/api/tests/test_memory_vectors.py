"""
Memory Vector Store Tests
Created: 2025-11-02 19:41:39
Author: electricwolfemarshmallowhypertext
"""

import pytest
import os
import shutil
from datetime import datetime
import numpy as np
from src.memory.memory_engine import MemoryEngine
from src.exceptions import MemoryException

TEST_DATA_DIR = "test_memory_store"
REDIS_URL = "redis://localhost:6379/0"

@pytest.fixture(autouse=True)
async def setup_teardown():
    """Setup and teardown test environment"""
    # Setup
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    
    yield
    
    # Teardown
    shutil.rmtree(TEST_DATA_DIR)

@pytest.fixture
async def memory_engine():
    """Create memory engine instance"""
    engine = MemoryEngine(
        redis_url=REDIS_URL,
        persist_directory=TEST_DATA_DIR,
        max_memories=20,
        sqlite_fallback_path=f"{TEST_DATA_DIR}/fallback.db"
    )
    await engine.initialize()
    return engine

@pytest.mark.asyncio
async def test_embedding_generation(memory_engine):
    """Test vector embedding generation"""
    # Test basic embedding
    text = "Test memory content"
    embedding = await memory_engine._get_embedding(text)
    assert len(embedding) == 1024
    assert all(isinstance(x, float) for x in embedding)
    assert -1 <= min(embedding) <= max(embedding) <= 1
    
    # Test consistency
    embedding2 = await memory_engine._get_embedding(text)
    assert np.allclose(embedding, embedding2, atol=1e-5)
    
    # Test empty text
    with pytest.raises(MemoryException):
        await memory_engine._get_embedding("")
    
    # Test long text
    long_text = "test " * 1000
    long_embedding = await memory_engine._get_embedding(long_text)
    assert len(long_embedding) == 1024

@pytest.mark.asyncio
async def test_memory_storage(memory_engine):
    """Test memory storage with vectors"""
    # Store test memory
    text = "Test memory content"
    embedding = await memory_engine._get_embedding(text)
    
    event = await memory_engine.store_memory(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        text=text,
        type="test",
        salience=0.5,
        embedding=embedding
    )
    
    # Verify stored memory
    assert event["id"]
    assert event["text"] == text
    assert event["user_id"] == "test_user"
    assert event["persona_id"] == "test_persona"
    assert event["type"] == "test"
    assert isinstance(event["created_at"], str)
    
    # Test size limits
    large_text = "large memory " * 1000
    with pytest.raises(MemoryException, match="Memory size exceeds"):
        await memory_engine.store_memory(
            user_id="test_user",
            thread_id="test_thread", 
            persona_id="test_persona",
            text=large_text,
            type="test",
            salience=0.5,
            embedding=await memory_engine._get_embedding(large_text)
        )

@pytest.mark.asyncio
async def test_vector_similarity_search(memory_engine):
    """Test vector similarity search"""
    # Store test memories
    memories = [
        "The cat sat on the mat",
        "Dogs love playing fetch",
        "Birds fly in the sky",
        "Fish swim in the ocean",
        "Rabbits hop in fields"
    ]
    
    for text in memories:
        embedding = await memory_engine._get_embedding(text)
        await memory_engine.store_memory(
            user_id="test_user",
            thread_id="test_thread",
            persona_id="test_persona",
            text=text,
            type="test",
            salience=0.5,
            embedding=embedding
        )
    
    # Test exact query
    context = await memory_engine.build_context(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        query="Tell me about cats"
    )
    assert len(context["memory"]) == 3  # Verify top 3 limit
    assert any("cat" in m for m in context["memory"])
    
    # Test semantic similarity
    context = await memory_engine.build_context(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        query="What about pets?"
    )
    assert len(context["memory"]) == 3
    assert any("cat" in m for m in context["memory"])
    assert any("dog" in m for m in context["memory"])

@pytest.mark.asyncio
async def test_memory_transfer(memory_engine):
    """Test memory context transfer between personas"""
    # Store test memories
    texts = [
        "Important fact about topic A",
        "Crucial information about B",
        "Key insight about topic C",
        "Random unrelated fact",
        "Critical detail about A"
    ]
    
    for text in texts:
        embedding = await memory_engine._get_embedding(text)
        await memory_engine.store_memory(
            user_id="test_user",
            thread_id="test_thread",
            persona_id="persona_a",
            text=text,
            type="test",
            salience=0.5,
            embedding=embedding
        )
    
    # Test context transfer
    transferred = await memory_engine.transfer_context(
        user_id="test_user",
        from_persona="persona_a",
        to_persona="persona_b",
        query="Tell me about topic A"
    )
    
    assert len(transferred) > 0
    assert any("topic A" in m["text"] for m in transferred)
    
    # Verify transferred memories are queryable
    context = await memory_engine.build_context(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="persona_b",
        query="topic A"
    )
    assert len(context["memory"]) > 0
    assert any("topic A" in m for m in context["memory"])

@pytest.mark.asyncio
async def test_memory_cleanup(memory_engine):
    """Test memory cleanup and size limits"""
    # Store max_memories + 5 memories
    for i in range(memory_engine.max_memories + 5):
        text = f"Memory {i}"
        embedding = await memory_engine._get_embedding(text)
        await memory_engine.store_memory(
            user_id="test_user",
            thread_id="test_thread",
            persona_id="test_persona",
            text=text,
            type="test",
            salience=0.5,
            embedding=embedding
        )
        
    # Force cleanup
    await memory_engine._cleanup_old_data()
    
    # Verify memory count
    context = await memory_engine.build_context(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        query="Memory"
    )
    assert len(context["memory"]) <= memory_engine.max_memories

@pytest.mark.asyncio
async def test_memory_persistence(memory_engine):
    """Test memory persistence across restarts"""
    # Store test memory
    text = "Persistent memory test"
    embedding = await memory_engine._get_embedding(text)
    await memory_engine.store_memory(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        text=text,
        type="test",
        salience=0.5,
        embedding=embedding
    )
    
    # Create new engine instance
    new_engine = MemoryEngine(
        redis_url=REDIS_URL,
        persist_directory=TEST_DATA_DIR,
        sqlite_fallback_path=f"{TEST_DATA_DIR}/fallback.db"
    )
    await new_engine.initialize()
    
    # Verify memory persists
    context = await new_engine.build_context(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        query=text
    )
    assert len(context["memory"]) > 0
    assert any(text in m for m in context["memory"])

@pytest.mark.asyncio
async def test_sqlite_fallback(memory_engine):
    """Test SQLite fallback functionality"""
    # Simulate Chroma failure
    memory_engine.client = None
    
    # Store should use SQLite
    text = "Fallback test"
    embedding = await memory_engine._get_embedding(text)
    event = await memory_engine.store_memory(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        text=text,
        type="test",
        salience=0.5,
        embedding=embedding
    )
    
    assert event["id"]
    
    # Verify retrieval from SQLite
    context = await memory_engine.build_context(
        user_id="test_user",
        thread_id="test_thread",
        persona_id="test_persona",
        query=text
    )
    assert len(context["memory"]) > 0

@pytest.mark.asyncio
async def test_error_handling(memory_engine):
    """Test error handling scenarios"""
    # Invalid embedding
    with pytest.raises(MemoryException):
        await memory_engine.store_memory(
            user_id="test_user",
            thread_id="test_thread",
            persona_id="test_persona",
            text="Test",
            type="test",
            salience=0.5,
            embedding=[0] * 100  # Wrong dimension
        )
    
    # Missing user_id
    with pytest.raises(MemoryException):
        await memory_engine.store_memory(
            user_id="",
            thread_id="test_thread",
            persona_id="test_persona",
            text="Test",
            type="test",
            salience=0.5,
            embedding=await memory_engine._get_embedding("Test")
        )
    
    # Invalid thread_id
    with pytest.raises(MemoryException):
        await memory_engine.build_context(
            user_id="test_user",
            thread_id="",
            persona_id="test_persona",
            query="Test"
        )