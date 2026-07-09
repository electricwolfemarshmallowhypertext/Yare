from __future__ import annotations

from fastapi import FastAPI, Depends, Header, HTTPException, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles
from typing import Optional, Dict, Any, Set, Callable
import structlog
import uvicorn
import os
import shutil
import json
import httpx
import asyncio
from pathlib import Path

from .config import settings
from .logging_config import setup_logging
from .monitoring import Monitoring
from .http_metrics import HttpMetricsMiddleware
from .security_headers import CSPNonceMiddleware
from .cache import MemoryCache
from .rate_limit import RateLimiter
from .persistence_factory import get_store as get_sync_store
from .security import ApiKeyAuth, Authorizer, audit_log
from .routes_orchestration import router as orchestration_router
from .routes_data import router as data_router
from .analytics import AnalyticsEngine
from .scheduler import AsyncScheduler
from .risk_engine import RiskEngine
from .api_keys_store import ApiKeyStore
from .persona_store import PersonaStore
from .status import snapshot as status_snapshot
from .metering import UsageMeter
from .org_context import get_org_id
from .geo_risk import GeoRisk
from .async_utils import maybe_await
from .ethics import PolicyEngine
from .watchdog import report as watchdog_report
from cli.yare import validate_workspace

logger = structlog.get_logger("memory.server")

# Optional async Postgres store
try:
    from .persistence_pg_async import AsyncPersistencePG
except Exception:
    AsyncPersistencePG = None  # type: ignore


class BodySizeLimitMiddleware:
    def __init__(self, app: FastAPI, max_body_size: int):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def limited_receive():
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"") or b""
                headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
                if "content-length" in headers:
                    try:
                        if int(headers["content-length"]) > self.max_body_size:
                            return {"type": "http.request", "body": b"", "more_body": False}
                    except Exception:
                        pass
                if len(body) > self.max_body_size:
                    return {"type": "http.request", "body": b"", "more_body": False}
                return message
            return message

        return await self.app(scope, limited_receive, send)


def _client_ip(request: Request, proxy_hops: int) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            idx = max(0, len(parts) - proxy_hops)
            return parts[idx]
    return request.client.host if request.client else "unknown"


def _load_plugins() -> Dict[str, Any]:
    try:
        p = os.path.join(os.getcwd(), "plugins.json")
        if os.path.isfile(p):
            raw = json.loads(open(p, "r", encoding="utf-8").read())
            return raw
    except Exception as e:
        logger.warning("plugins_load_failed", error=str(e))
    return {"geo": {"enabled": True}, "ethics": {"enabled": True}, "risk": {"enabled": True}}


def _load_latest_yare_receipt() -> Dict[str, Any]:
    receipts_dir = os.path.join(os.getcwd(), "receipts")
    if not os.path.isdir(receipts_dir):
        return {}
    files = sorted([f for f in os.listdir(receipts_dir) if f.endswith(".jsonl")], reverse=True)
    for name in files:
        path = os.path.join(receipts_dir, name)
        try:
            lines = [line.strip() for line in open(path, "r", encoding="utf-8").read().splitlines() if line.strip()]
            if not lines:
                continue
            return json.loads(lines[-1])
        except Exception:
            continue
    return {}


