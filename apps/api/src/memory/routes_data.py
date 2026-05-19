from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import Dict, Any, Optional, Iterable
import json
import hashlib

router = APIRouter(prefix="/data", tags=["data"])

def compute_etag(obj: Dict[str, Any]) -> str:
    m = hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"W/\"{m}\""

@router.get("/memories/{memory_id}")
async def get_memory_etagged(memory_id: str, request: Request):
    mem = request.app.state.store.get(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Not found")
    etag = compute_etag(mem)
    inm = request.headers.get("if-none-match")
    headers = {"ETag": etag}
    if inm and inm == etag:
        return Response(status_code=304, headers=headers)
    return PlainTextResponse(json.dumps(mem), headers=headers, media_type="application/json")

@router.get("/export")
async def export_ndjson(request: Request, org_id: Optional[str] = None, limit: int = 1000, offset: int = 0):
    # Stream NDJSON
    def gen():
        batch = request.app.state.store.query(limit=limit, offset=offset, project_id=None)  # extend as needed
        for m in batch:
            if org_id and m.get("org_id") != org_id:
                continue
            yield (json.dumps(m) + "\n").encode()
    return StreamingResponse(gen(), media_type="application/x-ndjson")

@router.post("/import")
async def import_ndjson(request: Request, org_id: Optional[str] = None):
    # Expect NDJSON in body (stream)
    count = 0
    async for chunk in request.stream():
        for line in chunk.splitlines():
            if not line.strip():
                continue
            try:
                m = json.loads(line)
                if org_id:
                    m["org_id"] = org_id
                request.app.state.store.upsert(m)
                count += 1
            except Exception:
                continue
    return {"status": "ok", "imported": count}

@router.get("/search")
async def search(request: Request, q: str, persona_id: Optional[str] = None, thread_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    # Simple LIKE search (DB-layer should be extended for Postgres FTS later)
    results = []
    batch = request.app.state.store.query(limit=1000, offset=0)
    ql = q.lower()
    for m in batch:
        if persona_id and m.get("persona_id") != persona_id:
            continue
        if thread_id and m.get("thread_id") != thread_id:
            continue
        if ql in (m.get("text") or "").lower():
            results.append(m)
        if len(results) >= limit:
            break
    return {"results": results, "count": len(results)}