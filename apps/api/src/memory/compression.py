"""
Zstandard compression with optional dictionary training and correct decompression.
"""

import zstandard as zstd
from typing import Any, Dict, Optional, List
import json
import base64
import xxhash
import structlog

logger = structlog.get_logger("memory.compression")


class MemoryCompression:
    def __init__(
        self,
        level: int = 3,
        dict_size: int = 128 * 1024,
        min_size: int = 1024,
        enable_dict: bool = True,
    ):
        self.level = level
        self.dict_size = dict_size
        self.min_size = min_size
        self.enable_dict = enable_dict

        self.compressor = zstd.ZstdCompressor(level=self.level, write_checksum=True)
        self.dict_trained = False
        self.compression_dict: Optional[zstd.ZstdCompressionDict] = None
        self.dict_compressor: Optional[zstd.ZstdCompressor] = None
        self.training_data: List[bytes] = []

    def compress_memory(self, memory: Dict[str, Any], use_dict: bool = True) -> Dict[str, Any]:
        try:
            if self.enable_dict and use_dict:
                self._update_training_data(memory)

            memory_data = json.dumps(memory, separators=(",", ":")).encode("utf-8")
            if len(memory_data) < self.min_size:
                return {**memory, "_compressed": False, "_size": len(memory_data)}

            if self.enable_dict and use_dict and self.dict_compressor:
                compressed = self.dict_compressor.compress(memory_data)
                used_dict = True
            else:
                compressed = self.compressor.compress(memory_data)
                used_dict = False

            encoded = base64.b64encode(compressed).decode("ascii")
            ratio = len(compressed) / len(memory_data)

            return {
                "id": memory.get("id"),
                "compressed_data": encoded,
                "_compressed": True,
                "_size": len(compressed),
                "_ratio": ratio,
                "_checksum": xxhash.xxh64(memory_data).hexdigest(),
                "_dict": used_dict,
            }
        except Exception as e:
            logger.error("compression_failed", memory_id=memory.get("id"), error=str(e))
            raise

    def decompress_memory(self, compressed_memory: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not compressed_memory.get("_compressed", False):
                return compressed_memory

            compressed = base64.b64decode(compressed_memory["compressed_data"])

            if compressed_memory.get("_dict") and self.enable_dict and self.compression_dict:
                decompressor = zstd.ZstdDecompressor(dict_data=self.compression_dict)
            else:
                decompressor = zstd.ZstdDecompressor()

            decompressed = decompressor.decompress(compressed)
            memory = json.loads(decompressed.decode("utf-8"))

            if compressed_memory.get("_checksum"):
                current_checksum = xxhash.xxh64(json.dumps(memory, separators=(",", ":")).encode("utf-8")).hexdigest()
                if current_checksum != compressed_memory["_checksum"]:
                    raise ValueError("Checksum verification failed")

            return memory
        except Exception as e:
            logger.error("decompression_failed", memory_id=compressed_memory.get("id"), error=str(e))
            raise

    def _update_training_data(self, memory: Dict[str, Any]) -> None:
        try:
            if not self.dict_trained:
                self.training_data.append(json.dumps(memory, separators=(",", ":")).encode("utf-8"))
                if len(self.training_data) >= 100:
                    self._train_dictionary()
        except Exception as e:
            logger.warning("train_data_update_failed", error=str(e))

    def _train_dictionary(self) -> None:
        try:
            if self.training_data:
                self.compression_dict = zstd.train_dictionary(self.dict_size, self.training_data)
                self.dict_compressor = zstd.ZstdCompressor(
                    level=self.level, dict_data=self.compression_dict, write_checksum=True
                )
                self.dict_trained = True
                self.training_data = []
                logger.info("compression_dict_trained", dict_size=len(self.compression_dict.as_bytes()))
        except Exception as e:
            logger.warning("dict_training_failed", error=str(e))

    def save_dictionary(self, path: str) -> None:
        try:
            if self.compression_dict:
                with open(path, "wb") as f:
                    f.write(self.compression_dict.as_bytes())
                logger.info("compression_dict_saved", path=path)
        except Exception as e:
            logger.warning("dict_save_failed", path=path, error=str(e))

    def load_dictionary(self, path: str) -> None:
        try:
            with open(path, "rb") as f:
                dict_data = f.read()
            self.compression_dict = zstd.ZstdCompressionDict(dict_data)
            self.dict_compressor = zstd.ZstdCompressor(
                level=self.level, dict_data=self.compression_dict, write_checksum=True
            )
            self.dict_trained = True
            logger.info("compression_dict_loaded", path=path, dict_size=len(dict_data))
        except Exception as e:
            logger.error("dict_load_failed", path=path, error=str(e))
            raise