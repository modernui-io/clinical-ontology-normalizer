#!/usr/bin/env python3
"""
Create Neo4j Vector Index for OMOP Concepts.

This script:
1. Creates a vector index on Concept nodes for similarity search
2. Generates embeddings for high-priority concepts (Drug, Condition domains)
3. Stores embeddings in Neo4j for vector similarity queries

Requirements:
- sentence-transformers
- neo4j
"""

import logging
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "clinical123"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 dimension
BATCH_SIZE = 500
MAX_CONCEPTS = 100_000  # Start with high-priority concepts


def create_vector_index(driver):
    """Create vector index for concept embeddings."""
    logger.info("Creating vector index...")

    with driver.session() as session:
        # Drop existing index if it exists (to recreate with correct settings)
        try:
            session.run("DROP INDEX concept_embedding IF EXISTS")
            logger.info("Dropped existing vector index")
        except Exception:
            pass

        # Create vector index using Neo4j 5.x syntax
        # Note: Community Edition supports vector indexes in 5.11+
        query = """
        CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
        FOR (c:Concept)
        ON c.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 384,
                `vector.similarity_function`: 'cosine'
            }
        }
        """
        try:
            session.run(query)
            logger.info("Created vector index 'concept_embedding' (384 dimensions, cosine similarity)")
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            return False

        # Verify index was created
        result = session.run("SHOW INDEXES YIELD name, type WHERE name = 'concept_embedding' RETURN name, type")
        indexes = list(result)
        if indexes:
            logger.info(f"Vector index verified: {indexes[0]['name']} ({indexes[0]['type']})")
            return True
        else:
            logger.warning("Vector index not found after creation")
            return False


def get_high_priority_concepts(driver, limit: int = MAX_CONCEPTS):
    """Get high-priority concepts to embed (drugs, conditions)."""
    logger.info(f"Fetching up to {limit:,} high-priority concepts...")

    # Prioritize Drug and Condition domains as they're most useful for clinical reasoning
    query = """
    MATCH (c:Concept)
    WHERE c.domain_id IN ['Drug', 'Condition', 'Procedure', 'Measurement']
      AND c.name IS NOT NULL
      AND c.standard_concept = 'S'
    RETURN c.concept_id as concept_id, c.name as name, c.domain_id as domain
    ORDER BY
        CASE c.domain_id
            WHEN 'Drug' THEN 1
            WHEN 'Condition' THEN 2
            WHEN 'Procedure' THEN 3
            ELSE 4
        END,
        c.concept_id
    LIMIT $limit
    """

    concepts = []
    with driver.session() as session:
        result = session.run(query, limit=limit)
        for record in result:
            concepts.append({
                "concept_id": record["concept_id"],
                "name": record["name"],
                "domain": record["domain"]
            })

    # Count by domain
    domain_counts = {}
    for c in concepts:
        domain_counts[c["domain"]] = domain_counts.get(c["domain"], 0) + 1

    logger.info(f"Fetched {len(concepts):,} concepts: {domain_counts}")
    return concepts


def generate_embeddings(texts: list[str], model):
    """Generate embeddings for a batch of texts."""
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [e.tolist() for e in embeddings]


def store_embeddings_batch(driver, batch: list[dict]):
    """Store embeddings in Neo4j."""
    query = """
    UNWIND $batch AS item
    MATCH (c:Concept {concept_id: item.concept_id})
    SET c.embedding = item.embedding
    """

    with driver.session() as session:
        session.run(query, batch=batch)


def embed_concepts(driver, concepts: list[dict], model):
    """Generate and store embeddings for concepts."""
    logger.info(f"Generating embeddings for {len(concepts):,} concepts...")

    total = len(concepts)
    embedded = 0
    start_time = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = concepts[i:i + BATCH_SIZE]
        names = [c["name"] for c in batch]

        # Generate embeddings
        embeddings = generate_embeddings(names, model)

        # Prepare batch for storage
        store_batch = [
            {"concept_id": batch[j]["concept_id"], "embedding": embeddings[j]}
            for j in range(len(batch))
        ]

        # Store in Neo4j
        store_embeddings_batch(driver, store_batch)

        embedded += len(batch)

        if embedded % 5000 == 0 or embedded == total:
            elapsed = time.time() - start_time
            rate = embedded / elapsed if elapsed > 0 else 0
            eta = (total - embedded) / rate if rate > 0 else 0
            logger.info(f"Embedded {embedded:,}/{total:,} concepts ({rate:.0f}/sec, ETA: {eta:.0f}s)")

    return embedded


def verify_embeddings(driver):
    """Verify embeddings were stored correctly."""
    with driver.session() as session:
        # Count concepts with embeddings
        result = session.run("""
            MATCH (c:Concept)
            WHERE c.embedding IS NOT NULL
            RETURN count(c) as count
        """)
        count = result.single()["count"]
        logger.info(f"Total concepts with embeddings: {count:,}")

        # Count by domain
        result = session.run("""
            MATCH (c:Concept)
            WHERE c.embedding IS NOT NULL
            RETURN c.domain_id as domain, count(c) as count
            ORDER BY count DESC
            LIMIT 10
        """)
        logger.info("Embeddings by domain:")
        for record in result:
            logger.info(f"  {record['domain']}: {record['count']:,}")

        return count


def test_vector_search(driver, model, query: str = "diabetes mellitus"):
    """Test vector similarity search."""
    logger.info(f"Testing vector search with query: '{query}'")

    # Generate query embedding
    query_embedding = model.encode(query, convert_to_numpy=True).tolist()

    with driver.session() as session:
        # Use Neo4j vector search
        result = session.run("""
            CALL db.index.vector.queryNodes('concept_embedding', 10, $embedding)
            YIELD node, score
            RETURN node.concept_id as concept_id, node.name as name,
                   node.domain_id as domain, score
            ORDER BY score DESC
        """, embedding=query_embedding)

        logger.info("Top 10 similar concepts:")
        for record in result:
            logger.info(f"  [{record['score']:.3f}] {record['name']} ({record['domain']})")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Neo4j Vector Index Creation for OMOP Concepts")
    logger.info("=" * 60)

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # Verify connection
        driver.verify_connectivity()
        logger.info(f"Connected to Neo4j at {NEO4J_URI}")

        # Create vector index
        if not create_vector_index(driver):
            logger.error("Failed to create vector index, aborting")
            return 1

        # Load embedding model
        logger.info("Loading sentence-transformers model...")
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded: all-MiniLM-L6-v2 (384 dimensions)")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            return 1

        # Get high-priority concepts
        concepts = get_high_priority_concepts(driver, MAX_CONCEPTS)

        if not concepts:
            logger.warning("No concepts found to embed")
            return 0

        # Generate and store embeddings
        embedded = embed_concepts(driver, concepts, model)
        logger.info(f"Successfully embedded {embedded:,} concepts")

        # Verify
        verify_embeddings(driver)

        # Test search
        test_vector_search(driver, model, "diabetes mellitus")
        test_vector_search(driver, model, "hypertension")
        test_vector_search(driver, model, "aspirin")

        logger.info("=" * 60)
        logger.info("Vector index creation complete!")
        logger.info("=" * 60)

        return 0

    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
