"""Tests for the graph building background job.

Tests the decoupled graph building pipeline where document processing
enqueues a graph_building job instead of running inline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestBuildGraphForPatientJob:
    """Tests for build_graph_for_patient_job function."""

    @patch("app.jobs.graph_building.get_kg_cache_service")
    @patch("app.jobs.graph_building.get_sync_engine")
    @patch("app.jobs.graph_building.log_audit")
    def test_job_returns_success_dict(
        self, mock_audit, mock_engine, mock_cache
    ) -> None:
        """Test that the job returns a success dict with node/edge counts."""
        from app.services.graph_builder import GraphResult

        mock_session = MagicMock()
        mock_engine.return_value.connect = MagicMock()

        # Make Session() context manager return mock session
        with patch("app.jobs.graph_building.Session") as mock_session_cls:
            mock_session_instance = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(
                return_value=mock_session_instance
            )
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            # Mock the graph builder
            with patch(
                "app.jobs.graph_building.DatabaseGraphBuilderService"
            ) as mock_builder_cls:
                mock_builder = MagicMock()
                mock_builder.build_graph_for_patient.return_value = GraphResult(
                    patient_id="P001",
                    node_count=5,
                    edge_count=4,
                    nodes_created=3,
                    edges_created=2,
                )
                mock_builder_cls.return_value = mock_builder

                mock_cache_instance = MagicMock()
                mock_cache_instance.invalidate_patient.return_value = 1
                mock_cache.return_value = mock_cache_instance

                from app.jobs.graph_building import build_graph_for_patient_job

                result = build_graph_for_patient_job("P001")

        assert result["success"] is True
        assert result["patient_id"] == "P001"
        assert result["nodes_created"] == 3
        assert result["edges_created"] == 2

    @patch("app.jobs.graph_building.get_kg_cache_service")
    @patch("app.jobs.graph_building.get_sync_engine")
    @patch("app.jobs.graph_building.log_audit")
    def test_job_handles_errors_gracefully(
        self, mock_audit, mock_engine, mock_cache
    ) -> None:
        """Test that the job returns error dict on failure."""
        with patch("app.jobs.graph_building.Session") as mock_session_cls:
            mock_session_instance = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(
                return_value=mock_session_instance
            )
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            with patch(
                "app.jobs.graph_building.DatabaseGraphBuilderService"
            ) as mock_builder_cls:
                mock_builder = MagicMock()
                mock_builder.build_graph_for_patient.side_effect = RuntimeError(
                    "DB error"
                )
                mock_builder_cls.return_value = mock_builder

                from app.jobs.graph_building import build_graph_for_patient_job

                result = build_graph_for_patient_job("P001")

        assert result["success"] is False
        assert "error" in result

    @patch("app.jobs.graph_building.get_kg_cache_service")
    @patch("app.jobs.graph_building.get_sync_engine")
    @patch("app.jobs.graph_building.log_audit")
    def test_job_invalidates_cache_after_build(
        self, mock_audit, mock_engine, mock_cache
    ) -> None:
        """Test that KG cache is invalidated after graph build."""
        from app.services.graph_builder import GraphResult

        with patch("app.jobs.graph_building.Session") as mock_session_cls:
            mock_session_instance = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(
                return_value=mock_session_instance
            )
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            with patch(
                "app.jobs.graph_building.DatabaseGraphBuilderService"
            ) as mock_builder_cls:
                mock_builder = MagicMock()
                mock_builder.build_graph_for_patient.return_value = GraphResult(
                    patient_id="P001",
                    node_count=1,
                    edge_count=0,
                    nodes_created=1,
                    edges_created=0,
                )
                mock_builder_cls.return_value = mock_builder

                mock_cache_instance = MagicMock()
                mock_cache.return_value = mock_cache_instance

                from app.jobs.graph_building import build_graph_for_patient_job

                build_graph_for_patient_job("P001")

        mock_cache_instance.invalidate_patient.assert_called_once_with("P001")

    @patch("app.jobs.graph_building.get_kg_cache_service")
    @patch("app.jobs.graph_building.get_sync_engine")
    @patch("app.jobs.graph_building.log_audit")
    def test_job_audits_start_and_completion(
        self, mock_audit, mock_engine, mock_cache
    ) -> None:
        """Test that audit events are logged for start and completion."""
        from app.services.graph_builder import GraphResult

        with patch("app.jobs.graph_building.Session") as mock_session_cls:
            mock_session_instance = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(
                return_value=mock_session_instance
            )
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            with patch(
                "app.jobs.graph_building.DatabaseGraphBuilderService"
            ) as mock_builder_cls:
                mock_builder = MagicMock()
                mock_builder.build_graph_for_patient.return_value = GraphResult(
                    patient_id="P001",
                    node_count=1,
                    edge_count=0,
                    nodes_created=1,
                    edges_created=0,
                )
                mock_builder_cls.return_value = mock_builder

                mock_cache_instance = MagicMock()
                mock_cache.return_value = mock_cache_instance

                from app.jobs.graph_building import build_graph_for_patient_job

                build_graph_for_patient_job("P001")

        # Should have at least 2 audit calls (start + completed)
        assert mock_audit.call_count >= 2


class TestDocumentProcessingDecoupling:
    """Tests for the decoupled document processing -> graph build pipeline."""

    def test_graph_building_job_is_importable(self) -> None:
        """Test that the job function can be imported."""
        from app.jobs.graph_building import build_graph_for_patient_job

        assert callable(build_graph_for_patient_job)

    def test_job_exported_from_init(self) -> None:
        """Test that the job is exported from the jobs package."""
        from app.jobs import build_graph_for_patient_job

        assert callable(build_graph_for_patient_job)


class TestGraphBuildingQueue:
    """Tests for the graph_building queue configuration."""

    def test_graph_building_queue_name_exists(self) -> None:
        """Test that graph_building queue name is defined."""
        from app.core.queue import QUEUE_NAMES

        assert "graph" in QUEUE_NAMES
        assert QUEUE_NAMES["graph"] == "graph_building"

    def test_get_graph_queue_function_exists(self) -> None:
        """Test that get_graph_queue helper exists."""
        from app.core.queue import get_graph_queue

        assert callable(get_graph_queue)
