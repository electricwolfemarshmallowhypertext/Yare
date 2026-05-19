"""
Memory System Utilities
Created: 2025-11-02 20:01:15
Author: electricwolfemarshmallowhypertext
"""

import os
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import json
import xxhash
import numpy as np
from pathlib import Path
import asyncio
import structlog
from .exceptions import MemoryException

# Configure logging
logger = structlog.get_logger("sticky.memory.utils")

class MemoryLock:
    """Thread-safe memory locking"""
    
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        
    async def acquire(self, key: str) -> None:
        """Acquire lock for key"""
        async with self._lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
                
        await self._locks[key].acquire()
        
    async def release(self, key: str) -> None:
        """Release lock for key"""
        if key in self._locks:
            self._locks[key].release()
            
    async def cleanup(self) -> None:
        """Remove unused locks"""
        async with self._lock:
            self._locks.clear()

class MemoryCache:
    """Simple LRU cache for memory data"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = asyncio.Lock()
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self._lock:
            if key in self._cache:
                value, _ = self._cache[key]
                # Update access time
                self._cache[key] = (value, datetime.utcnow())
                return value
        return None
        
    async def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        async with self._lock:
            # Check size limit
            if len(self._cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k][1]
                )
                del self._cache[oldest_key]
                
            self._cache[key] = (value, datetime.utcnow())
            
    async def clear(self) -> None:
        """Clear cache"""
        async with self._lock:
            self._cache.clear()

def calculate_vector_similarity(
    v1: List[float],
    v2: List[float]
) -> float:
    """Calculate cosine similarity between vectors"""
    try:
        if len(v1) != len(v2):
            raise ValueError("Vector dimensions must match")
            
        v1_array = np.array(v1)
        v2_array = np.array(v2)
        
        # Normalize vectors
        v1_norm = np.linalg.norm(v1_array)
        v2_norm = np.linalg.norm(v2_array)
        
        if v1_norm == 0 or v2_norm == 0:
            return 0.0
            
        v1_normalized = v1_array / v1_norm
        v2_normalized = v2_array / v2_norm
        
        # Calculate cosine similarity
        similarity = np.dot(v1_normalized, v2_normalized)
        
        # Ensure result is in [-1, 1]
        return float(np.clip(similarity, -1.0, 1.0))
        
    except Exception as e:
        logger.error("Vector similarity calculation failed", error=str(e))
        raise MemoryException("Failed to calculate vector similarity")

def calculate_batch_similarities(
    query_vector: List[float],
    vectors: List[List[float]]
) -> List[float]:
    """Calculate similarities for batch of vectors"""
    try:
        # Convert to numpy arrays
        query = np.array(query_vector)
        batch = np.array(vectors)
        
        # Normalize query vector
        query_norm = np.linalg.norm(query)
        if query_norm > 0:
            query = query / query_norm
            
        # Normalize batch vectors
        batch_norms = np.linalg.norm(batch, axis=1, keepdims=True)
        valid_vectors = batch_norms > 0
        batch[valid_vectors] = batch[valid_vectors] / batch_norms[valid_vectors]
        
        # Calculate similarities
        similarities = np.dot(batch, query)
        
        # Set similarity to 0 for zero-norm vectors
        similarities[~valid_vectors.flatten()] = 0
        
        return similarities.tolist()
        
    except Exception as e:
        logger.error("Batch similarity calculation failed", error=str(e))
        raise MemoryException("Failed to calculate batch similarities")

def generate_memory_id(
    user_id: str,
    thread_id: str,
    text: str,
    timestamp: Optional[datetime] = None
) -> str:
    """Generate unique memory ID"""
    try:
        # Combine components
        components = [
            user_id,
            thread_id,
            text,
            str(timestamp or datetime.utcnow().timestamp())
        ]
        
        # Generate hash
        return xxhash.xxh64('|'.join(components).encode()).hexdigest()
        
    except Exception as e:
        logger.error("Memory ID generation failed", error=str(e))
        raise MemoryException("Failed to generate memory ID")

def calculate_memory_stats(memories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate memory statistics"""
    try:
        stats = {
            "total_memories": len(memories),
            "total_size_bytes": 0,
            "type_counts": {},
            "state_counts": {},
            "persona_counts": {},
            "avg_salience": 0.0,
            "avg_embedding_norm": 0.0
        }
        
        if not memories:
            return stats
            
        # Calculate stats
        total_salience = 0
        total_norm = 0
        valid_embeddings = 0
        
        for memory in memories:
            # Size
            stats["total_size_bytes"] += len(json.dumps(memory).encode())
            
            # Counts
            memory_type = memory.get("type", "unknown")
            stats["type_counts"][memory_type] = stats["type_counts"].get(memory_type, 0) + 1
            
            state = memory.get("metadata", {}).get("state", "unknown")
            stats["state_counts"][state] = stats["state_counts"].get(state, 0) + 1
            
            persona = memory.get("persona_id", "unknown")
            stats["persona_counts"][persona] = stats["persona_counts"].get(persona, 0) + 1
            
            # Averages
            total_salience += memory.get("salience", 0)
            
            if "embedding" in memory:
                embedding_norm = np.linalg.norm(memory["embedding"])
                if embedding_norm > 0:
                    total_norm += embedding_norm
                    valid_embeddings += 1
                    
        # Calculate averages
        stats["avg_salience"] = total_salience / len(memories)
        if valid_embeddings > 0:
            stats["avg_embedding_norm"] = total_norm / valid_embeddings
            
        return stats
        
    except Exception as e:
        logger.error("Stats calculation failed", error=str(e))
        raise MemoryException("Failed to calculate memory statistics")

def cleanup_old_files(
    directory: Union[str, Path],
    pattern: str = "*",
    days: int = 30
) -> List[Path]:
    """Clean up old files matching pattern"""
    try:
        directory = Path(directory)
        if not directory.exists():
            return []
            
        deleted = []
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        for path in directory.glob(pattern):
            if path.is_file():
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    path.unlink()
                    deleted.append(path)
                    
        return deleted
        
    except Exception as e:
        logger.error("File cleanup failed",
            directory=str(directory),
            pattern=pattern,
            error=str(e)
        )
        raise MemoryException("Failed to cleanup files")

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
        
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length-len(ext)] + ext
        
    return filename.strip()

def format_size(size_bytes: int) -> str:
    """Format byte size to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

class AsyncTimer:
    """Async context manager for timing operations"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time: Optional[float] = None
        
    async def __aenter__(self) -> 'AsyncTimer':
        self.start_time = asyncio.get_event_loop().time()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            duration = asyncio.get_event_loop().time() - self.start_time
            logger.info(f"{self.name} completed",
                duration=f"{duration:.3f}s"
            )