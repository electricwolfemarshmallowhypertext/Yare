# Security Checklist

- Secrets via files or secret manager, never plaintext env
- Rotate API keys and Fernet keys regularly (key rotation supported)
- Enforce edge limits (Caddy) and API limits (rate limiter)
- Validate input sizes and content types
- TLS everywhere via reverse proxy
- Separate roles: reader/writer/admin with least privilege
- Log audit events (memory_upsert) and monitor AUTH_DECISIONS
- Run SAST (bandit), dep checks (safety)
- Regular backups + integrity checks, test restores
- Pen-test and fuzz routes, chaos testing for Redis/DB outages