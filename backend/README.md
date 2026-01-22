# Clinical Knowledge Graph Platform

A production-grade clinical knowledge graph platform with Neo4j integration, UMLS-compatible multi-hop reasoning, and vector similarity search.

## Features

- **Knowledge Graph**: 5.6M OMOP concepts, 33M relationships
- **Multi-hop Reasoning**: DR.KNOWS-compatible path traversal (1-5 hops)
- **Vector Search**: Semantic similarity via sentence-transformers
- **Query Caching**: Two-tier LRU + Redis cache
- **NLP Pipeline**: BioClinicalBERT + rule-based extraction
- **Multi-Agent**: 4-agent consensus system for clinical reasoning

## Quick Start

```bash
# 1. Start Neo4j
docker run -d --name neo4j-clinical \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/clinical123 \
  -e 'NEO4J_PLUGINS=["apoc"]' \
  neo4j:5.15.0-community

# 2. Install dependencies
uv sync

# 3. Load data (requires OMOP CSV files)
python scripts/load_omop_to_neo4j.py
python scripts/load_omop_relationships.py

# 4. Start API
uvicorn app.main:app --reload
```

## API Endpoints

### Graph Reasoning

| Endpoint | Description |
|----------|-------------|
| `POST /graph/reasoning/multi-hop` | Multi-hop reasoning from seed concepts |
| `POST /graph/reasoning/find-treatments` | Find treatments for conditions |
| `POST /graph/reasoning/check-contraindications` | Drug safety checks |
| `GET /graph/cache/stats` | Cache performance stats |

### Ontology Search

| Endpoint | Description |
|----------|-------------|
| `GET /graph-rag/ontology/search` | Semantic concept search |
| `GET /graph-rag/ontology/expand` | Concept expansion |

## Benchmark Results

DR.KNOWS parity achieved (105.4% of baseline):

| Metric | Score | Baseline |
|--------|-------|----------|
| Overall | 89.17% | 84.60% |
| Multi-hop (1-3) | 100% | 85.6-92.3% |
| Semantic Coverage | 90.55% | N/A |

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md)
- [Benchmark Results](docs/BENCHMARK_RESULTS.md)
- [Gap Analysis](docs/GAP_ANALYSIS.md)
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md)

## Architecture

```
FastAPI Application
├── Graph API (/graph/*)
│   ├── Health & Stats
│   ├── Concept Navigation
│   └── Multi-hop Reasoning
├── Graph RAG API (/graph-rag/*)
│   ├── Ontology Search
│   └── Enhanced Answers
├── NLP API (/nlp/*)
└── Agent API (/agent/*)

Services
├── Neo4j (5.6M concepts, 33M relationships)
├── Sentence Transformers (150K embeddings)
└── Query Cache (L1: LRU, L2: Redis)
```

## Data Statistics

| Resource | Count |
|----------|-------|
| Concepts | 5,655,175 |
| Relationships | 32,871,367 |
| Vector Embeddings | 150,000 |
| Vocabularies | 60+ |

## License

Proprietary - Internal Use Only
