# Deployment Guide

This guide explains deployment options for the RAG Platform across low, medium, and high resource tiers. The repository itself only ships application code and local development scripts. Production Docker Compose or Kubernetes manifests should be maintained outside this repository.

## Table of Contents

- [Overview](#overview)
- [Low Resource Deployment (SQLite)](#low-resource-deployment-sqlite)
- [Medium Resource Deployment (PostgreSQL + pgvector)](#medium-resource-deployment-postgresql--pgvector)
- [High Resource Deployment (Elasticsearch Cluster)](#high-resource-deployment-elasticsearch-cluster)
- [Environment Variables](#environment-variables)
- [Health Checks and Monitoring](#health-checks-and-monitoring)
- [Backup and Recovery](#backup-and-recovery)
- [Upgrading](#upgrading)
- [Troubleshooting](#troubleshooting)

## Overview

The RAG Platform supports three deployment tiers based on your resource constraints and scale requirements:

| Level | Backend | Documents | Latency | Memory |
|-------|---------|-----------|---------|--------|
| Low | SQLite + FTS5 | < 10,000 | < 500ms | < 512MB |
| Medium | PostgreSQL + pgvector | 10K - 1M | < 200ms | < 4GB |
| High | Elasticsearch cluster | > 1M | < 100ms | Scale out |

Choose the tier that matches your needs. You can migrate between tiers by exporting and re-importing data.

## Low Resource Deployment (SQLite)

Best for: personal use, small teams, edge deployments, demos.

### Deployment Inputs

- `DATA_STORE_TYPE=sqlite`
- `SQLITE_DB_PATH=api/data/rag.sqlite`
- Persist `api/data/` outside the repository when deploying
- Build or reverse-proxy the frontend using your own infrastructure manifests

### Deploy

This repository no longer ships Docker Compose files. For local setup use:

```bash
./install.sh
./start.sh
```

### Resource Requirements

- CPU: 1 core
- RAM: 512MB
- Disk: 10GB

### Notes

- SQLite stores data in a single file. Back up by copying the `.db` file.
- FTS5 is built into SQLite 3.9.0+. No extra extensions needed.
- Vector search is disabled by default. Enable with `VECTOR_ENABLED=true` for small-scale semantic search.

## Medium Resource Deployment (PostgreSQL + pgvector)

Best for: small to medium businesses, self-hosted production.

### Deployment Inputs

- `DATA_STORE_TYPE=pgvector`
- `PGVECTOR_HOST`, `PGVECTOR_PORT`, `PGVECTOR_DATABASE`, `PGVECTOR_USER`, `PGVECTOR_PASSWORD`
- Provide a managed or self-hosted PostgreSQL + pgvector instance outside this repository
- Keep runtime credentials in environment variables or external secret managers

### Deploy

Use your own Docker/Kubernetes manifests outside this repository, or run locally via `./install.sh` + `./start.sh`.

### Resource Requirements

- CPU: 2 cores
- RAM: 4GB
- Disk: 100GB SSD

### Database Setup

The pgvector image includes the vector extension. The API will create tables and indexes automatically on first use.

For manual setup:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Notes

- HNSW indexes are created automatically for vector columns.
- Connection pooling is handled internally (pool size: 1-10).
- Consider PostgreSQL tuning for your workload:
  - `shared_buffers = 1GB`
  - `effective_cache_size = 3GB`
  - `work_mem = 16MB`

## High Resource Deployment (Elasticsearch Cluster)

Best for: large enterprises, high availability, massive scale.

### Deployment Inputs

- `DATA_STORE_TYPE=elasticsearch`
- `ELASTICSEARCH_HOSTS`, `ELASTICSEARCH_USERNAME`, `ELASTICSEARCH_PASSWORD`, `ELASTICSEARCH_API_KEY`
- Provision the Elasticsearch cluster outside this repository
- Store secrets in your deployment platform instead of checked-in files

### Multi-Node Cluster (Production)

For high availability, use a dedicated 3-node Elasticsearch cluster managed by your own infrastructure manifests or platform tooling.

### Deploy

Use your own production orchestration manifests. This repository only keeps application code and local development scripts.

### Resource Requirements (Single Node)

- CPU: 4 cores
- RAM: 8GB
- Disk: 500GB SSD

### Resource Requirements (3-Node Cluster)

- CPU: 12 cores total (4 per node)
- RAM: 24GB total (8GB per node)
- Disk: 1.5TB SSD total (500GB per node)
- Network: Low latency between nodes

### Notes

- Elasticsearch 8.x requires setting `xpack.security.enabled=false` for development.
- For production, enable security and configure TLS.
- The RRF (Reciprocal Rank Fusion) feature requires ES 8.8.0+.
- Monitor JVM heap usage. Set `Xms` and `Xmx` to 50% of available RAM.

## Environment Variables

### Common Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_STORE_TYPE` | Backend type: sqlite, pgvector, elasticsearch | sqlite |
| `LOG_LEVEL` | Logging level: DEBUG, INFO, WARNING, ERROR | INFO |
| `API_PORT` | API server port | 8000 |

### SQLite Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_DB_PATH` | Path to SQLite database file | api/data/rag.sqlite |
| `VECTOR_ENABLED` | Enable vector search in SQLite | false |

### PostgreSQL Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PGVECTOR_HOST` | PostgreSQL host | localhost |
| `PGVECTOR_PORT` | PostgreSQL port | 5432 |
| `PGVECTOR_DATABASE` | Database name | rag_platform |
| `PGVECTOR_USER` | Database user | postgres |
| `PGVECTOR_PASSWORD` | Database password | (empty) |
| `PGVECTOR_POOL_MIN` | Min connections in pool | 1 |
| `PGVECTOR_POOL_MAX` | Max connections in pool | 10 |

### Elasticsearch Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ELASTICSEARCH_HOSTS` | Comma-separated list of hosts | http://localhost:9200 |
| `ELASTICSEARCH_USERNAME` | Username for basic auth | (empty) |
| `ELASTICSEARCH_PASSWORD` | Password for basic auth | (empty) |
| `ELASTICSEARCH_API_KEY` | API key for authentication | (empty) |
| `ELASTICSEARCH_VERIFY_CERTS` | Verify TLS certificates | true |

## Health Checks and Monitoring

### API Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 12
}
```

### Backend Health Checks

Each data store implements `health_check()`:

```python
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

store = DataStoreFactory.create("pgvector", {...})
print(store.health_check())  # True or False
```

### Prometheus Metrics

The API exposes Prometheus metrics at `/metrics`:

- `rag_query_latency_seconds` - Query latency histogram
- `rag_documents_total` - Total documents indexed
- `rag_search_requests_total` - Search request counter

### Grafana Dashboard

Import the dashboard from `monitoring/grafana-dashboard.json` to visualize:

- Query latency by resource level
- Document count trends
- Backend health status
- Error rates

## Backup and Recovery

### SQLite

```bash
# Backup
cp api/data/rag.sqlite api/data/rag.sqlite.backup.$(date +%Y%m%d)

# Restore
cp api/data/rag.sqlite.backup.20240101 api/data/rag.sqlite
```

### PostgreSQL

```bash
# Backup
docker exec rag-platform-postgres-1 pg_dump -U rag_user rag_platform > backup.sql

# Restore
docker exec -i rag-platform-postgres-1 psql -U rag_user rag_platform < backup.sql
```

### Elasticsearch

```bash
# Backup (using snapshot repository)
curl -X PUT "localhost:9200/_snapshot/my_backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/mount/backups"
  }
}'

curl -X PUT "localhost:9200/_snapshot/my_backup/snapshot_1"

# Restore
curl -X POST "localhost:9200/_snapshot/my_backup/snapshot_1/_restore"
```

## Upgrading

### General Upgrade Steps

1. Back up your data
2. Review the changelog for breaking changes
3. Pull the latest code: `git pull origin main`
4. Update dependencies: `./install.sh`
5. Run migrations if needed
6. Restart services: `./start.sh`

### Version Compatibility

| Platform Version | SQLite | PostgreSQL | Elasticsearch |
|------------------|--------|------------|---------------|
| 1.0.x | 3.9.0+ | 14+ with pgvector 0.5+ | 8.8.0+ |

## Troubleshooting

### App Won't Start

Check logs:

Use the foreground output from `./start.sh`, or run backend/frontend commands separately for troubleshooting.

### Database Connection Failed

Verify the database is running and accessible:

```bash
# PostgreSQL
docker exec -it rag-platform-postgres-1 psql -U rag_user -d rag_platform -c "SELECT 1"

# Elasticsearch
curl http://localhost:9200/_cluster/health
```

### Slow Queries

1. Check resource limits (CPU, memory)
2. Review index sizes and consider reindexing
3. For PostgreSQL, run `ANALYZE` on tables
4. For Elasticsearch, check shard allocation

### Migration Between Tiers

To migrate from low to medium tier:

1. Export documents from SQLite
2. Set up PostgreSQL with pgvector
3. Import documents into PostgreSQL
4. Update `DATA_STORE_TYPE` environment variable

Example export/import script:

```python
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory

# Export from SQLite
sqlite = DataStoreFactory.create("sqlite", {"db_path": "api/data/rag.sqlite"})
docs = sqlite.search("my_collection", "*", search_method="keyword", top_k=10000)

# Import to PostgreSQL
pg = DataStoreFactory.create("pgvector", {...})
pg.create_collection("my_collection", dimension=768)
pg.add_documents("my_collection", docs)
```
