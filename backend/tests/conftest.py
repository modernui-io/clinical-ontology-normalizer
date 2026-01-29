"""Pytest configuration and fixtures for backend tests.

This module provides shared fixtures for all test modules:
- Test database setup with SQLite in-memory
- FastAPI test client (sync and async)
- Mock services for external dependencies
- Test data factories for creating test objects
"""

import json
import os
import sys
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if sys.version_info < (3, 10):
    pytest.skip("Backend tests require Python 3.10+ for type syntax.", allow_module_level=True)

from app.core.database import Base, get_db
from app.main import app
from app.services.vocabulary import reset_vocabulary_singleton

# =============================================================================
# SQLite Type Compatibility for PostgreSQL-specific Types
# =============================================================================

from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


@compiles(PG_ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


# =============================================================================
# Singleton Reset Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_vocab_singleton() -> None:
    """Reset the vocabulary singleton before each test module.

    This ensures clean state for tests and prevents test interference.
    The singleton is automatically reset at the start of each test.
    """
    reset_vocabulary_singleton()
    yield
    # Also reset after test to leave clean state
    reset_vocabulary_singleton()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="function")
async def async_engine():
    """Create an async SQLite in-memory engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
def sync_engine():
    """Create a sync SQLite in-memory engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create an async database session for testing."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
def sync_session(sync_engine) -> Generator[Session, None, None]:
    """Create a sync database session for testing."""
    sync_session_factory = sessionmaker(
        bind=sync_engine,
        autocommit=False,
        autoflush=False,
    )

    session = sync_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session.

    Returns a mock AsyncSession that can be used in place of a real database.
    """
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    return session


# =============================================================================
# Job Queue Fixtures
# =============================================================================


@pytest.fixture
def mock_enqueue_job() -> MagicMock:
    """Create a mock enqueue_job function.

    Returns a mock that can be used to verify job enqueueing.
    """
    mock_job = MagicMock()
    mock_job.id = "mock-job-id"
    return MagicMock(return_value=mock_job)


# =============================================================================
# FastAPI Test Client Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def override_get_db(async_session):
    """Override the database dependency for testing."""
    async def _override_get_db():
        yield async_session

    return _override_get_db


@pytest.fixture(scope="function")
def test_app(override_get_db) -> FastAPI:
    """Create a test FastAPI application with overridden dependencies."""
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_client(test_app) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""
    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
async def client_with_mock_db(
    mock_db_session: MagicMock,
    mock_enqueue_job: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with mocked database and queue.

    This allows testing API endpoints without a real database or Redis connection.
    """

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test/api/v1",
        ) as ac:
            yield ac

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client without database mocking.

    Use this for endpoints that don't require database access.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# Mock Service Fixtures
# =============================================================================


