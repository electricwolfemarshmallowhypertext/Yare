#!/usr/bin/env python3
"""
Simple fuzzing harness for pre-VPS checks.
Sends random and edge-case payloads to critical endpoints and asserts non-5xx responses.
"""

from __future__ import annotations
import os
import json
import random
import string
import time
import httpx

BASE = os.getenv("BASE_URL", "http://localhost:8000")
TOKEN = os.getenv("API_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

def rand_text(n=100):
    alphabet = string.ascii_letters + string.digits + "     \n\t!@#$%^&*()[]{}<>?/'\"\\"
    return "".join(random.choice(alphabet) for _ in range(n))

def post(path, body, headers=None):
    h = HEADERS.copy()
    if headers:
        h.update(headers)
    return httpx.post(f"{BASE}{path}", json=body, headers=h, timeout=10)

def get(path, headers=None):
    h = HEADERS.copy()
    if headers:
        h.update(headers)
    return httpx.get(f"{BASE}{path}", headers=h, timeout=10)

def main():
    # Health/status public
    for path in ["/health", "/status"]:
        r = get(path)
        assert r.status_code == 200, (path, r.status_code, r.text)

    # Protected routes (skip if no token)
    if not TOKEN:
        print("No API_TOKEN set; skipping protected fuzz")
        return

    # Fuzz memories create
    for i in range(10):
        mem = {
            "id": f"fuzz_{i}_{int(time.time()*1000)}",
            "text": rand_text(200),
            "type": random.choice(["fact", "interaction", "summary", "note"]),
            "salience": random.random(),
            "created_at": "2025-01-01T00:00:00Z",
            "thread_id": f"t{random.randint(1,5)}",
            "user_id": f"u{random.randint(1,5)}",
            "persona_id": f"p{random.randint(1,5)}",
        }
        r = post("/memories", mem)
        assert r.status_code in (200, 201, 400, 429, 403), (r.status_code, r.text)

    # Risks and personas list should not 5xx
    for path in ["/risks", "/persona"]:
        r = get(path)
        assert r.status_code in (200, 403, 429), (path, r.status_code, r.text)

    print("Fuzz complete")

if __name__ == "__main__":
    main()