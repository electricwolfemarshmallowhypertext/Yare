"""
Memory Engine with Vector Storage and Persistence
Created: 2025-11-02 19:46:15 
Author: electricwolfemarshmallowhypertext
"""

import os
from pathlib import Path
import shutil
import logging
from typing import Optional, Dict, List, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import sqlite3
from datetime import datetime, timedelta
import json
import zstandard as zstd
import xxhash
from sentence_transformers import SentenceTransformer
import numpy as np
from prometheus_client import Counter, Histogram, Gauge
import structlog
from ..exceptions import MemoryException

# Configure logging
logger = structlog.get_logger("sticky.memory.engine")

# Metrics
MEMORY_SIZE = Gauge(
    "sticky_memory_size_bytes",
    "Memory store size in bytes",
    ["store"]
)
MEMORY_OPS = Counter(
    "sticky_memory_operations_total",
    "Memory operations count",
    ["operation"]
)
MEMORY_OP_DURATION = Histogram(
    "sticky_memory_operation_duration_seconds",
    "Memory operation duration"
)
EMBEDDING_DURATION = Histogram(
    "sticky_embedding_generation_duration_seconds",
    "Embedding generation duration"
)
CACHE_HITS = Counter(
    "sticky_memory_cache_hits_total",
    "Memory cache hit count"
)