@pytest.fixture
def mock_vocabulary_service():
    """Mock vocabulary service for testing without loading full vocabulary."""
    with patch("app.services.vocabulary.get_vocabulary_service") as mock:
        service = MagicMock()
        service.load.return_value = None
        service.search.return_value = []
        service.get_by_id.return_value = None
        service.get_stats.return_value = {
            "loaded": True,
            "concept_count": 100,
            "term_count": 500,
            "load_time_ms": 10.0,
        }
        service.concepts = []
        service.concept_count = 100
        mock.return_value = service
        yield service


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch("app.core.redis.get_redis") as mock:
        redis_client = MagicMock()
        redis_client.ping.return_value = True
        redis_client.get.return_value = None
        redis_client.set.return_value = True
        redis_client.delete.return_value = 1
        mock.return_value = redis_client
        yield redis_client


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j graph database service for testing."""
    with patch("app.services.graph_database_service.get_graph_database_service") as mock:
        service = MagicMock()
        health_result = MagicMock()
        health_result.status.value = "mock_mode"
        health_result.latency_ms = 1.0
        health_result.server_version = "5.0.0"
        health_result.database = "neo4j"
        health_result.error_message = None
        service.health_check.return_value = health_result
        mock.return_value = service
        yield service


@pytest.fixture
def mock_kafka():
    """Mock Kafka service for testing."""
    with patch("app.services.kafka_service.get_kafka_service") as mock:
        service = MagicMock()
        health = MagicMock()
        health.connected = True
        health.latency_ms = 1.0
        health.broker_count = 3
        health.topic_count = 10
        health.error_message = None
        service.get_health.return_value = health
        service.is_mock_mode.return_value = True
        mock.return_value = service
        yield service


@pytest.fixture
def mock_all_external_services(mock_vocabulary_service, mock_redis, mock_neo4j, mock_kafka):
    """Convenience fixture to mock all external services."""
    return {
        "vocabulary": mock_vocabulary_service,
        "redis": mock_redis,
        "neo4j": mock_neo4j,
        "kafka": mock_kafka,
    }


# =============================================================================
# Test Data Factories
# =============================================================================


class TestDataFactory:
    """Factory for creating test data objects."""

    @staticmethod
    def create_patient_id() -> str:
        """Generate a test patient ID."""
        return f"P{str(uuid4())[:8].upper()}"

    @staticmethod
    def create_document_id() -> str:
        """Generate a test document ID."""
        return str(uuid4())

    @staticmethod
    def create_job_id() -> str:
        """Generate a test job ID."""
        return str(uuid4())

    @staticmethod
    def create_document_data(
        patient_id: str | None = None,
        note_type: str = "Progress Note",
        text: str | None = None,
    ) -> dict[str, Any]:
        """Create test document data."""
        return {
            "patient_id": patient_id or TestDataFactory.create_patient_id(),
            "note_type": note_type,
            "text": text or "Patient presents with diabetes mellitus type 2. Blood pressure 120/80.",
            "metadata": {"source": "test"},
        }

    @staticmethod
    def create_clinical_fact_data(
        patient_id: str | None = None,
        domain: str = "Condition",
        concept_name: str = "Type 2 diabetes mellitus",
    ) -> dict[str, Any]:
        """Create test clinical fact data."""
        return {
            "id": str(uuid4()),
            "patient_id": patient_id or TestDataFactory.create_patient_id(),
            "domain": domain,
            "omop_concept_id": 201826,
            "concept_name": concept_name,
            "assertion": "present",
            "temporality": "current",
            "experiencer": "patient",
            "confidence": 0.95,
            "value": None,
            "unit": None,
            "start_date": None,
            "end_date": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_mention_data(
        document_id: str | None = None,
        text: str = "diabetes",
    ) -> dict[str, Any]:
        """Create test mention data."""
        return {
            "id": str(uuid4()),
            "document_id": document_id or TestDataFactory.create_document_id(),
            "text": text,
            "start_offset": 0,
            "end_offset": len(text),
            "lexical_variant": text.lower(),
            "section": "Assessment",
            "assertion": "present",
            "temporality": "current",
            "experiencer": "patient",
            "confidence": 0.9,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_graph_node_data(
        patient_id: str | None = None,
        node_type: str = "condition",
        label: str = "Diabetes",
    ) -> dict[str, Any]:
        """Create test graph node data."""
        return {
            "id": str(uuid4()),
            "patient_id": patient_id or TestDataFactory.create_patient_id(),
            "node_type": node_type,
            "omop_concept_id": 201826,
            "label": label,
            "properties": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


@pytest.fixture
def factory():
    """Provide access to the test data factory."""
    return TestDataFactory


@pytest.fixture
def sample_patient_id():
    """Provide a sample patient ID for tests."""
    return "P001"


@pytest.fixture
def sample_document_data(sample_patient_id) -> dict[str, Any]:
    """Provide sample document data for tests."""
    return TestDataFactory.create_document_data(patient_id=sample_patient_id)


@pytest.fixture
def sample_clinical_text() -> str:
    """Provide sample clinical text for NLP testing."""
    return """
    CHIEF COMPLAINT: Follow-up for diabetes management.

    HISTORY OF PRESENT ILLNESS:
    The patient is a 55-year-old male with type 2 diabetes mellitus diagnosed 5 years ago.
    He reports good compliance with metformin 1000mg twice daily.
    Blood glucose readings at home have been between 110-140 mg/dL fasting.
    He denies hypoglycemia, polyuria, or polydipsia.

    PAST MEDICAL HISTORY:
    1. Type 2 diabetes mellitus
    2. Hypertension, controlled on lisinopril
    3. Hyperlipidemia on atorvastatin

    MEDICATIONS:
    1. Metformin 1000mg BID
    2. Lisinopril 20mg daily
    3. Atorvastatin 40mg daily

    VITAL SIGNS:
    Blood pressure: 128/82 mmHg
    Heart rate: 72 bpm
    Temperature: 98.6 F
    Weight: 185 lbs

    LABORATORY:
    HbA1c: 7.2% (3 months ago)
    Fasting glucose: 126 mg/dL
    Creatinine: 0.9 mg/dL
    eGFR: >60 mL/min/1.73m2

    ASSESSMENT AND PLAN:
    1. Type 2 diabetes mellitus - Adequate control. Continue current regimen.
       Repeat HbA1c in 3 months. Goal <7%.
    2. Hypertension - Well controlled. Continue lisinopril.
    3. Hyperlipidemia - Continue atorvastatin. Check lipid panel at next visit.
    """


# =============================================================================
# Fixture Directory and File Helpers
# =============================================================================


@pytest.fixture
def fixtures_dir() -> Path:
    """Provide path to the fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def load_fixture(fixtures_dir):
    """Provide a helper function to load JSON fixtures."""
    def _load_fixture(filename: str) -> Any:
        filepath = fixtures_dir / filename
        if not filepath.exists():
            pytest.skip(f"Fixture file not found: {filepath}")
        with open(filepath) as f:
            return json.load(f)

    return _load_fixture


# =============================================================================
# Performance Helpers
# =============================================================================


@pytest.fixture
def performance_threshold():
    """Provide performance thresholds for API response times."""
    return {
        "health_check_ms": 100,
        "simple_query_ms": 500,
        "complex_query_ms": 2000,
        "document_processing_ms": 5000,
    }


# =============================================================================
# Authentication Fixtures
# =============================================================================


@pytest.fixture
def api_key_header():
    """Provide API key header for authenticated requests."""
    return {"X-API-Key": "test-api-key-12345"}


@pytest.fixture
def auth_headers(api_key_header):
    """Provide full authentication headers."""
    return {
        **api_key_header,
        "Content-Type": "application/json",
    }
