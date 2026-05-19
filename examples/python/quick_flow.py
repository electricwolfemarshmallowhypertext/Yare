#!/usr/bin/env python3
import os, json, requests, uuid, time

BASE = os.getenv("BASE_URL", "http://localhost:8000")
TOKEN = os.getenv("API_TOKEN", "")
ORG = os.getenv("ORG_ID", "org-123")
H = {"Authorization": f"Bearer {TOKEN}", "X-Org-Id": ORG, "Content-Type": "application/json"}

print("# Health")
print(requests.get(f"{BASE}/health").text)

print("# Store and fetch a memory")
mid = f"m_{uuid.uuid4().hex}"
payload = {
    "id": mid, "text": "test note", "type": "note", "salience": 0.5,
    "created_at": "2025-01-01T00:00:00Z", "thread_id": "t1", "user_id": "u1", "persona_id": "p1"
}
print(requests.post(f"{BASE}/memories", headers=H, data=json.dumps(payload)).text)
print(requests.get(f"{BASE}/memories/{mid}", headers=H).text)

print("# Export NDJSON (first lines)")
r = requests.get(f"{BASE}/data/export", headers=H, stream=True)
for i, chunk in enumerate(r.iter_lines()):
    print(chunk.decode())
    if i > 2: break