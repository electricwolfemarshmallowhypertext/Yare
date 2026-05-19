from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Set
import os
import json
from pathlib import Path


def getenv_file_first(name: str, default: Optional[str] = None) -> Optional[str]:
    file_key = f"{name}_FILE"
    if file_key in os.environ and os.environ[file_key]:
        p = Path(os.environ[file_key])
        if p.exists():
            return p.read_text().strip()
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    ENV: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    REQUEST_MAX_BYTES: int = 10 * 1024 * 1024
    READ_TIMEOUT: int = 30
    WRITE_TIMEOUT: int = 30
    KEEPALIVE_TIMEOUT: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"

    SQLITE_PATH: str = "data/memory/fallback.db"

    METRICS_PORT: int = 9090
    OTLP_ENDPOINT: Optional[str] = None

    ENCRYPTION_KEY_PATH: Optional[str] = None

    EMBEDDING_LRU_MAX: int = 10_000

    RATE_LIMIT_WINDOW_SEC: int = 60
    RATE_LIMIT_MAX: int = 100

    RATE_PLANS: str = json.dumps(
        {"basic": {"limit": 60, "window": 60}, "pro": {"limit": 600, "window": 60}, "partner": {"limit": 3000, "window": 60}}
    )

    API_KEYS: str = ""

    REGISTRATION_TOKEN: Optional[str] = None
    REGISTRATION_WEBHOOK_URL: Optional[str] = None

    ALLOWED_ORIGINS: str = "*"
    TRUSTED_HOSTS: str = "*"
    PROXY_COUNT: int = 1

    DATABASE_URL: Optional[str] = None
    ASYNC_DB: bool = False  # Use SQLAlchemy async engine for Postgres

    def _get_bool(self, name: str, default: bool) -> bool:
        v = os.getenv(name)
        if v is None:
            return default
        return v.lower() in ("1", "true", "yes", "on")

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls(
            ENV=os.getenv("ENV", cls.ENV),
            DEBUG=cls._get_bool(cls, "DEBUG", cls.DEBUG),
            LOG_LEVEL=os.getenv("LOG_LEVEL", cls.LOG_LEVEL),
            HOST=os.getenv("HOST", cls.HOST),
            PORT=int(os.getenv("PORT", str(cls.PORT))),
            WORKERS=int(os.getenv("WORKERS", str(cls.WORKERS))),
            REQUEST_MAX_BYTES=int(os.getenv("REQUEST_MAX_BYTES", str(cls.REQUEST_MAX_BYTES))),
            READ_TIMEOUT=int(os.getenv("READ_TIMEOUT", str(cls.READ_TIMEOUT))),
            WRITE_TIMEOUT=int(os.getenv("WRITE_TIMEOUT", str(cls.WRITE_TIMEOUT))),
            KEEPALIVE_TIMEOUT=int(os.getenv("KEEPALIVE_TIMEOUT", str(cls.KEEPALIVE_TIMEOUT))),
            REDIS_URL=os.getenv("REDIS_URL", cls.REDIS_URL),
            SQLITE_PATH=os.getenv("SQLITE_PATH", cls.SQLITE_PATH),
            METRICS_PORT=int(os.getenv("METRICS_PORT", str(cls.METRICS_PORT))),
            OTLP_ENDPOINT=os.getenv("OTLP_ENDPOINT", cls.OTLP_ENDPOINT),
            ENCRYPTION_KEY_PATH=os.getenv("ENCRYPTION_KEY_PATH", cls.ENCRYPTION_KEY_PATH) or os.getenv("FERNET_KEY_PATH"),
            EMBEDDING_LRU_MAX=int(os.getenv("EMBEDDING_LRU_MAX", str(cls.EMBEDDING_LRU_MAX))),
            RATE_LIMIT_WINDOW_SEC=int(os.getenv("RATE_LIMIT_WINDOW_SEC", str(cls.RATE_LIMIT_WINDOW_SEC))),
            RATE_LIMIT_MAX=int(os.getenv("RATE_LIMIT_MAX", str(cls.RATE_LIMIT_MAX))),
            RATE_PLANS=os.getenv("RATE_PLANS", cls.RATE_PLANS),
            API_KEYS=getenv_file_first("API_KEYS", cls.API_KEYS),
            REGISTRATION_TOKEN=getenv_file_first("REGISTRATION_TOKEN", cls.REGISTRATION_TOKEN),
            REGISTRATION_WEBHOOK_URL=os.getenv("REGISTRATION_WEBHOOK_URL"),
            ALLOWED_ORIGINS=os.getenv("ALLOWED_ORIGINS", cls.ALLOWED_ORIGINS),
            TRUSTED_HOSTS=os.getenv("TRUSTED_HOSTS", cls.TRUSTED_HOSTS),
            PROXY_COUNT=int(os.getenv("PROXY_COUNT", str(cls.PROXY_COUNT))),
            DATABASE_URL=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"),
            ASYNC_DB=cls._get_bool(cls, "ASYNC_DB", cls.ASYNC_DB),
        )

        # Ensure dirs
        sqlite_parent = Path(s.SQLITE_PATH).parent
        if str(sqlite_parent):
            sqlite_parent.mkdir(parents=True, exist_ok=True)
        if s.ENCRYPTION_KEY_PATH:
            key_parent = Path(s.ENCRYPTION_KEY_PATH).parent
            if str(key_parent):
                key_parent.mkdir(parents=True, exist_ok=True)
        return s

    def parse_api_keys(self) -> Dict[str, Set[str]]:
        from .security import ApiKeyAuth
        mapping: Dict[str, Set[str]] = {}
        if not self.API_KEYS:
            return mapping
        entries = [x.strip() for x in self.API_KEYS.split(",") if x.strip()]
        for e in entries:
            if ":" not in e:
                continue
            plain_key, roles = e.split(":", 1)
            role_set: Set[str] = set(r.strip() for r in roles.split("|") if r.strip())
            hashed = ApiKeyAuth.hash_key(plain_key)
            mapping[hashed] = role_set
        return mapping

    def rate_plan_for(self, tier: Optional[str]) -> Dict[str, int]:
        try:
            plans = json.loads(self.RATE_PLANS)
            if tier and tier in plans:
                p = plans[tier]
                return {"limit": int(p["limit"]), "window": int(p["window"])}
        except Exception:
            pass
        return {"limit": self.RATE_LIMIT_MAX, "window": self.RATE_LIMIT_WINDOW_SEC}


settings = Settings.from_env()