class MemoryEngine:
    """Memory engine with vector storage and persistence"""
    
    def __init__(
        self,
        persist_dir: str = "memory_store",
        sqlite_fallback_path: str = "memory_store/fallback.db",
        max_size_mb: int = 5,
        backup_dir: str = "memory_store/backups",
        env: str = "production",
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_cache_size: int = 1000,
        embedding_batch_size: int = 32
    ):
        self.persist_dir = Path(persist_dir)
        self.sqlite_path = Path(sqlite_fallback_path)
        self.backup_dir = Path(backup_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.env = env
        
        # Create directories
        self.persist_dir.mkdir(exist_ok=True, parents=True)
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        self.sqlite_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Initialize components
        self.client = None
        self.sqlite_conn = None
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_cache = {}
        self.embedding_cache_size = embedding_cache_size
        self.embedding_batch_size = embedding_batch_size
        
        # Initialize compression
        self.compressor = zstd.ZstdCompressor(level=3)
        
        # Track initialization
        self.initialized = False
        
    async def initialize(self) -> None:
        """Initialize vector store with fallback and monitoring"""
        try:
            # Setup embedding function
            sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            
            # Initialize Chroma
            self.client = chromadb.Client(Settings(
                persist_directory=str(self.persist_dir),
                chroma_db_impl="duckdb+parquet",
                anonymized_telemetry=False,
                allow_reset=self.env == "development"
            ))
            
            # Setup collections with proper schemas
            await self._setup_collections(sentence_transformer_ef)
            
            # Initialize SQLite fallback
            await self._setup_sqlite_fallback()
            
            # Verify size limits
            await self._check_storage_limits()
            
            # Initial backup
            await self._create_backup()
            
            self.initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize memory engine", error=str(e))
            raise MemoryException("Memory initialization failed") from e
            
    async def _setup_collections(self, embedding_fn: Any) -> None:
        """Setup required collections with proper configuration"""
        collections = {
            "user_memories": {
                "metadata": {"hnsw:space": "cosine", "hnsw:M": 16},
                "embedding_function": embedding_fn
            },
            "persona_contexts": {
                "metadata": {"hnsw:space": "cosine", "hnsw:M": 8},
                "embedding_function": embedding_fn
            }
        }
        
        for name, config in collections.items():
            try:
                self.client.create_collection(
                    name=name,
                    metadata=config["metadata"],
                    embedding_function=config["embedding_function"]
                )
            except ValueError: # Collection exists
                continue
                
    async def _setup_sqlite_fallback(self) -> None:
        """Initialize SQLite fallback database"""
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        cursor = self.sqlite_conn.cursor()
        
        # Create tables for fallback storage
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            persona_id TEXT,
            content TEXT,
            embedding BLOB,
            created_at TIMESTAMP,
            metadata TEXT
        )
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_persona 
        ON memories(user_id, persona_id)
        """)
        
        self.sqlite_conn.commit()
        
    async def build_context(
        self,
        user_id: str,
        thread_id: str,
        persona_id: str,
        query: str,
        include_memory: bool = True,
        top_k: int = 3
    ) -> Dict:
        """Build conversation context with vector similarity search"""
        try:
            # Get session messages
            session = await self.load_session(user_id, thread_id)
            
            memories = []
            if include_memory:
                # Get query embedding
                query_embedding = await self._get_embedding(query)
                
                # Search vector store
                with MEMORY_OP_DURATION.time():
                    results = self.client.collection("user_memories").query(
                        query_embeddings=[query_embedding],
                        where={
                            "$and": [
                                {"user_id": user_id},
                                {"persona_id": persona_id}
                            ]
                        },
                        n_results=top_k
                    )
                    MEMORY_OPS.labels("search").inc()
                
                memories = [
                    json.loads(meta["memory"])
                    for meta in results["metadatas"][0]
                ]
                
            return {
                "messages": session["messages"],
                "memory": self._format_memories(memories)
            }
            
        except Exception as e:
            logger.error("Failed to build context", error=str(e))
            raise MemoryException("Context building failed") from e
            
    async def transfer_context(
        self,
        user_id: str,
        from_persona: str,
        to_persona: str,
        query: str
    ) -> List[Dict]:
        """Transfer relevant memories between personas"""
        try:
            # Get query embedding
            query_embedding = await self._get_embedding(query)
            
            # Search source persona memories
            with MEMORY_OP_DURATION.time():
                results = self.client.collection("user_memories").query(
                    query_embeddings=[query_embedding],
                    where={
                        "$and": [
                            {"user_id": user_id},
                            {"persona_id": from_persona}
                        ]
                    },
                    n_results=5
                )
                MEMORY_OPS.labels("search").inc()
            
            # Transfer relevant memories
            transferred = []
            for i, memory in enumerate(results["metadatas"][0]):
                memory_data = json.loads(memory["memory"])
                embedding = results["embeddings"][0][i]
                
                # Store for new persona
                event = await self.store_memory(
                    user_id=user_id,
                    thread_id=memory_data["thread_id"],
                    persona_id=to_persona,
                    text=memory_data["text"],
                    type="transferred",
                    salience=memory_data["salience"],
                    embedding=embedding
                )
                
                transferred.append(event)
                
            return transferred
            
        except Exception as e:
            logger.error("Failed to transfer context", error=str(e))
            raise MemoryException("Context transfer failed") from e
            
    async def store_memory(
        self,
        user_id: str,
        thread_id: str,
        persona_id: str,
        text: str,
        type: str,
        salience: float,
        embedding: Optional[List[float]] = None
    ) -> Dict:
        """Store vectorized memory with compression"""
        try:
            # Validate inputs
            if not user_id or not thread_id or not text:
                raise ValueError("Missing required fields")
                
            # Generate memory ID
            memory_id = xxhash.xxh64(
                f"{user_id}:{thread_id}:{text}".encode()
            ).hexdigest()
            
            # Get embedding if not provided
            if embedding is None:
                embedding = await self._get_embedding(text)
                
            # Validate embedding
            if len(embedding) != 1024:
                raise ValueError("Invalid embedding dimension")
                
            # Create memory event
            event = {
                "id": memory_id,
                "text": text,
                "type": type,
                "salience": salience,
                "created_at": datetime.utcnow().isoformat(),
                "thread_id": thread_id,
                "user_id": user_id,
                "persona_id": persona_id
            }
            
            # Compress text
            compressed_text = self.compressor.compress(text.encode())
            
            try:
                # Store in vector database
                with MEMORY_OP_DURATION.time():
                    self.client.collection("user_memories").add(
                        ids=[memory_id],
                        embeddings=[embedding],
                        metadatas=[{
                            "user_id": user_id,
                            "persona_id": persona_id,
                            "memory": json.dumps(event)
                        }],
                        documents=[compressed_text]
                    )
                    MEMORY_OPS.labels("store").inc()
                    
            except Exception as e:
                # Fallback to SQLite
                logger.warning("Vector store failed, using SQLite fallback", error=str(e))
                cursor = self.sqlite_conn.cursor()
                cursor.execute("""
                INSERT INTO memories (id, user_id, persona_id, content, embedding, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory_id,
                    user_id,
                    persona_id,
                    compressed_text,
                    np.array(embedding).tobytes(),
                    event["created_at"],
                    json.dumps(event)
                ))
                self.sqlite_conn.commit()
                
            # Check size limits
            await self._check_storage_limits()
            
            return event
            
        except Exception as e:
            logger.error("Failed to store memory", error=str(e))
            raise MemoryException("Memory storage failed") from e
            
    async def load_session(
        self,
        user_id: str,
        thread_id: str
    ) -> Dict:
        """Load conversation session"""
        try:
            if not user_id or not thread_id:
                raise ValueError("Missing user_id or thread_id")
                
            with MEMORY_OP_DURATION.time():
                collection = self.client.collection("user_memories")
                results = collection.get(
                    where={
                        "$and": [
                            {"user_id": user_id},
                            {"thread_id": thread_id}
                        ]
                    },
                    limit=100
                )
                MEMORY_OPS.labels("retrieve").inc()
                
            if not results["ids"]:
                return {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "messages": [],
                    "created_at": datetime.utcnow().isoformat()
                }
                
            # Sort by timestamp
            memories = []
            for meta in results["metadatas"]:
                memory = json.loads(meta["memory"])
                memories.append(memory)
                
            memories.sort(key=lambda x: x["created_at"])
            
            return {
                "thread_id": thread_id,
                "user_id": user_id,
                "messages": memories,
                "created_at": memories[0]["created_at"]
            }
            
        except Exception as e:
            logger.error("Failed to load session", error=str(e))
            raise MemoryException("Session loading failed") from e
            
    async def _get_embedding(self, text: str) -> List[float]:
        """Generate vector embedding with caching"""
        try:
            if not text:
                raise ValueError("Empty text")
                
            # Check cache
            cache_key = xxhash.xxh64(text.encode()).hexdigest()
            if cache_key in self.embedding_cache:
                CACHE_HITS.inc()
                return self.embedding_cache[cache_key]
                
            # Generate embedding
            with EMBEDDING_DURATION.time():
                embedding = self.embedding_model.encode(
                    text,
                    batch_size=self.embedding_batch_size
                ).tolist()
                
            # Update cache
            self.embedding_cache[cache_key] = embedding
            if len(self.embedding_cache) > self.embedding_cache_size:
                # Remove oldest entry
                self.embedding_cache.pop(next(iter(self.embedding_cache)))
                
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise MemoryException("Embedding generation failed") from e
            
    async def _check_storage_limits(self) -> None:
        """Verify and enforce storage limits"""
        total_size = 0
        
        # Check Chroma size
        for path in self.persist_dir.rglob('*'):
            if path.is_file():
                total_size += path.stat().st_size
                
        # Check SQLite size
        if self.sqlite_path.exists():
            total_size += self.sqlite_path.stat().st_size
            
        # Update metrics
        MEMORY_SIZE.labels("total").set(total_size)
        
        if total_size > self.max_size_bytes:
            logger.warning(
                "Storage size exceeds limit",
                current_size=total_size,
                limit=self.max_size_bytes
            )
            await self._cleanup_old_data()
            
    async def _cleanup_old_data(self) -> None:
        """Remove oldest data to maintain size limits"""
        try:
            # Get all collections
            for collection in self.client.list_collections():
                # Get count and sort by timestamp
                results = collection.get(
                    limit=1000,
                    where={},
                    include=["metadatas"]
                )
                
                if results["ids"]:
                    # Sort by timestamp and remove oldest
                    sorted_results = sorted(
                        zip(results["ids"], results["metadatas"]),
                        key=lambda x: json.loads(x[1]["memory"])["created_at"]
                    )
                    
                    # Remove oldest 20%
                    to_remove = sorted_results[:len(sorted_results)//5]
                    collection.delete(ids=[id for id, _ in to_remove])
                    
            # Vacuum SQLite
            if self.sqlite_conn:
                self.sqlite_conn.execute("VACUUM")
                
        except Exception as e:
            logger.error("Failed to cleanup old data", error=str(e))
            
    async def _create_backup(self) -> None:
        """Create timestamped backup"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"memory_store_{timestamp}"
        
        try:
            # Backup Chroma
            shutil.copytree(self.persist_dir, backup_path)
            
            # Backup SQLite
            if self.sqlite_path.exists():
                shutil.copy2(
                    self.sqlite_path,
                    backup_path / "fallback.db"
                )
                
            # Cleanup old backups (keep last 5)
            backups = sorted(self.backup_dir.glob("memory_store_*"))
            for backup in backups[:-5]:
                shutil.rmtree(backup)
                
        except Exception as e:
            logger.error("Failed to create backup", error=str(e))
            
    def cleanup(self) -> None:
        """Cleanup connections and resources"""
        try:
            if self.sqlite_conn:
                self.sqlite_conn.close()
                
            if self.client:
                self.client.reset()
                
            # Clear embedding cache
            self.embedding_cache.clear()
                
        except Exception as e:
            logger.error("Failed to cleanup", error=str(e))
            
    def _format_memories(self, memories: List[Dict]) -> List[str]:
        """Format memories for context"""
        return [f"- {m['text']}" for m in memories]