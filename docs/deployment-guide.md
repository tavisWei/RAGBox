# Deployment Guide

This guide explains how to deploy the RAG Platform in production for all three resource levels: low, medium, and high.

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

### Docker Compose

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "5001:5001"
    environment:
      - DATA_STORE_TYPE=sqlite
      - SQLITE_DB_PATH=/data/rag_data.db
    volumes:
      - sqlite_data:/data
    restart: unless-stopped

  web:
    build:
      context: ./web
      dockerfile: ../docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:5001
    depends_on:
      - api
    restart: unless-stopped

volumes:
  sqlite_data:
```

### Deploy

```bash
cp docker-compose.low.yml docker-compose.yml
docker-compose up -d
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

### Docker Compose

```yaml
version: "3.8"

services:
  postgres:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: rag_platform
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "5001:5001"
    environment:
      - DATA_STORE_TYPE=pgvector
      - PGVECTOR_HOST=postgres
      - PGVECTOR_PORT=5432
      - PGVECTOR_DATABASE=rag_platform
      - PGVECTOR_USER=rag_user
      - PGVECTOR_PASSWORD=changeme
    depends_on:
      - postgres
    restart: unless-stopped

  web:
    build:
      context: ./web
      dockerfile: ../docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:5001
    depends_on:
      - api
    restart: unless-stopped

volumes:
  pg_data:
```

### Deploy

```bash
cp docker-compose.medium.yml docker-compose.yml
docker-compose up -d
```

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

### Docker Compose

```yaml
version: "3.8"

services:
  es01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - node.name=es01
      - cluster.name=rag-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "5001:5001"
    environment:
      - DATA_STORE_TYPE=elasticsearch
      - ELASTICSEARCH_HOSTS=http://es01:9200
    depends_on:
      - es01
    restart: unless-stopped

  web:
    build:
      context: ./web
      dockerfile: ../docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:5001
    depends_on:
      - api
    restart: unless-stopped

volumes:
  es_data:
```

### Multi-Node Cluster (Production)

For true high availability, deploy a 3-node cluster:

```yaml
services:
  es01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - node.name=es01
      - cluster.name=rag-cluster
      - cluster.initial_master_nodes=es01,es02,es03
      - discovery.seed_hosts=es02,es03
      - bootstrap.memory_lock=true
      - xpack.security.enabled=true
      - xpack.security.transport.ssl.enabled=true
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"
    ...

  es02:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - node.name=es02
      - cluster.name=rag-cluster
      - cluster.initial_master_nodes=es01,es02,es03
      - discovery.seed_hosts=es01,es03
      ...

  es03:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - node.name=es03
      - cluster.name=rag-cluster
      - cluster.initial_master_nodes=es01,es02,es03
      - discovery.seed_hosts=es01,es02
      ...
```

### Deploy

```bash
cp docker-compose.high.yml docker-compose.yml
docker-compose up -d
```

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
| `API_PORT` | API server port | 5001 |

### SQLite Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_DB_PATH` | Path to SQLite database file | data/rag_data.db |
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
curl http://localhost:5001/health
```

Expected response:

```json
{
  "status": "healthy",
  "data_store": "sqlite",
  "data_store_healthy": true
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
cp data/rag_data.db data/rag_data.db.backup.$(date +%Y%m%d)

# Restore
cp data/rag_data.db.backup.20240101 data/rag_data.db
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
4. Update dependencies: `pip install -r requirements.txt`
5. Run migrations if needed
6. Restart services: `docker-compose up -d`

### Version Compatibility

| Platform Version | SQLite | PostgreSQL | Elasticsearch |
|------------------|--------|------------|---------------|
| 1.0.x | 3.9.0+ | 14+ with pgvector 0.5+ | 8.8.0+ |

## Troubleshooting

### Container Won't Start

Check logs:

```bash
docker-compose logs api
docker-compose logs postgres
docker-compose logs es01
```

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
sqlite = DataStoreFactory.create("sqlite", {"db_path": "data/rag_data.db"})
docs = sqlite.search("my_collection", "*", search_method="keyword", top_k=10000)

# Import to PostgreSQL
pg = DataStoreFactory.create("pgvector", {...})
pg.create_collection("my_collection", dimension=768)
pg.add_documents("my_collection", docs)
```
