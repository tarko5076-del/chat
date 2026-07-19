# Deployment & Infrastructure Guide

## Overview

The Restaurant Intelligence Platform is deployed using Docker Compose with:
- **Backend**: Django + Gunicorn (ASGI via uvicorn for streaming)
- **Frontend**: React + Vite (served via Nginx)
- **Database**: PostgreSQL 16 with pgvector extension
- **Reverse Proxy**: Nginx (production) / Gunicorn (container)

---

## Prerequisites

- Docker & Docker Compose v2.4+
- Environment variables configured (see `.env.example`)
- PostgreSQL client (for manual backup/restore)
- A Hugging Face API token (or other LLM provider key) for AI features

---

## Quick Start

```bash
# Clone and enter the project
git clone <repo-url> && cd first_chatbot

# Copy environment file
cp backend/.env.example backend/.env
# Edit .env with your API keys and DB credentials

# Build and start all services
docker compose up --build -d

# Check health
curl http://localhost/health/

# View logs
docker compose logs -f
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_DB` | Yes | `restaurant_agent` | Database name |
| `POSTGRES_USER` | Yes | `resto_user` | Database user |
| `POSTGRES_PASSWORD` | Yes | — | Database password (generate a strong one) |
| `LLM_API_KEY` | No | — | OpenAI-compatible API key (HF, OpenRouter, etc.) |
| `LLM_BASE_URL` | No | `https://api-inference.huggingface.co/v1` | LLM provider base URL |
| `LLM_MODEL` | No | `meta-llama/Llama-3.1-8B-Instruct` | Model name |
| `HF_TOKEN` | No | — | Hugging Face token (alternative to LLM_API_KEY) |
| `OPENAI_API_KEY` | No | — | For embeddings (RAG) |
| `CHAPA_SECRET_KEY` | No | — | Payment gateway |
| `CHAPA_PUBLIC_KEY` | No | — | Payment gateway |
| `CORS_ORIGINS` | No | `http://localhost` | Allowed CORS origins |
| `USE_SQLITE` | No | `false` | Set `true` for local dev without Docker |
| `FORCE_REFRESH` | No | `false` | Re-seed menu & knowledge on startup |

---

## Database Backup Strategy

### Automated Daily Backups

Add a cron job or Docker sidecar container to run daily backups:

```bash
# Backup script: scripts/backup-db.sh
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/restaurant"
mkdir -p "$BACKUP_DIR"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "$POSTGRES_HOST" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  -f "$BACKUP_DIR/${POSTGRES_DB}_${TIMESTAMP}.dump"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -delete
```

**Cron example** (daily at 3 AM):
```
0 3 * * * /opt/restaurant/scripts/backup-db.sh
```

### Docker Backup Command

```bash
# One-time backup
docker compose exec db pg_dump \
  -U $POSTGRES_USER \
  --format=custom \
  -f /tmp/backup_$(date +%Y%m%d).dump \
  $POSTGRES_DB

# Copy out of container
docker compose cp db:/tmp/backup_*.dump ./backups/
```

### Restore

```bash
# Restore from backup file
docker compose exec -T db pg_restore \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  --clean \
  --if-exists \
  < ./backups/backup_20260719.dump
```

### Backup Verification

Check backup integrity monthly:
```bash
pg_restore --list backup.dump | head -5
# Should show table names and sequences
```

### Recovery Point Objective (RPO)

| Backup Type | Frequency | RPO | Storage |
|-------------|-----------|-----|---------|
| Full DB dump | Daily | 24 hours | ~100 MB (compressed) |
| Transaction logs | Continuous (if enabled) | Seconds | Configurable |

---

## Health Checks

The platform exposes:

- **`GET /health/`** — DB connectivity, pgvector status, LLM provider config, uptime
- **`GET /metrics/`** — Request counts, avg response time, error rate, LLM calls, token usage, tool calls

Configure your monitoring system (Prometheus, Datadog, etc.) to poll `/health/` every 30s and `/metrics/` every 60s.

---

## Scaling Considerations

### Horizontal Scaling (Multiple Workers)

- **Gunicorn workers**: Set `GUNICORN_WORKERS` env var (default: 4). Increase for higher concurrency.
- **Database connections**: Each worker needs a DB connection pool entry. Set `CONN_MAX_AGE` in Django settings.
- **Stateless design**: The agent stores session state in the database (AgentSession model), so requests can be routed to any worker.

### Vertical Scaling

- **LLM latency**: The primary bottleneck is LLM API calls. Consider upgrading to a faster model or enabling response streaming.
- **Vector search**: For large knowledge bases (>10K items), ensure pgvector has sufficient memory. Set `ivfflat.probes` in the index creation query.

---

## Monitoring & Alerting

