# Deployment (VPS)

## Prereqs
- Docker + Docker Compose
- Domain name (for TLS via Caddy) or use plain HTTP on port 8000 behind firewall
- Create secrets:
  - `secrets/api_keys.txt`: e.g. `mysupersecret:admin|*`
  - `secrets/fernet.key`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Run
```bash
cp .env.example .env
docker compose up -d --build
```

Health: `curl -fsS http://localhost:8000/health`

Prometheus metrics: `:9090/metrics`

## Backups
```bash
python scripts/backup_sqlite.py --db data/memory/fallback.db --out data/backups --retention 7
```
Cron example:
```
0 * * * * /usr/bin/python /app/scripts/backup_sqlite.py --db /app/data/memory/fallback.db --out /app/data/backups --retention 24 >> /var/log/memory_backup.log 2>&1
```

## Migrations
```bash
python scripts/migrate.py --db data/memory/fallback.db --migrations migrations
```

## TLS/Ingress
Use the provided `Caddyfile` on the VPS:
```bash
# install caddy then:
sudo caddy run --config ./Caddyfile
```

## Scale strategy
- Start with SQLite (single instance).
- For horizontal writes: move to Postgres, replace MemoryStore with a Postgres-backed implementation (SQLAlchemy) and run Alembic migrations.
- Redis scales independently (external managed Redis recommended in prod).