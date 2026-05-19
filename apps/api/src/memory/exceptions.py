"""
Memory System Exceptions
Created: 2025-11-02 19:53:06
Author: electricwolfemarshmallowhypertext
"""

from typing import Optional, Any
import structlog

logger = structlog.get_logger("sticky.memory.exceptions")

class MemoryException(Exception):
    """Base exception for memory system errors"""
    
    def __init__(
        self,
        message: str,
        code: str = "MEMORY_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        
        # Log error
        logger.error(self.message,
            code=self.code,
            status_code=self.status_code,
            details=self.details
        )
        
        super().__init__(self.message)

class MemoryInitError(MemoryException):
    """Raised when memory system fails to initialize"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_INIT_ERROR",
            status_code=500,
            details=details
        )

class MemoryStorageError(MemoryException):
    """Raised when storing memories fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_STORAGE_ERROR", 
            status_code=500,
            details=details
        )

class MemoryRetrievalError(MemoryException):
    """Raised when retrieving memories fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_RETRIEVAL_ERROR",
            status_code=500,
            details=details
        )

class MemoryLimitError(MemoryException):
    """Raised when memory limits are exceeded"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_LIMIT_ERROR",
            status_code=413,
            details=details
        )

class MemoryValidationError(MemoryException):
    """Raised when memory validation fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_VALIDATION_ERROR",
            status_code=400,
            details=details
        )

class MemoryBackupError(MemoryException):
    """Raised when memory backup/restore fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_BACKUP_ERROR",
            status_code=500,
            details=details
        )

class MemoryEmbeddingError(MemoryException):
    """Raised when embedding generation fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_EMBEDDING_ERROR",
            status_code=500,
            details=details
        )

class MemoryCompressionError(MemoryException):
    """Raised when memory compression/decompression fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_COMPRESSION_ERROR",
            status_code=500,
            details=details
        )

class MemoryCleanupError(MemoryException):
    """Raised when memory cleanup fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_CLEANUP_ERROR",
            status_code=500,
            details=details
        )

class MemoryTransferError(MemoryException):
    """Raised when memory transfer between personas fails"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="MEMORY_TRANSFER_ERROR",
            status_code=500,
            details=details
        )