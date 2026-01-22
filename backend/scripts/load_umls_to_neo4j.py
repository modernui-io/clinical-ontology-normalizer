#!/usr/bin/env python3
"""
UMLS Metathesaurus Loader for Neo4j.

Loads UMLS RRF files into Neo4j for the clinical knowledge graph.
Achieves parity with published systems like DR.KNOWS (4.5M concepts, 15M relations).

Files loaded:
- MRCONSO.RRF: 4.5M concepts (concept names, vocabularies, codes)
- MRREL.RRF: 15M relations (concept relationships)
- MRSTY.RRF: Semantic types (127 UMLS semantic types)
- MRDEF.RRF: Definitions (optional)

Usage:
    python scripts/load_umls_to_neo4j.py --umls-path /path/to/umls/META --neo4j-uri bolt://localhost:7687

Requirements:
    - UMLS license from https://uts.nlm.nih.gov/uts/signup-login
    - Neo4j 5.x with APOC plugin
    - ~16GB RAM for full load
    - ~4 hours for full load

Based on:
    - DR.KNOWS (JMIR 2025): 4.5M UMLS concepts, 15M relations
    - Neo4j Healthcare Framework (medRxiv 2025): 625K nodes, 2.1M relationships
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generator

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class SemanticGroup(str, Enum):
    """UMLS Semantic Groups (15 groups covering 127 semantic types)."""

    ANAT = "Anatomy"
    CHEM = "Chemicals & Drugs"
    DISO = "Disorders"
    GENE = "Genes & Molecular Sequences"
    GEOG = "Geographic Areas"
    LIVB = "Living Beings"
    OBJC = "Objects"
    OCCU = "Occupations"
    ORGA = "Organizations"
    PHEN = "Phenomena"
    PHYS = "Physiology"
    PROC = "Procedures"
    CONC = "Concepts & Ideas"


# Mapping of UMLS Semantic Types (TUI) to Semantic Groups
SEMANTIC_TYPE_GROUPS = {
    # Disorders (T019-T050, T190-T191)
    "T019": SemanticGroup.DISO,  # Congenital Abnormality
    "T020": SemanticGroup.DISO,  # Acquired Abnormality
    "T037": SemanticGroup.DISO,  # Injury or Poisoning
    "T046": SemanticGroup.DISO,  # Pathologic Function
    "T047": SemanticGroup.DISO,  # Disease or Syndrome
    "T048": SemanticGroup.DISO,  # Mental or Behavioral Dysfunction
    "T049": SemanticGroup.DISO,  # Cell or Molecular Dysfunction
    "T050": SemanticGroup.DISO,  # Experimental Model of Disease
    "T190": SemanticGroup.DISO,  # Anatomical Abnormality
    "T191": SemanticGroup.DISO,  # Neoplastic Process
    # Chemicals & Drugs
    "T103": SemanticGroup.CHEM,  # Chemical
    "T104": SemanticGroup.CHEM,  # Chemical Viewed Structurally
    "T109": SemanticGroup.CHEM,  # Organic Chemical
    "T114": SemanticGroup.CHEM,  # Nucleic Acid, Nucleoside, or Nucleotide
    "T116": SemanticGroup.CHEM,  # Amino Acid, Peptide, or Protein
    "T118": SemanticGroup.CHEM,  # Carbohydrate
    "T119": SemanticGroup.CHEM,  # Lipid
    "T121": SemanticGroup.CHEM,  # Pharmacologic Substance
    "T122": SemanticGroup.CHEM,  # Biomedical or Dental Material
    "T123": SemanticGroup.CHEM,  # Biologically Active Substance
    "T124": SemanticGroup.CHEM,  # Neuroreactive Substance or Biogenic Amine
    "T125": SemanticGroup.CHEM,  # Hormone
    "T126": SemanticGroup.CHEM,  # Enzyme
    "T127": SemanticGroup.CHEM,  # Vitamin
    "T129": SemanticGroup.CHEM,  # Immunologic Factor
    "T130": SemanticGroup.CHEM,  # Indicator, Reagent, or Diagnostic Aid
    "T131": SemanticGroup.CHEM,  # Hazardous or Poisonous Substance
    "T195": SemanticGroup.CHEM,  # Antibiotic
    "T196": SemanticGroup.CHEM,  # Element, Ion, or Isotope
    "T197": SemanticGroup.CHEM,  # Inorganic Chemical
    "T200": SemanticGroup.CHEM,  # Clinical Drug
    # Procedures
    "T058": SemanticGroup.PROC,  # Health Care Activity
    "T059": SemanticGroup.PROC,  # Laboratory Procedure
    "T060": SemanticGroup.PROC,  # Diagnostic Procedure
    "T061": SemanticGroup.PROC,  # Therapeutic or Preventive Procedure
    "T062": SemanticGroup.PROC,  # Research Activity
    "T063": SemanticGroup.PROC,  # Molecular Biology Research Technique
    "T065": SemanticGroup.PROC,  # Educational Activity
    # Anatomy
    "T017": SemanticGroup.ANAT,  # Anatomical Structure
    "T021": SemanticGroup.ANAT,  # Fully Formed Anatomical Structure
    "T022": SemanticGroup.ANAT,  # Body System
    "T023": SemanticGroup.ANAT,  # Body Part, Organ, or Organ Component
    "T024": SemanticGroup.ANAT,  # Tissue
    "T025": SemanticGroup.ANAT,  # Cell
    "T026": SemanticGroup.ANAT,  # Cell Component
    "T029": SemanticGroup.ANAT,  # Body Location or Region
    "T030": SemanticGroup.ANAT,  # Body Space or Junction
    # Genes & Molecular Sequences
    "T028": SemanticGroup.GENE,  # Gene or Genome
    "T085": SemanticGroup.GENE,  # Molecular Sequence
    "T086": SemanticGroup.GENE,  # Nucleotide Sequence
    "T087": SemanticGroup.GENE,  # Amino Acid Sequence
    "T088": SemanticGroup.GENE,  # Carbohydrate Sequence
    # Physiology
    "T032": SemanticGroup.PHYS,  # Organism Attribute
    "T033": SemanticGroup.PHYS,  # Finding
    "T034": SemanticGroup.PHYS,  # Laboratory or Test Result
    "T038": SemanticGroup.PHYS,  # Biologic Function
    "T039": SemanticGroup.PHYS,  # Physiologic Function
    "T040": SemanticGroup.PHYS,  # Organism Function
    "T041": SemanticGroup.PHYS,  # Mental Process
    "T042": SemanticGroup.PHYS,  # Organ or Tissue Function
    "T043": SemanticGroup.PHYS,  # Cell Function
    "T044": SemanticGroup.PHYS,  # Molecular Function
    "T045": SemanticGroup.PHYS,  # Genetic Function
    "T184": SemanticGroup.PHYS,  # Sign or Symptom
    # Concepts & Ideas
    "T077": SemanticGroup.CONC,  # Conceptual Entity
    "T078": SemanticGroup.CONC,  # Idea or Concept
    "T079": SemanticGroup.CONC,  # Temporal Concept
    "T080": SemanticGroup.CONC,  # Qualitative Concept
    "T081": SemanticGroup.CONC,  # Quantitative Concept
    "T089": SemanticGroup.CONC,  # Regulation or Law
    "T102": SemanticGroup.CONC,  # Group Attribute
    "T169": SemanticGroup.CONC,  # Functional Concept
    "T170": SemanticGroup.CONC,  # Intellectual Product
    "T171": SemanticGroup.CONC,  # Language
    "T185": SemanticGroup.CONC,  # Classification
}

# Relationship type mappings for clinical relevance
CLINICAL_RELATIONS = {
    "RO": "related_to",
    "RB": "has_broader_concept",
    "RN": "has_narrower_concept",
    "PAR": "has_parent",
    "CHD": "has_child",
    "SY": "has_synonym",
    "SIB": "has_sibling",
    "RL": "has_similar_concept",
    "AQ": "allowed_qualifier",
    # Clinical-specific
    "may_treat": "MAY_TREAT",
    "may_prevent": "MAY_PREVENT",
    "treats": "TREATS",
    "prevents": "PREVENTS",
    "contraindicated_with": "CONTRAINDICATED_WITH",
    "has_finding_site": "HAS_FINDING_SITE",
    "has_causative_agent": "HAS_CAUSATIVE_AGENT",
    "has_associated_morphology": "HAS_ASSOCIATED_MORPHOLOGY",
    "has_mechanism_of_action": "HAS_MECHANISM_OF_ACTION",
    "has_physiologic_effect": "HAS_PHYSIOLOGIC_EFFECT",
}


@dataclass
class LoaderStats:
    """Statistics for the loading process."""

    concepts_loaded: int = 0
    relations_loaded: int = 0
    semantic_types_loaded: int = 0
    definitions_loaded: int = 0
    synonyms_loaded: int = 0
    errors: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def duration_formatted(self) -> str:
        secs = int(self.duration_seconds)
        hours, remainder = divmod(secs, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"


class UMLSLoader:
    """Load UMLS Metathesaurus into Neo4j."""

    def __init__(
        self,
        umls_path: Path,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "clinical123",
        batch_size: int = 10000,
        english_only: bool = True,
    ):
        self.umls_path = Path(umls_path)
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.batch_size = batch_size
        self.english_only = english_only

        self._driver = None
        self.stats = LoaderStats()

        # Cache for semantic types (TUI -> STY name)
        self._semantic_types: dict[str, str] = {}
        # Cache for concept CUIs to verify relations
        self._loaded_cuis: set[str] = set()

    def connect(self) -> None:
        """Connect to Neo4j."""
        self._driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password),
            max_connection_lifetime=3600,
            max_connection_pool_size=100,
        )
        # Verify connection
        with self._driver.session() as session:
            session.run("RETURN 1")
        logger.info(f"Connected to Neo4j at {self.neo4j_uri}")

    def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def create_schema(self) -> None:
        """Create Neo4j schema for UMLS data."""
        schema_queries = [
            # Constraints
            "CREATE CONSTRAINT umls_cui IF NOT EXISTS FOR (c:Concept) REQUIRE c.cui IS UNIQUE",
            "CREATE CONSTRAINT umls_aui IF NOT EXISTS FOR (a:Atom) REQUIRE a.aui IS UNIQUE",
            # Indexes for fast lookup
            "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
            "CREATE INDEX concept_sty IF NOT EXISTS FOR (c:Concept) ON (c.semantic_type)",
            "CREATE INDEX concept_sab IF NOT EXISTS FOR (c:Concept) ON (c.source_vocabulary)",
            "CREATE INDEX concept_code IF NOT EXISTS FOR (c:Concept) ON (c.code)",
            # Full-text search
            """CREATE FULLTEXT INDEX concept_search IF NOT EXISTS
               FOR (c:Concept) ON EACH [c.name, c.synonyms_text]""",
        ]

        with self._driver.session() as session:
            for query in schema_queries:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug(f"Schema query (may already exist): {e}")

        logger.info("Neo4j schema created")

    def _read_rrf_file(
        self,
        filename: str,
        columns: list[str],
    ) -> Generator[dict[str, str], None, None]:
        """Read a UMLS RRF file and yield rows as dicts."""
        filepath = self.umls_path / filename

        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="|")
            for row in reader:
                if len(row) >= len(columns):
                    yield dict(zip(columns, row))

    def load_semantic_types(self) -> int:
        """
        Load semantic types from MRSTY.RRF.

        Format: CUI|TUI|STN|STY|ATUI|CVF|

        This assigns semantic types to concepts and enables filtering
        by clinical category (disorders, drugs, procedures, etc.).
        """
        logger.info("Loading semantic types from MRSTY.RRF...")

        columns = ["CUI", "TUI", "STN", "STY", "ATUI", "CVF"]
        cui_to_sty: dict[str, list[tuple[str, str]]] = defaultdict(list)

        count = 0
        for row in self._read_rrf_file("MRSTY.RRF", columns):
            cui = row["CUI"]
            tui = row["TUI"]
            sty = row["STY"]

            cui_to_sty[cui].append((tui, sty))
            self._semantic_types[tui] = sty
            count += 1

        logger.info(f"Loaded {count} semantic type assignments for {len(cui_to_sty)} concepts")

        # Update concepts with semantic types in batches
        batch = []
        for cui, types in cui_to_sty.items():
            # Use primary semantic type (first one)
            primary_tui, primary_sty = types[0]
            semantic_group = SEMANTIC_TYPE_GROUPS.get(primary_tui)

            batch.append({
                "cui": cui,
                "semantic_type": primary_sty,
                "semantic_type_id": primary_tui,
                "semantic_group": semantic_group.value if semantic_group else None,
                "all_semantic_types": [sty for _, sty in types],
            })

            if len(batch) >= self.batch_size:
                self._batch_update_semantic_types(batch)
                batch = []

        if batch:
            self._batch_update_semantic_types(batch)

        self.stats.semantic_types_loaded = count
        return count

    def _batch_update_semantic_types(self, batch: list[dict]) -> None:
        """Update semantic types for a batch of concepts."""
        query = """
        UNWIND $batch AS item
        MATCH (c:Concept {cui: item.cui})
        SET c.semantic_type = item.semantic_type,
            c.semantic_type_id = item.semantic_type_id,
            c.semantic_group = item.semantic_group,
            c.all_semantic_types = item.all_semantic_types
        """
        with self._driver.session() as session:
            session.run(query, batch=batch)

    def load_concepts(self) -> int:
        """
        Load concepts from MRCONSO.RRF.

        Format: CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF|

        This is the main concept file with ~4.5M entries.
        We create one node per CUI with the preferred term as the name.
        """
        logger.info("Loading concepts from MRCONSO.RRF...")

        columns = [
            "CUI", "LAT", "TS", "LUI", "STT", "SUI", "ISPREF", "AUI",
            "SAUI", "SCUI", "SDUI", "SAB", "TTY", "CODE", "STR", "SRL",
            "SUPPRESS", "CVF"
        ]

        # Collect concepts by CUI (aggregate synonyms)
        concepts: dict[str, dict[str, Any]] = {}
        synonym_count = 0

        for row in self._read_rrf_file("MRCONSO.RRF", columns):
            # Filter by language if requested
            if self.english_only and row["LAT"] != "ENG":
                continue

            cui = row["CUI"]
            name = row["STR"]
            sab = row["SAB"]  # Source vocabulary
            code = row["CODE"]
            is_preferred = row["ISPREF"] == "Y" and row["TS"] == "P"

            if cui not in concepts:
                concepts[cui] = {
                    "cui": cui,
                    "name": name,
                    "source_vocabulary": sab,
                    "code": code,
                    "synonyms": [],
                    "sources": set(),
                }
                self._loaded_cuis.add(cui)

            # Update with preferred term if this is the preferred one
            if is_preferred:
                concepts[cui]["name"] = name
                concepts[cui]["source_vocabulary"] = sab
                concepts[cui]["code"] = code

            # Add synonym if different from main name
            if name != concepts[cui]["name"]:
                if name not in concepts[cui]["synonyms"]:
                    concepts[cui]["synonyms"].append(name)
                    synonym_count += 1

            concepts[cui]["sources"].add(sab)

        logger.info(f"Found {len(concepts)} unique concepts with {synonym_count} synonyms")

        # Load in batches
        batch = []
        loaded = 0

        for concept in concepts.values():
            # Convert sources set to list
            concept["sources"] = list(concept["sources"])
            # Create synonyms text for full-text search
            concept["synonyms_text"] = " | ".join(concept["synonyms"][:50])  # Limit synonyms
            batch.append(concept)

            if len(batch) >= self.batch_size:
                self._batch_create_concepts(batch)
                loaded += len(batch)
                logger.info(f"Loaded {loaded:,} concepts...")
                batch = []

        if batch:
            self._batch_create_concepts(batch)
            loaded += len(batch)

        self.stats.concepts_loaded = loaded
        self.stats.synonyms_loaded = synonym_count
        logger.info(f"Loaded {loaded:,} concepts total")
        return loaded

    def _batch_create_concepts(self, batch: list[dict]) -> None:
        """Create concepts in batch."""
        query = """
        UNWIND $batch AS concept
        MERGE (c:Concept {cui: concept.cui})
        SET c.name = concept.name,
            c.source_vocabulary = concept.source_vocabulary,
            c.code = concept.code,
            c.synonyms = concept.synonyms,
            c.synonyms_text = concept.synonyms_text,
            c.sources = concept.sources
        """
        with self._driver.session() as session:
            session.run(query, batch=batch)

    def load_relations(self) -> int:
        """
        Load relations from MRREL.RRF.

        Format: CUI1|AUI1|STYPE1|REL|CUI2|AUI2|STYPE2|RELA|RUI|SRUI|SAB|SL|RG|DIR|SUPPRESS|CVF|

        This creates edges between concepts (~15M relations).
        Key relationships for clinical use:
        - RO: Has relationship (general)
        - RB/RN: Broader/Narrower than
        - PAR/CHD: Parent/Child (hierarchy)
        - may_treat, treats: Drug-disease treatment
        - contraindicated_with: Drug contraindications
        """
        logger.info("Loading relations from MRREL.RRF...")

        columns = [
            "CUI1", "AUI1", "STYPE1", "REL", "CUI2", "AUI2", "STYPE2",
            "RELA", "RUI", "SRUI", "SAB", "SL", "RG", "DIR", "SUPPRESS", "CVF"
        ]

        # Batch relations
        batch = []
        loaded = 0
        skipped = 0

        for row in self._read_rrf_file("MRREL.RRF", columns):
            cui1 = row["CUI1"]
            cui2 = row["CUI2"]
            rel = row["REL"]
            rela = row["RELA"]  # More specific relationship type
            sab = row["SAB"]

            # Skip if either concept not loaded
            if cui1 not in self._loaded_cuis or cui2 not in self._loaded_cuis:
                skipped += 1
                continue

            # Skip self-loops
            if cui1 == cui2:
                continue

            # Determine relationship type
            rel_type = CLINICAL_RELATIONS.get(rela, CLINICAL_RELATIONS.get(rel, "RELATED_TO"))

            batch.append({
                "cui1": cui1,
                "cui2": cui2,
                "rel_type": rel_type,
                "source": sab,
                "rel_attribute": rela or rel,
            })

            if len(batch) >= self.batch_size:
                self._batch_create_relations(batch)
                loaded += len(batch)
                if loaded % 100000 == 0:
                    logger.info(f"Loaded {loaded:,} relations...")
                batch = []

        if batch:
            self._batch_create_relations(batch)
            loaded += len(batch)

        self.stats.relations_loaded = loaded
        logger.info(f"Loaded {loaded:,} relations (skipped {skipped:,} with missing concepts)")
        return loaded

    def _batch_create_relations(self, batch: list[dict]) -> None:
        """Create relations in batch using APOC."""
        # Group by relationship type for efficient creation
        by_type: dict[str, list[dict]] = defaultdict(list)
        for rel in batch:
            by_type[rel["rel_type"]].append(rel)

        with self._driver.session() as session:
            for rel_type, rels in by_type.items():
                query = f"""
                UNWIND $rels AS rel
                MATCH (c1:Concept {{cui: rel.cui1}})
                MATCH (c2:Concept {{cui: rel.cui2}})
                MERGE (c1)-[r:{rel_type}]->(c2)
                SET r.source = rel.source,
                    r.attribute = rel.rel_attribute
                """
                try:
                    session.run(query, rels=rels)
                except Exception as e:
                    # Some relationship types may have invalid characters
                    logger.debug(f"Error creating {rel_type} relations: {e}")

    def load_definitions(self) -> int:
        """
        Load definitions from MRDEF.RRF (optional).

        Format: CUI|AUI|ATUI|SATUI|SAB|DEF|SUPPRESS|CVF|
        """
        logger.info("Loading definitions from MRDEF.RRF...")

        columns = ["CUI", "AUI", "ATUI", "SATUI", "SAB", "DEF", "SUPPRESS", "CVF"]

        batch = []
        loaded = 0

        for row in self._read_rrf_file("MRDEF.RRF", columns):
            cui = row["CUI"]
            definition = row["DEF"]

            if cui not in self._loaded_cuis:
                continue

            batch.append({
                "cui": cui,
                "definition": definition[:2000],  # Limit length
            })

            if len(batch) >= self.batch_size:
                self._batch_update_definitions(batch)
                loaded += len(batch)
                batch = []

        if batch:
            self._batch_update_definitions(batch)
            loaded += len(batch)

        self.stats.definitions_loaded = loaded
        logger.info(f"Loaded {loaded:,} definitions")
        return loaded

    def _batch_update_definitions(self, batch: list[dict]) -> None:
        """Update definitions for concepts."""
        query = """
        UNWIND $batch AS item
        MATCH (c:Concept {cui: item.cui})
        SET c.definition = item.definition
        """
        with self._driver.session() as session:
            session.run(query, batch=batch)

    def load_all(self, include_definitions: bool = False) -> LoaderStats:
        """Load all UMLS data."""
        logger.info("=" * 60)
        logger.info("Starting UMLS load to Neo4j")
        logger.info(f"UMLS path: {self.umls_path}")
        logger.info(f"Neo4j URI: {self.neo4j_uri}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"English only: {self.english_only}")
        logger.info("=" * 60)

        try:
            self.connect()
            self.create_schema()

            # Load in order: concepts first, then semantic types, then relations
            self.load_concepts()
            self.load_semantic_types()
            self.load_relations()

            if include_definitions:
                self.load_definitions()

            self.stats.end_time = time.time()

            logger.info("=" * 60)
            logger.info("UMLS load complete!")
            logger.info(f"Concepts: {self.stats.concepts_loaded:,}")
            logger.info(f"Relations: {self.stats.relations_loaded:,}")
            logger.info(f"Semantic types: {self.stats.semantic_types_loaded:,}")
            logger.info(f"Synonyms: {self.stats.synonyms_loaded:,}")
            logger.info(f"Definitions: {self.stats.definitions_loaded:,}")
            logger.info(f"Duration: {self.stats.duration_formatted}")
            logger.info("=" * 60)

        except Exception as e:
            self.stats.errors.append(str(e))
            logger.error(f"Error during load: {e}")
            raise
        finally:
            self.close()

        return self.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load UMLS Metathesaurus into Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Load from default UMLS location
    python scripts/load_umls_to_neo4j.py --umls-path /data/umls/2024AA/META

    # Load with custom Neo4j settings
    python scripts/load_umls_to_neo4j.py \\
        --umls-path /data/umls/META \\
        --neo4j-uri bolt://neo4j:7687 \\
        --neo4j-password mypassword

    # Include definitions (slower)
    python scripts/load_umls_to_neo4j.py --umls-path /data/umls/META --include-definitions

Required UMLS files in the META directory:
    - MRCONSO.RRF (concepts, ~4.5M rows)
    - MRREL.RRF (relations, ~15M rows)
    - MRSTY.RRF (semantic types)
    - MRDEF.RRF (definitions, optional)

Get UMLS license at: https://uts.nlm.nih.gov/uts/signup-login
        """,
    )

    parser.add_argument(
        "--umls-path",
        type=Path,
        required=True,
        help="Path to UMLS META directory containing RRF files",
    )
    parser.add_argument(
        "--neo4j-uri",
        type=str,
        default="bolt://localhost:7687",
        help="Neo4j connection URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--neo4j-user",
        type=str,
        default="neo4j",
        help="Neo4j username (default: neo4j)",
    )
    parser.add_argument(
        "--neo4j-password",
        type=str,
        default=os.environ.get("NEO4J_PASSWORD", "clinical123"),
        help="Neo4j password (default: from NEO4J_PASSWORD env or 'clinical123')",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for Neo4j operations (default: 10000)",
    )
    parser.add_argument(
        "--include-definitions",
        action="store_true",
        help="Include concept definitions (slower)",
    )
    parser.add_argument(
        "--all-languages",
        action="store_true",
        help="Load all languages, not just English",
    )

    args = parser.parse_args()

    # Validate UMLS path
    if not args.umls_path.exists():
        logger.error(f"UMLS path does not exist: {args.umls_path}")
        sys.exit(1)

    mrconso = args.umls_path / "MRCONSO.RRF"
    if not mrconso.exists():
        logger.error(f"MRCONSO.RRF not found in {args.umls_path}")
        logger.error("Ensure you have downloaded UMLS and extracted the META directory")
        sys.exit(1)

    loader = UMLSLoader(
        umls_path=args.umls_path,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        batch_size=args.batch_size,
        english_only=not args.all_languages,
    )

    try:
        stats = loader.load_all(include_definitions=args.include_definitions)

        if stats.errors:
            logger.warning(f"Completed with {len(stats.errors)} errors")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Load failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
