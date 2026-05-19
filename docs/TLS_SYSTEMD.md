# TLS/Ingress and systemd (when ready)

## Reverse proxy (Caddy) as a service
1) Install Caddy (official docs).
2) Put your Caddyfile at /etc/caddy/Caddyfile (use the one we provided earlier).
3) Enable and start:
```bash
sudo systemctl enable caddy
sudo systemctl restart caddy
```

## Hardened service unit for a non-docker run (optional)
Create /etc/systemd/system/memory.service:
```ini
[Unit]
Description=Memory Service
After=network.target

[Service]
Environment=ENV=production
Environment=LOG_LEVEL=INFO
Environment=REDIS_URL=redis://127.0.0.1:6379/0
Environment=SQLITE_PATH=/var/lib/memory/fallback.db
WorkingDirectory=/opt/memory
ExecStart=/usr/bin/uvicorn src.memory.server:app --host 0.0.0.0 --port 8000
User=memory
Group=memory
Restart=always
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
AmbientCapabilities=

[Install]
WantedBy=multi-user.target
```
Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable memory
sudo systemctl start memory
```

## Security headers at the edge
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: no-referrer
- CSP: default-src 'none'