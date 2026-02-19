"""Unit tests for MIMIC-IV-Note ingestion service."""

from __future__ import annotations

import pytest

from app.schemas.mimic import MimicImportConfig
from app.services.mimic_ingestion import MimicIngestionService, REQUIRED_COLUMNS

# Sample CSV data
VALID_CSV = """note_id,subject_id,hadm_id,note_type,text
10001,100,200001,Discharge Summary,"Patient admitted with chest pain. History of hypertension and diabetes mellitus type 2."
10002,100,200001,Discharge Summary,"Follow-up note: Blood pressure controlled on lisinopril 10mg daily."
10003,101,200002,Discharge Summary,"72-year-old male presenting with acute myocardial infarction."
10004,102,200003,Discharge Summary,"Admission for pneumonia. Started on azithromycin and ceftriaxone."
10005,103,200004,Discharge Summary,"Patient with COPD exacerbation. Treated with bronchodilators and corticosteroids."
"""

MISSING_COLUMNS_CSV = """note_id,subject_id,text
10001,100,"Some text"
"""

EMPTY_CSV = ""

HEADER_ONLY_CSV = """note_id,subject_id,hadm_id,note_type,text
"""

EMPTY_FIELD_CSV = """note_id,subject_id,hadm_id,note_type,text
10001,,200001,Discharge Summary,"Some text"
"""


class TestMimicIngestionServiceValidation:
    """Tests for CSV validation logic."""

    def setup_method(self) -> None:
        self.service = MimicIngestionService()

    def test_validate_valid_csv(self) -> None:
        result = self.service.validate_csv(VALID_CSV)
        assert result.valid is True
        assert result.total_rows == 5
        assert set(REQUIRED_COLUMNS).issubset(set(result.columns_found))
        assert result.columns_missing == []
        assert len(result.errors) == 0

    def test_validate_missing_columns(self) -> None:
        result = self.service.validate_csv(MISSING_COLUMNS_CSV)
        assert result.valid is False
        assert "hadm_id" in result.columns_missing
        assert "note_type" in result.columns_missing
        assert len(result.errors) > 0

    def test_validate_empty_csv(self) -> None:
        result = self.service.validate_csv(EMPTY_CSV)
        assert result.valid is False
        assert result.total_rows == 0

    def test_validate_header_only_csv(self) -> None:
        result = self.service.validate_csv(HEADER_ONLY_CSV)
        assert result.valid is True
        assert result.total_rows == 0

    def test_validate_empty_field(self) -> None:
        result = self.service.validate_csv(EMPTY_FIELD_CSV)
        assert result.valid is False
        assert any("empty value" in e for e in result.errors)

    def test_validate_sample_rows_limited(self) -> None:
        result = self.service.validate_csv(VALID_CSV, max_sample_rows=2)
        assert len(result.sample_rows) == 2

    def test_validate_sample_rows_text_truncated(self) -> None:
        long_text = "A" * 500
        csv = f"note_id,subject_id,hadm_id,note_type,text\n10001,100,200001,DS,{long_text}\n"
        result = self.service.validate_csv(csv, max_sample_rows=1)
        assert len(result.sample_rows) == 1
        assert len(result.sample_rows[0]["text"]) <= 203  # 200 + "..."

    def test_count_csv_rows(self) -> None:
        count = self.service.count_csv_rows(VALID_CSV)
        assert count == 5


class TestMimicImportConfig:
    """Tests for config validation."""

    def test_defaults(self) -> None:
        config = MimicImportConfig()
        assert config.chunk_size == 100
        assert config.max_rows is None
        assert config.skip_duplicates is True
        assert config.enqueue_processing is True

    def test_custom_values(self) -> None:
        config = MimicImportConfig(chunk_size=50, max_rows=10, skip_duplicates=False)
        assert config.chunk_size == 50
        assert config.max_rows == 10
        assert config.skip_duplicates is False

    def test_chunk_size_bounds(self) -> None:
        with pytest.raises(Exception):
            MimicImportConfig(chunk_size=0)
        with pytest.raises(Exception):
            MimicImportConfig(chunk_size=20000)


class TestRequiredColumns:
    """Tests for column constants."""

    def test_required_columns_present(self) -> None:
        assert "note_id" in REQUIRED_COLUMNS
        assert "subject_id" in REQUIRED_COLUMNS
        assert "hadm_id" in REQUIRED_COLUMNS
        assert "note_type" in REQUIRED_COLUMNS
        assert "text" in REQUIRED_COLUMNS
        assert len(REQUIRED_COLUMNS) == 5