def create_app() -> FastAPI:
    setup_logging(settings.LOG_LEVEL)
    app = FastAPI(title="Memory Service", version="v1")

    Monitoring(metrics_port=settings.METRICS_PORT, otlp_endpoint=settings.OTLP_ENDPOINT).start()

    app.add_middleware(HttpMetricsMiddleware)
    app.add_middleware(CSPNonceMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.TRUSTED_HOSTS and settings.TRUSTED_HOSTS != "*":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[h.strip() for h in settings.TRUSTED_HOSTS.split(",")])
    app.add_middleware(BodySizeLimitMiddleware, max_body_size=settings.REQUEST_MAX_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ALLOWED_ORIGINS == "*" else [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared services (created once at startup)
    app.state.cache = MemoryCache(redis_url=settings.REDIS_URL, embedding_max_entries=settings.EMBEDDING_LRU_MAX)
    app.state.rate_limiter = RateLimiter(redis_url=settings.REDIS_URL)

    # Data store: optionally async Postgres, else sync (SQLite or PG sync)
    db_url = settings.DATABASE_URL or f"sqlite:///{os.path.abspath(settings.SQLITE_PATH)}"
    app.state.store_async = False
    if settings.ASYNC_DB and AsyncPersistencePG and db_url.startswith(("postgresql://", "postgresql+asyncpg://")):
        app.state.store = AsyncPersistencePG(db_url=db_url)
        app.state.store_async = True
    else:
        app.state.store = get_sync_store(settings.SQLITE_PATH)

    # Keys/personas/metering (use DATABASE_URL for centralization)
    app.state.keys = ApiKeyStore(db_url=db_url)
    app.state.personas = PersonaStore(db_url=db_url)
    app.state.meter = UsageMeter(db_url=db_url)

    # Scheduler
    app.state.scheduler = AsyncScheduler()

    # Risk engine (pluggable detectors already registered in module)
    app.state.risk_engine = RiskEngine(store=app.state.store)

    # Plugins manifest + optional components
    app.state.plugins = _load_plugins()
    if app.state.plugins.get("geo", {}).get("enabled", True):
        app.state.geo = GeoRisk(db_path=os.getenv("MAXMIND_DB_PATH"))
    else:
        app.state.geo = GeoRisk(db_path=None)

    # Security (inline keys still supported)
    keys_to_roles = settings.parse_api_keys()
    app.state.auth = ApiKeyAuth(keys_to_roles=keys_to_roles)
    app.state.authorizer = Authorizer(role_permissions={"admin": {"*"}, "reader": {"mem.read"}, "writer": {"mem.read", "mem.write"}})

    # Static mini dashboard/admin
    static_dir = os.path.join(os.getcwd(), "public")
    if os.path.isdir(static_dir):
        app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")
        app.mount("/admin", StaticFiles(directory=static_dir, html=True), name="admin")

    # Startup/Shutdown hooks (cold-start preload + graceful close)
    @app.on_event("startup")
    async def _startup():
        # Initialize async store schema if needed
        if app.state.store_async:
            await app.state.store.init()
        # Preload: parse rate plans, instantiate policy engine, warm metrics snapshot once
        app.state.rate_plans_cache = json.loads(settings.RATE_PLANS) if settings.RATE_PLANS else {}
        ethics_enabled = app.state.plugins.get("ethics", {}).get("enabled", True)
        app.state.policy = PolicyEngine(rules_path=os.getenv("ETHICS_RULES_PATH")) if ethics_enabled else None
        _ = status_snapshot()  # touch registry once
        # Start analytics periodically (deferred run inside task)
        async def _run_analytics_forever():
            app.state.analytics = AnalyticsEngine(store=app.state.store, db_url=db_url, interval_seconds=900)
            while True:
                try:
                    await app.state.analytics.run_once()
                except Exception as e:
                    logger.warning("analytics_run_failed", error=str(e))
                await asyncio.sleep(900)

        app.state.scheduler.add_task("analytics", _run_analytics_forever)

        # Memory watchdog every 5 minutes
        async def _watchdog():
            while True:
                try:
                    cache_stats = getattr(app.state.cache, "stats", None)
                    watchdog_report(cache_stats() if callable(cache_stats) else {})
                except Exception as e:
                    logger.warning("watchdog_failed", error=str(e))
                await asyncio.sleep(300)

        app.state.scheduler.add_task("watchdog", _watchdog)
        app.state.scheduler.start()

    @app.on_event("shutdown")
    async def _shutdown():
        # Stop scheduler tasks
        try:
            await app.state.scheduler.stop()
        except Exception:
            pass
        # Close Redis
        try:
            app.state.cache.redis.close()
        except Exception:
            pass
        # Dispose DB engine (async engine closes via .engine.dispose())
        try:
            if app.state.store_async:
                await app.state.store.engine.dispose()  # type: ignore
        except Exception:
            pass

    # --------------- Dependencies ---------------

    async def get_api_info(authorization: Optional[str] = Header(None, alias="Authorization")) -> Dict[str, Any]:
        info: Dict[str, Any] = {}
        if not authorization or not authorization.startswith("Bearer "):
            return info
        api_key = authorization.replace("Bearer ", "", 1).strip()
        dk = app.state.keys.get_roles_and_tier_by_plain(api_key)
        if dk:
            info = {"roles": dk["roles"], "tier": dk["tier"], "api_key": api_key, "key_hash": dk["key_hash"], "org_id": dk.get("org_id")}
            return info
        roles = app.state.auth.authenticate(api_key)
        if roles:
            info = {"roles": roles, "tier": None, "api_key": api_key, "key_hash": None}
        return info

    def require_permission(permission: str) -> Callable:
        async def dep(info: Dict[str, Any] = Depends(get_api_info)) -> Dict[str, Any]:
            roles: Set[str] = set(info.get("roles") or [])
            if not roles or not app.state.authorizer.is_allowed(roles, permission):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
            return info
        return dep

    async def rate_limit_dep(request: Request, info: Dict[str, Any] = Depends(get_api_info)):
        route_path = request.url.path
        if info.get("key_hash"):
            try:
                app.state.meter.record_call(info["key_hash"], route_path)
            except Exception as e:
                logger.warning("usage_meter_failed", error=str(e))
        if info.get("api_key"):
            plan = settings.rate_plan_for(info.get("tier"))
            allowed = await app.state.rate_limiter.allow(
                key=f"key:{info['api_key'][:12]}",
                limit=plan["limit"],
                window_seconds=plan["window"],
            )
        else:
            ip = _client_ip(request, settings.PROXY_COUNT)
            allowed = await app.state.rate_limiter.allow(
                key=f"ip:{ip}",
                limit=settings.RATE_LIMIT_MAX,
                window_seconds=settings.RATE_LIMIT_WINDOW_SEC,
            )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limited")

    # --------------- Routes ---------------

    @app.get("/health")
    async def health(request: Request):
        ip = _client_ip(request, settings.PROXY_COUNT)
        geo = app.state.geo.score_ip(ip)
        # Redis
        try:
            app.state.cache.redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
        # Store
        try:
            await maybe_await(app.state.store.query(limit=1))
            store_ok = True
        except Exception:
            store_ok = False
        return {
            "status": "ok" if (redis_ok and store_ok) else "degraded",
            "components": {"redis": "ok" if redis_ok else "error", "store": "ok" if store_ok else "error"},
            "metrics_port": settings.METRICS_PORT,
            "client": geo,
        }

    @app.get("/status")
    async def status_public():
        return {"status": "ok", "metrics": status_snapshot()}

    @app.get("/yare/results")
    async def yare_results():
        resolved_path = os.path.join(os.getcwd(), ".yare", "resolved-context.json")
        resolved: Dict[str, Any] = {}
        if os.path.isfile(resolved_path):
            try:
                resolved = json.loads(open(resolved_path, "r", encoding="utf-8").read())
            except Exception:
                resolved = {}
        latest_receipt = _load_latest_yare_receipt()
        selected = resolved.get("selected", []) if isinstance(resolved, dict) else []
        excluded = resolved.get("excluded", []) if isinstance(resolved, dict) else []
        why_selected = [{"path": item.get("path"), "why": item.get("reason")} for item in selected]
        why_excluded = [{"path": item.get("path"), "why": item.get("reason")} for item in excluded]
        validation = latest_receipt.get("validation") if latest_receipt else (resolved.get("validation", {}) if isinstance(resolved, dict) else {})
        validation_summary = validate_workspace(Path(os.getcwd()))
        policy_warnings = []
        if isinstance(validation, dict):
            policy_warnings.extend(validation.get("errors", []))
            policy_warnings.extend(validation.get("warnings", []))
        return {
            "task": resolved.get("task") if isinstance(resolved, dict) else None,
            "selected_context": selected,
            "why_selected": why_selected,
            "excluded_context": excluded,
            "why_excluded": why_excluded,
            "context_bundle_hash": resolved.get("context_bundle_hash") if isinstance(resolved, dict) else None,
            "policy_warnings": policy_warnings,
            "receipt_hash": latest_receipt.get("receipt_hash") if latest_receipt else None,
            "git_commit": latest_receipt.get("git_commit") if latest_receipt else None,
            "git_dirty": latest_receipt.get("git_dirty") if latest_receipt else None,
            "changed_files": latest_receipt.get("changed_files", []) if latest_receipt else [],
            "untracked_files": latest_receipt.get("untracked_files", []) if latest_receipt else [],
            "file_hashes": latest_receipt.get("file_hashes", {}) if latest_receipt else {},
            "validation_status": validation,
            "validation_summary": validation_summary,
            "latest_receipt": latest_receipt,
            "latest_resolved_context": resolved,
        }

    @app.get("/system/diagnostics")
    async def diagnostics():
        # Redis
        try:
            app.state.cache.redis.ping()
            redis = {"status": "ok"}
        except Exception as e:
            redis = {"status": "error", "error": str(e)}
        # DB
        try:
            await maybe_await(app.state.store.query(limit=1))
            db = {"status": "ok", "async": bool(app.state.store_async)}
        except Exception as e:
            db = {"status": "error", "error": str(e)}
        # Disk
        try:
            du = shutil.disk_usage("/")
            disk = {"status": "ok", "total": du.total, "used": du.used, "free": du.free}
        except Exception as e:
            disk = {"status": "error", "error": str(e)}
        return {"redis": redis, "db": db, "disk": disk, "version": os.getenv("APP_VERSION", "dev")}

    # API key self-service
    @app.post("/register")
    async def register_key(payload: Dict[str, Any], background: BackgroundTasks, registration_token: Optional[str] = Header(None, alias="X-Registration-Token")):
        if not settings.REGISTRATION_TOKEN or registration_token != settings.REGISTRATION_TOKEN:
            raise HTTPException(status_code=403, detail="Registration disabled or invalid token")
        tier = str(payload.get("tier") or "basic")
        roles = set(payload.get("roles") or ["reader"])
        org_id = payload.get("org_id")
        doc = app.state.keys.create_key(roles=roles, tier=tier, org_id=org_id)
        audit_log("api_key_issued", tier=tier, roles=sorted(list(roles)), org_id=org_id)
        # Optional webhook
        if settings.REGISTRATION_WEBHOOK_URL:
            data = {"event": "key_issued", "tier": doc["tier"], "org_id": doc["org_id"], "roles": doc["roles"], "key_hash": doc["key_hash"]}
            async def _notify():
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(settings.REGISTRATION_WEBHOOK_URL, json=data)
                except Exception as e:
                    logger.warning("registration_webhook_failed", error=str(e))
            background.add_task(_notify)
        return {"api_key": doc["api_key"], "tier": doc["tier"], "roles": doc["roles"], "org_id": doc["org_id"]}

    # Admin: list, revoke, upgrade, usage
    @app.get("/keys", dependencies=[Depends(rate_limit_dep)])
    async def list_keys_admin(info=Depends(require_permission("admin"))):
        return app.state.keys.list_keys(include_revoked=True)

    @app.delete("/keys/{key_hash}", dependencies=[Depends(rate_limit_dep)])
    async def revoke_key_admin(key_hash: str, info=Depends(require_permission("admin"))):
        ok = app.state.keys.revoke_key(key_hash)
        if not ok:
            raise HTTPException(status_code=404, detail="Not found")
        audit_log("api_key_revoked", key_hash=key_hash)
        return {"status": "revoked", "key_hash": key_hash}

    @app.post("/keys/{key_hash}/upgrade", dependencies=[Depends(rate_limit_dep)])
    async def upgrade_key_admin(key_hash: str, payload: Dict[str, Any], info=Depends(require_permission("admin"))):
        new_tier = str(payload.get("tier") or "").strip()
        if not new_tier:
            raise HTTPException(status_code=400, detail="Missing tier")
        ok = app.state.keys.upgrade_tier(key_hash, new_tier)
        if not ok:
            raise HTTPException(status_code=404, detail="Not found")
        audit_log("api_key_upgraded", key_hash=key_hash, tier=new_tier)
        return {"status": "upgraded", "key_hash": key_hash, "tier": new_tier}

    # Memories (protected)
    @app.post("/memories", dependencies=[Depends(rate_limit_dep)])
    async def store_memory(payload: Dict[str, Any], info=Depends(require_permission("mem.write")), org_id: Optional[str] = Depends(get_org_id)):
        required = ["id", "text", "type", "salience", "created_at", "thread_id", "user_id", "persona_id"]
        missing = [f for f in required if f not in payload]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")
        if org_id:
            payload["org_id"] = org_id
        await maybe_await(app.state.store.upsert(payload))
        audit_log("memory_upsert", memory_id=payload["id"], user=payload.get("user_id"), org_id=payload.get("org_id"))
        return {"status": "stored", "id": payload["id"]}

    @app.get("/memories/{memory_id}", dependencies=[Depends(rate_limit_dep)])
    async def get_memory(memory_id: str, info=Depends(require_permission("mem.read")), org_id: Optional[str] = Depends(get_org_id)):
        mem = await maybe_await(app.state.store.get(memory_id))
        if not mem:
            raise HTTPException(status_code=404, detail="Not found")
        if org_id and mem.get("org_id") not in (None, org_id):
            raise HTTPException(status_code=404, detail="Not found")
        return mem

    # Personas (protected)
    @app.post("/persona/import", dependencies=[Depends(rate_limit_dep)])
    async def persona_import(payload: Dict[str, Any], info=Depends(require_permission("mem.write")), org_id: Optional[str] = Depends(get_org_id)):
        res = app.state.personas.import_persona(payload, org_id)
        return res

    @app.get("/persona/export/{persona_id}", dependencies=[Depends(rate_limit_dep)])
    async def persona_export(persona_id: str, info=Depends(require_permission("mem.read")), org_id: Optional[str] = Depends(get_org_id)):
        doc = app.state.personas.export_persona(persona_id, org_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        return doc

    @app.get("/persona", dependencies=[Depends(rate_limit_dep)])
    async def persona_list(info=Depends(require_permission("mem.read")), org_id: Optional[str] = Depends(get_org_id)):
        return {"personas": app.state.personas.list_personas(org_id)}

    @app.get("/risks", dependencies=[Depends(rate_limit_dep)])
    async def list_risks(info=Depends(require_permission("mem.read")), org_id: Optional[str] = Depends(get_org_id)):
        risks = app.state.risk_engine.compute_risks()
        if org_id:
            risks = [r for r in risks if (not r.get("scope")) or r["scope"].get("org_id") in (None, org_id)]
        return {"risks": risks}

    # Data routes
    app.include_router(data_router)

    # Orchestration routes
    app.include_router(orchestration_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.memory.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENV == "development",
        workers=settings.WORKERS,
        timeout_keep_alive=settings.KEEPALIVE_TIMEOUT,
    )
