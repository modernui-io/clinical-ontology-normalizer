# Clinical Knowledge Graph Deployment Guide

This guide covers deploying the Clinical Knowledge Graph platform with Neo4j integration.

## Prerequisites

- Docker Desktop 24.0+
- Python 3.11+
- 16GB RAM minimum (32GB recommended)
- 50GB free disk space

## Quick Start

### 1. Start Neo4j

```bash
# Deploy Neo4j 5.15.0 with APOC plugin
docker run -d \
  --name neo4j-clinical \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/clinical123 \
  -e 'NEO4J_PLUGINS=["apoc"]' \
  -e NEO4J_dbms_security_procedures_unrestricted='apoc.*' \
  -v neo4j_data:/data \
  neo4j:5.15.0-community

# Wait for Neo4j to be ready (30-60 seconds)
docker logs -f neo4j-clinical
```

### 2. Configure Environment

Create or update `.env` in the backend directory:

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=clinical123

# Optional: Redis for L2 cache
REDIS_URL=redis://localhost:6379
```

### 3. Install Dependencies

```bash
cd backend
uv sync  # or: pip install -e .
```

### 4. Load OMOP Vocabulary Data

Download OMOP CDM vocabularies from [Athena](https://athena.ohdsi.org/):
- SNOMED-CT
- RxNorm
- ICD-10-CM
- LOINC
- CPT

Place the CSV files in `~/Downloads/` (or update the script paths).

```bash
# Load concepts (~5.6M, ~3 minutes)
python scripts/load_omop_to_neo4j.py

# Load relationships (~33M, ~11 minutes)
python scripts/load_omop_relationships.py
```

### 5. Create Vector Index (Optional but Recommended)

For semantic similarity search:

```bash
# Creates embeddings for 150K high-priority concepts (~2 minutes)
python scripts/create_vector_index.py
```

### 6. Verify Installation

```bash
# Test Neo4j connection
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'clinical123'))
with driver.session() as session:
    result = session.run('MATCH (c:Concept) RETURN count(c) as count')
    print(f'Total concepts: {result.single()[\"count\"]:,}')
driver.close()
"
```

### 7. Start the API Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Graph Reasoning

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/graph/health` | GET | Neo4j connection health |
| `/graph/cache/stats` | GET | Cache performance statistics |
| `/graph/reasoning/multi-hop` | POST | Multi-hop reasoning queries |
| `/graph/reasoning/score-paths` | POST | Path confidence scoring |
| `/graph/reasoning/find-treatments` | POST | Treatment discovery |
| `/graph/reasoning/check-contraindications` | POST | Drug safety checks |
| `/graph/reasoning/aggregate-evidence` | POST | Evidence aggregation |

### Ontology Search

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/graph-rag/ontology/search` | GET | Semantic concept search |
| `/graph-rag/ontology/expand` | GET | Concept expansion |
| `/graph-rag/ontology-enhanced-answer` | POST | Graph-RAG with ontology |

## Example API Calls

### Multi-hop Reasoning

```bash
curl -X POST http://localhost:8000/graph/reasoning/multi-hop \
  -H "Content-Type: application/json" \
  -d '{
    "seed_concepts": [201826],
    "max_hops": 3,
    "target_domains": ["Drug"],
    "min_confidence": 0.5,
    "top_k": 10,
    "include_evidence": true
  }'
```

### Ontology Search

```bash
curl "http://localhost:8000/graph-rag/ontology/search?query=diabetes&limit=5"
```

### Vector Similarity Search

```bash
curl "http://localhost:8000/graph-rag/ontology/search?query=heart+failure&limit=10"
```

## Performance Tuning

### Neo4j Configuration

For production deployments, add to `neo4j.conf`:

```
# Memory settings
dbms.memory.heap.initial_size=4g
dbms.memory.heap.max_size=8g
dbms.memory.pagecache.size=4g

# Transaction settings
dbms.transaction.timeout=60s
```

### Cache Configuration

The platform uses a two-tier cache:
- **L1**: In-memory LRU cache (10K entries, 512MB max)
- **L2**: Redis (optional, for distributed caching)

TTL settings by cache type:
- Concepts: 1 hour
- Relationships: 30 minutes
- Query results: 2 minutes
- Embeddings: 2 hours

### Connection Pooling

Default Neo4j driver settings:
- Max connections: 50
- Connection timeout: 30s
- Max transaction retry: 3

## Monitoring

### Cache Statistics

```bash
curl http://localhost:8000/graph/cache/stats
```

Returns:
```json
{
  "hits": 1234,
  "misses": 567,
  "hit_rate": 0.6854,
  "l1_size": 892,
  "l1_memory_bytes": 45678901,
  "l2_enabled": false
}
```

### Neo4j Metrics

Access Neo4j Browser at http://localhost:7474 for:
- Query performance
- Memory usage
- Index statistics

## Troubleshooting

### Neo4j Won't Start

```bash
# Check Docker logs
docker logs neo4j-clinical

# Verify ports are available
lsof -i :7474
lsof -i :7687
```

### Connection Refused

```bash
# Verify Neo4j is ready
curl http://localhost:7474

# Check driver connectivity
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'clinical123'))
driver.verify_connectivity()
print('Connected!')
"
```

### Slow Queries

1. Check index usage:
```cypher
EXPLAIN MATCH (c:Concept {concept_id: 12345}) RETURN c
```

2. Verify indexes exist:
```cypher
SHOW INDEXES
```

3. Monitor cache hit rate:
```bash
curl http://localhost:8000/graph/cache/stats
```

### Memory Issues

Reduce batch sizes in scripts:
```python
BATCH_SIZE = 5000  # Default is 10000
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│  Graph API  │  Graph RAG API  │  Reasoning API  │  NLP API  │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Graph DB    │  │ Embedding   │  │ Cache Service       │  │
│  │ Service     │  │ Service     │  │ (L1: LRU, L2: Redis)│  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
├─────────┼────────────────┼──────────────────────────────────┤
│         │                │                                   │
│    ┌────▼────┐     ┌─────▼─────┐                            │
│    │ Neo4j   │     │ Sentence  │                            │
│    │ 5.15.0  │     │ Transform │                            │
│    └─────────┘     └───────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Data Statistics

After loading OMOP CDM vocabularies:

| Metric | Value |
|--------|-------|
| Total Concepts | 5,655,175 |
| Total Relationships | 32,871,367 |
| Vector Embeddings | 150,000 |
| Unique Vocabularies | 60+ |

Top vocabularies by concept count:
- RxNorm Extension: 2.17M
- NDC: 1.28M
- SNOMED: 1.09M
- ICD10CM: 83K
- RxNorm: 120K

## Security Considerations

1. **Change default passwords** in production
2. **Enable Neo4j authentication** (already enabled by default)
3. **Use TLS** for Neo4j connections in production
4. **Restrict network access** to Neo4j ports
5. **Monitor API access** for unusual patterns

## Backup and Recovery

### Backup Neo4j

```bash
# Stop Neo4j first
docker stop neo4j-clinical

# Backup data volume
docker run --rm -v neo4j_data:/data -v $(pwd):/backup \
  ubuntu tar cvf /backup/neo4j-backup.tar /data

# Restart
docker start neo4j-clinical
```

### Restore

```bash
docker stop neo4j-clinical
docker run --rm -v neo4j_data:/data -v $(pwd):/backup \
  ubuntu tar xvf /backup/neo4j-backup.tar -C /
docker start neo4j-clinical
```
