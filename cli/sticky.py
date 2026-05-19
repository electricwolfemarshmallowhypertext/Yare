#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import sys
from pathlib import Path
import typer
import requests

app = typer.Typer(add_completion=False)
CONFIG = Path.home() / ".sticky" / "config.json"

def load_cfg():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {"base_url": "http://localhost:8000", "token": "", "org_id": ""}

def save_cfg(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))

def headers(cfg, need_auth=True, need_org=False):
    h = {"Content-Type":"application/json"}
    if need_auth and cfg.get("token"):
        h["Authorization"] = f"Bearer {cfg['token']}"
    if need_org and cfg.get("org_id"):
        h["X-Org-Id"] = cfg["org_id"]
    return h

@app.command()
def config(base_url: str = typer.Option(None), token: str = typer.Option(None), org_id: str = typer.Option(None)):
    "Set or show config"
    cfg = load_cfg()
    if base_url is not None: cfg["base_url"] = base_url
    if token is not None: cfg["token"] = token
    if org_id is not None: cfg["org_id"] = org_id
    save_cfg(cfg)
    typer.echo(json.dumps(cfg, indent=2))

@app.command()
def health():
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/health", timeout=10)
    typer.echo(r.text)

@app.command()
def status():
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/status", timeout=10)
    typer.echo(r.text)

@app.command()
def keys():
    "List API keys (admin)"
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/keys", headers=headers(cfg), timeout=15)
    typer.echo(r.text)

@app.command()
def revoke(key_hash: str):
    cfg = load_cfg()
    r = requests.delete(f"{cfg['base_url']}/keys/{key_hash}", headers=headers(cfg), timeout=15)
    typer.echo(r.text)

@app.command()
def usage():
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/usage", headers=headers(cfg), timeout=15)
    typer.echo(r.text)

@app.command()
def store_memory(id: str, text: str, thread_id: str, user_id: str, persona_id: str, type: str = "fact", salience: float = 0.5):
    cfg = load_cfg()
    payload = {"id": id, "text": text, "type": type, "salience": salience, "created_at": "2025-01-01T00:00:00Z", "thread_id": thread_id, "user_id": user_id, "persona_id": persona_id}
    r = requests.post(f"{cfg['base_url']}/memories", headers=headers(cfg, need_org=True), json=payload, timeout=20)
    typer.echo(r.text)

@app.command()
def get_memory(id: str):
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/memories/{id}", headers=headers(cfg, need_org=True), timeout=15)
    typer.echo(r.text)

@app.command()
def export_ndjson(out: str = "export.ndjson"):
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/data/export", headers=headers(cfg, need_org=True), stream=True, timeout=60)
    with open(out, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk: f.write(chunk)
    typer.echo(f"Wrote {out}")

@app.command()
def import_ndjson(path: str):
    cfg = load_cfg()
    with open(path, "rb") as f:
        data = f.read()
    r = requests.post(f"{cfg['base_url']}/data/import", headers=headers(cfg, need_org=True), data=data, timeout=120)
    typer.echo(r.text)

@app.command()
def search(q: str, limit: int = 20):
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/data/search", headers=headers(cfg, need_org=True), params={"q": q, "limit": limit}, timeout=20)
    typer.echo(r.text)

@app.command()
def personas():
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/persona", headers=headers(cfg, need_org=True), timeout=15)
    typer.echo(r.text)

@app.command()
def persona_import(path: str):
    cfg = load_cfg()
    doc = json.loads(Path(path).read_text())
    r = requests.post(f"{cfg['base_url']}/persona/import", headers=headers(cfg, need_org=True), json=doc, timeout=20)
    typer.echo(r.text)

@app.command()
def persona_export(pid: str):
    cfg = load_cfg()
    r = requests.get(f"{cfg['base_url']}/persona/export/{pid}", headers=headers(cfg, need_org=True), timeout=15)
    typer.echo(r.text)

if __name__ == "__main__":
    app()