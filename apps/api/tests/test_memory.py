import pytest
from datetime import datetime
import json
from src.memory.memory_engine import MemoryEngine

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:14:41",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "memory_engine"
}

@pytest.fixture
def test_session_data():
    return {
        "thread_id": "test_thread",
        "user_id": "test_user",
        "messages": [
            {"role": "user", "content": "My favorite color is blue"},
            {"role": "assistant", "content": "I'll remember that you like blue"}
        ],
        "created_at": TEST_METADATA["created_at"],
        "created_by": TEST_METADATA["created_by"]
    }

async def test_load_session(memory_engine, redis_client):
    """Test session loading and creation"""
    session = await memory_engine.load_session("test_user", "test_thread")
    
    assert session["thread_id"] == "test_thread"
    assert session["user_id"] == "test_user"
    assert isinstance(session["messages"], list)
    assert session["created_at"] == TEST_METADATA["created_at"]
    
    # Verify Redis storage
    key = f"sess:test_user:test_thread"
    stored_data = redis_client.get(key)
    assert stored_data is not None
    
    stored_session = json.loads(stored_data)
    assert stored_session == session

async def test_build_context(memory_engine, test_session_data, redis_client):
    """Test context building with memory"""
    # Store test session
    key = f"sess:{test_session_data['user_id']}:{test_session_data['thread_id']}"
    redis_client.setex(
        key,
        memory_engine.redis_ttl,
        json.dumps(test_session_data)
    )
    
    # Build context with memory
    context = await memory_engine.build_context(
        "test_user",
        "test_thread",
        include_memory=True
    )
    
    assert "messages" in context
    assert len(context["messages"]) == len(test_session_data["messages"])
    assert "memory" in context

async def test_append_turn(memory_engine):
    """Test appending conversation turns"""
    thread_id = f"thread_{datetime.now().timestamp()}"
    
    # Add first turn
    await memory_engine.append_turn(
        "test_user",
        thread_id,
        "via",
        "Hello",
        "Hi there!"
    )
    
    # Verify session
    session = await memory_engine.load_session("test_user", thread_id)
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"

async def test_extract_and_store_memories(memory_engine):
    """Test memory extraction and storage"""
    text = "My name is Alice. I prefer tea over coffee. I live in London."
    
    memories = await memory_engine.extract_and_store_memories(
        "test_user",
        "test_thread",
        text
    )
    
    assert len(memories) > 0
    assert any("prefer" in memory for memory in memories)
    assert any("live" in memory for memory in memories)

async def test_memory_loading(memory_engine):
    """Test loading memories from storage"""
    memories = await memory_engine._load_memories(
        "test_user",
        "test_thread"
    )
    
    assert isinstance(memories, list)
    for memory in memories:
        assert "text" in memory
        assert "salience" in memory
        assert "type" in memory

def test_memory_formatting(memory_engine):
    """Test memory formatting for context"""
    test_memories = [
        {"text": "User likes blue", "type": "fact"},
        {"text": "User is from London", "type": "fact"}
    ]
    
    formatted = memory_engine._format_memories(test_memories)
    assert all(memory.startswith("- ") for memory in formatted)