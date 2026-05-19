"""
Fernet-based content encryption with safe serialization.
- No eval()
- Stable key save/load
- Optional password-derived key (PBKDF2-HMAC-SHA256) with user-supplied salt
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import base64
import json
import os

import structlog
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = structlog.get_logger("memory.encryption")


class MemoryEncryption:
    def __init__(
        self,
        key: Optional[bytes] = None,
        *,
        password: Optional[str] = None,
        salt: Optional[bytes] = None,
        kdf_iterations: int = 200_000,
    ) -> None:
        if key and password:
            raise ValueError("Provide either key or password, not both")

        self._salt = salt
        self._iterations = kdf_iterations

        if key is not None:
            if not isinstance(key, (bytes, bytearray)):
                raise ValueError("key must be bytes")
            self._key = bytes(key)
        elif password is not None:
            if not salt:
                raise ValueError("salt is required when using password")
            self._key = self._derive_key(password.encode("utf-8"), salt, kdf_iterations)
        else:
            self._key = Fernet.generate_key()

        self._fernet = Fernet(self._key)

    @staticmethod
    def _derive_key(password_bytes: bytes, salt: bytes, iterations: int) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return base64.urlsafe_b64encode(kdf.derive(password_bytes))

    @property
    def key(self) -> bytes:
        return self._key

    def save_key(self, path: str) -> None:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self._key)
        os.chmod(path, 0o600)

    @classmethod
    def load_key(cls, path: str) -> "MemoryEncryption":
        with open(path, "rb") as f:
            key = f.read().strip()
        return cls(key=key)

    def encrypt_memory(self, memory: Dict[str, Any], include_metadata: bool = True) -> Dict[str, Any]:
        try:
            out: Dict[str, Any] = {
                "id": memory["id"],
                "type": memory.get("type"),
                "salience": memory.get("salience"),
                "created_at": memory.get("created_at"),
                "thread_id": memory.get("thread_id"),
                "user_id": memory.get("user_id"),
                "persona_id": memory.get("persona_id"),
            }

            enc_text = self._fernet.encrypt(memory["text"].encode("utf-8"))
            out["text"] = base64.b64encode(enc_text).decode("ascii")

            if "embedding" in memory and memory["embedding"] is not None:
                enc_vec = self._fernet.encrypt(json.dumps(memory["embedding"]).encode("utf-8"))
                out["embedding"] = base64.b64encode(enc_vec).decode("ascii")

            if include_metadata and "metadata" in memory and memory["metadata"] is not None:
                enc_meta = self._fernet.encrypt(json.dumps(memory["metadata"]).encode("utf-8"))
                out["metadata"] = base64.b64encode(enc_meta).decode("ascii")

            return out
        except Exception as e:
            logger.error("encrypt_failed", memory_id=memory.get("id"), error=str(e))
            raise

    def decrypt_memory(self, encrypted: Dict[str, Any], include_metadata: bool = True) -> Dict[str, Any]:
        try:
            out: Dict[str, Any] = {
                "id": encrypted["id"],
                "type": encrypted.get("type"),
                "salience": encrypted.get("salience"),
                "created_at": encrypted.get("created_at"),
                "thread_id": encrypted.get("thread_id"),
                "user_id": encrypted.get("user_id"),
                "persona_id": encrypted.get("persona_id"),
            }

            ct = base64.b64decode(encrypted["text"])
            out["text"] = self._fernet.decrypt(ct).decode("utf-8")

            if "embedding" in encrypted:
                ct_vec = base64.b64decode(encrypted["embedding"])
                out["embedding"] = json.loads(self._fernet.decrypt(ct_vec).decode("utf-8"))

            if include_metadata and "metadata" in encrypted:
                ct_meta = base64.b64decode(encrypted["metadata"])
                out["metadata"] = json.loads(self._fernet.decrypt(ct_meta).decode("utf-8"))

            return out
        except InvalidToken:
            logger.warning("decrypt_invalid_token", memory_id=encrypted.get("id"))
            raise
        except Exception as e:
            logger.error("decrypt_failed", memory_id=encrypted.get("id"), error=str(e))
            raise

    def rotate_key(self, new_key: Optional[bytes] = None) -> bytes:
        old = self._key
        self._key = new_key or Fernet.generate_key()
        self._fernet = Fernet(self._key)
        logger.info("encryption_key_rotated")
        return old