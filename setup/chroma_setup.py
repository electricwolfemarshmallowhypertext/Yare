"""
Vector Database Setup and Configuration
Created: 2025-11-02 19:39:13
Author: electricwolfemarshmallowhypertext
"""

import os
from pathlib import Path
import shutil
import logging
from typing import Optional, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import sqlite3
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ChromaSetup:
    def __init__(
        self,
        persist_dir: str = "memory_store",
        sqlite_fallback_path: str = "memory_store/fallback.db",
        max_size_mb: int = 5,
        backup_dir: str = "memory_store/backups",
        env: str = "production"
    ):
        self.persist_dir = Path(persist_dir)
        self.sqlite_path = Path(sqlite_fallback_path)
        self.backup_dir = Path(backup_dir)
        self.max_size_mb = max_size_mb
        self.env = env
        self.client = None
        self.sqlite_conn = None
        
    def initialize(self) -> chromadb.Client:
        """Initialize vector store with fallback and monitoring"""
        try:
            # Create directories
            self.persist_dir.mkdir(exist_ok=True, parents=True)
            self.backup_dir.mkdir(exist_ok=True, parents=True)
            
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
            self._setup_collections(sentence_transformer_ef)
            
            # Initialize SQLite fallback
            self._setup_sqlite_fallback()
            
            # Verify size limits
            self._check_storage_limits()
            
            # Initial backup
            self._create_backup()
            
            return self.client
            
        except Exception as e:
            logger.error(f"Failed to initialize Chroma: {str(e)}")
            raise
            
    def _setup_collections(self, embedding_fn: Any) -> None:
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
                
    def _setup_sqlite_fallback(self) -> None:
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
        
        self.sqlite_conn.commit()
        
    def _check_storage_limits(self) -> None:
        """Verify and enforce storage limits"""
        total_size = 0
        
        # Check Chroma size
        for path in self.persist_dir.rglob('*'):
            if path.is_file():
                total_size += path.stat().st_size
                
        # Check SQLite size
        if self.sqlite_path.exists():
            total_size += self.sqlite_path.stat().st_size
            
        total_size_mb = total_size / (1024 * 1024)
        
        if total_size_mb > self.max_size_mb:
            logger.warning(f"Storage size ({total_size_mb:.2f}MB) exceeds limit ({self.max_size_mb}MB)")
            self._cleanup_old_data()
            
    def _cleanup_old_data(self) -> None:
        """Remove oldest data to maintain size limits"""
        try:
            # Get all collections
            for collection in self.client.list_collections():
                # Get count and sort by timestamp
                results = collection.get(
                    limit=1000,
                    where={},
                    include=["metadatas", "documents"]
                )
                
                if results["ids"]:
                    # Sort by timestamp and remove oldest
                    sorted_results = sorted(
                        zip(results["ids"], results["metadatas"]),
                        key=lambda x: x[1].get("created_at", "")
                    )
                    
                    # Remove oldest 20%
                    to_remove = sorted_results[:len(sorted_results)//5]
                    collection.delete(ids=[id for id, _ in to_remove])
                    
            # Vacuum SQLite
            if self.sqlite_conn:
                self.sqlite_conn.execute("VACUUM")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {str(e)}")
            
    def _create_backup(self) -> None:
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
            logger.error(f"Failed to create backup: {str(e)}")
            
    def cleanup(self) -> None:
        """Cleanup connections and resources"""
        try:
            if self.sqlite_conn:
                self.sqlite_conn.close()
                
            if self.client:
                self.client.reset()
                
        except Exception as e:
            logger.error(f"Failed to cleanup: {str(e)}")