### Recommended Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| 5xx error rate | > 1% over 5 min | Check logs, restart workers |
| LLM call failures | > 10% over 5 min | Check API key, fallback to local planner |
| DB connection pool exhaustion | > 80% | Increase pool size or workers |
| Avg response time | > 5s over 5 min | Investigate slow queries or LLM latency |
| Disk space (backups) | > 80% | Archive or delete old backups |

### Logging

Logs are written to stdout/stderr and collected by Docker. Configure a log aggregator (e.g., Loki, Datadog, Papertrail) for production.

**Key loggers:**
- `agent.llm_audit` — LLM call metadata (provider, model, duration, tokens)
- `agent.controller` — Agent orchestration, tool execution
- `django.request` — HTTP request/response
- `config.monitoring` — Health and metrics

**Never logged at INFO+**: Full prompt content, payment details, raw LLM responses.

---

## Secret Management

### Environment-Based (Development / Single-Server)

The simplest approach for small deployments. Store secrets in `.env` files:

```bash
# .env (never commit to git)
POSTGRES_PASSWORD=<strong-random-password>
LLM_API_KEY=sk-...
CHAPA_SECRET_KEY=...
```

**Risks**:
- Secrets are in plaintext on disk
- No audit trail for secret access
- Rotation requires restarting the container

### Docker Secrets (Single-Server / Docker Swarm)

Better for single-server production deployments:

```bash
# Create secrets from files
echo "<strong-random-password>" | docker secret create postgres_password -
echo "sk-..." | docker secret create llm_api_key -

# docker-compose.yml snippet:
# secrets:
#   postgres_password:
#     external: true
#
# services:
#   backend:
#     secrets:
#       - postgres_password
#     environment:
#       POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
```

Update `entrypoint.sh` to read secrets from files:
```bash
# entrypoint.sh
if [ -f "$POSTGRES_PASSWORD_FILE" ]; then
  export POSTGRES_PASSWORD=$(cat $POSTGRES_PASSWORD_FILE)
fi
```

**Benefits**:
- Secrets are mounted as tmpfs files (in-memory, not on disk)
- Only services with explicit `secrets:` blocks can access them
- Rotation via `docker secret update` or deploy with new secrets

### Vault-Based (Multi-Server / Enterprise)

For multi-node deployments with compliance requirements, use a vault service:

| Service | Use Case | Free Tier |
|---------|----------|-----------|
| **HashiCorp Vault** | Enterprise, dynamic secrets | Self-hosted (open source) |
| **AWS Secrets Manager** | AWS-native deployments | $0.40/secret/month |
| **Azure Key Vault** | Azure-native deployments | $0.03/10K operations |
| **GCP Secret Manager** | GCP-native deployments | $0.06/secret/month |
| **1Password Connect** | Small teams | Included with 1Password |

### Secret Rotation Strategy

| Secret | Rotation Frequency | Method |
|--------|-------------------|--------|
| Database password | Every 90 days | `docker secret update` + DB `ALTER USER ... PASSWORD` |
| LLM API key | On compromise | Update env var + restart service |
| Chapa API keys | Every 180 days | Update env var + restart service |
| JWT secret | Every 90 days | Update `SECRET_KEY` + issue new tokens |

## Security

- **CORS**: Restrict to known frontend domains in production.
- **Rate limiting**: Enabled by default (60 req/min for chat, 120 for menu, 15 for auth).
- **Prompt injection protection**: User messages are sanitized (HTML stripped, injection patterns detected) before reaching the LLM.
- **Admin endpoints**: Knowledge management CRUD requires `is_staff=True`.

---

## Troubleshooting

### Common Issues

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `connection refused` on DB | PostgreSQL not ready | Docker healthcheck will retry; ensure `depends_on` has `condition: service_healthy` |
| LLM returns empty responses | API key invalid or rate-limited | Check `LLM_API_KEY`, verify in provider dashboard |
| `no pg_hba.conf entry` | DB credentials mismatch | Check `POSTGRES_USER`/`POSTGRES_PASSWORD` in `.env` |
| Frontend shows blank page | API server unreachable | Check `VITE_API_BASE_URL` in frontend `.env` |
| Migrations failing | Schema conflict | Run `python manage.py migrate --fake` or restore from backup |
| Embedding generation fails | API key missing | Set `OPENAI_API_KEY` or `HF_TOKEN` for embedding model |
| High memory usage | Too many gunicorn workers | Reduce `GUNICORN_WORKERS` or add `--max-requests` |

### Debug Mode

```bash
# View real-time logs
docker compose logs -f backend

# Enter a running container
docker compose exec backend bash

# Run Django management commands
docker compose exec backend python manage.py check --deploy

# Test DB connectivity
docker compose exec db pg_isready -U $POSTGRES_USER
```
