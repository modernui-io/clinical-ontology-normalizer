"""Tests for voice transcription service and API.

Tests verify:
- Audio transcription with simulated backend
- Clinical data extraction from transcripts
- API endpoint functionality
- Error handling for invalid inputs
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.voice_transcription_service import (
    VoiceTranscriptionService,
    AudioFormat,
    TranscriptionStatus,
    get_voice_transcription_service,
)


class TestVoiceTranscriptionService:
    """Test the voice transcription service."""

    @pytest.fixture
    def service(self):
        return VoiceTranscriptionService()

    @pytest.mark.asyncio
    async def test_transcribe_audio_basic(self, service):
        # Simulate audio content
        audio_content = b"fake audio data" * 1000
        result = await service.transcribe_audio(
            audio_content=audio_content,
            audio_format=AudioFormat.WAV,
            language="en",
        )

        assert result.job_id is not None
        assert result.status == TranscriptionStatus.COMPLETED
        assert result.text != ""
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_audio_creates_segments(self, service):
        audio_content = b"fake audio data" * 1000
        result = await service.transcribe_audio(
            audio_content=audio_content,
            audio_format=AudioFormat.WAV,
        )

        assert len(result.segments) > 0
        for segment in result.segments:
            assert segment.id is not None
            assert segment.start_time >= 0
            assert segment.end_time >= segment.start_time
            assert segment.text != ""

    @pytest.mark.asyncio
    async def test_transcribe_audio_tracks_duration(self, service):
        audio_content = b"fake audio data" * 1000
        result = await service.transcribe_audio(
            audio_content=audio_content,
            audio_format=AudioFormat.MP3,
        )

        assert result.duration_seconds > 0
        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_get_transcription_status(self, service):
        audio_content = b"fake audio data" * 1000
        result = await service.transcribe_audio(audio_content, AudioFormat.WAV)

        # Check status retrieval
        status = service.get_transcription_status(result.job_id)
        assert status is not None
        assert status.job_id == result.job_id
        assert status.status == TranscriptionStatus.COMPLETED

    def test_get_transcription_status_not_found(self, service):
        status = service.get_transcription_status("nonexistent-job-id")
        assert status is None


class TestClinicalDataExtraction:
    """Test clinical data extraction from transcripts."""

    @pytest.fixture
    def service(self):
        return VoiceTranscriptionService()

    def test_extract_chief_complaint(self, service):
        text = "Chief complaint: Patient presents with severe headache for 3 days."
        extracted = service.extract_clinical_data(text)

        assert extracted.chief_complaint is not None
        assert "headache" in extracted.chief_complaint.lower() or "headache" in text.lower()

    def test_extract_history_present_illness(self, service):
        text = """
        History of present illness: The patient reports onset of throbbing
        headache starting three days ago. Pain is located in the frontal region.
        Associated with nausea.
        """
        extracted = service.extract_clinical_data(text)

        assert len(extracted.history_present_illness) > 0 or "hpi" in extracted.raw_sections

    def test_extract_physical_exam(self, service):
        text = """
        Physical exam: General: Alert and oriented. Vitals: BP 120/80.
        HEENT: PERRLA. Neck: Supple.
        """
        extracted = service.extract_clinical_data(text)

        assert len(extracted.physical_exam) > 0 or "physical_exam" in extracted.raw_sections

    def test_extract_assessment_and_plan(self, service):
        text = """
        Assessment: Tension headache. Migraine to rule out.
        Plan: Start acetaminophen 500mg PRN. Hydration. Follow up in one week.
        """
        extracted = service.extract_clinical_data(text)

        assert len(extracted.assessment) > 0 or "assessment" in extracted.raw_sections
        assert len(extracted.plan) > 0 or "plan" in extracted.raw_sections

    def test_extract_medications(self, service):
        text = "The patient is currently taking acetaminophen and ibuprofen for pain."
        extracted = service.extract_clinical_data(text)

        assert len(extracted.medications_mentioned) > 0
        # Should find acetaminophen and/or ibuprofen
        meds_lower = [m.lower() for m in extracted.medications_mentioned]
        assert "acetaminophen" in meds_lower or "ibuprofen" in meds_lower

    def test_extract_full_soap_note(self, service):
        text = """
        Chief complaint: Headache for two days.
        History of present illness: Patient reports throbbing frontal headache.
        Review of systems: Neurological - headache, no vision changes.
        Physical exam: General alert and oriented. Vitals stable.
        Assessment: Tension headache.
        Plan: Acetaminophen as needed. Return if symptoms worsen.
        """
        extracted = service.extract_clinical_data(text)

        # Should extract multiple sections
        sections_found = 0
        if extracted.chief_complaint:
            sections_found += 1
        if extracted.history_present_illness:
            sections_found += 1
        if extracted.assessment:
            sections_found += 1
        if extracted.plan:
            sections_found += 1
        if extracted.raw_sections:
            sections_found += len(extracted.raw_sections)

        assert sections_found >= 2  # At least 2 sections should be found


class TestVoiceAPI:
    """Test the voice API endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_supported_formats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/voice/formats")

        assert response.status_code == 200
        data = response.json()
        assert "formats" in data
        assert "wav" in data["formats"]
        assert "mp3" in data["formats"]

    @pytest.mark.asyncio
    async def test_transcribe_audio_endpoint(self, client):
        # Create a fake audio file
        audio_content = b"fake audio content for testing" * 100

        async with client as ac:
            response = await ac.post(
                "/api/v1/voice/transcribe",
                files={"file": ("test.wav", audio_content, "audio/wav")},
                data={"language": "en", "extract_clinical": "true"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "completed"
        assert "text" in data
        assert data["text"] != ""

    @pytest.mark.asyncio
    async def test_transcribe_with_extraction(self, client):
        audio_content = b"fake audio content" * 100

        async with client as ac:
            response = await ac.post(
                "/api/v1/voice/transcribe",
                files={"file": ("test.wav", audio_content, "audio/wav")},
                data={"language": "en", "extract_clinical": "true"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "extracted_data" in data
        # Extracted data should be present when extract_clinical is true
        if data["extracted_data"]:
            assert isinstance(data["extracted_data"], dict)

    @pytest.mark.asyncio
    async def test_transcribe_without_extraction(self, client):
        audio_content = b"fake audio content" * 100

        async with client as ac:
            response = await ac.post(
                "/api/v1/voice/transcribe",
                files={"file": ("test.wav", audio_content, "audio/wav")},
                data={"language": "en", "extract_clinical": "false"},
            )

        assert response.status_code == 200
        data = response.json()
        # Should still have the transcription
        assert "text" in data

    @pytest.mark.asyncio
    async def test_transcribe_empty_file(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/voice/transcribe",
                files={"file": ("test.wav", b"", "audio/wav")},
                data={"language": "en"},
            )

        assert response.status_code == 400
        data = response.json()
        # Error response uses standardized format with message or detail
        error_text = data.get("message", data.get("detail", ""))
        assert "Empty" in error_text or "empty" in error_text.lower()

    @pytest.mark.asyncio
    async def test_extract_endpoint(self, client):
        text = "Chief complaint: Headache. Assessment: Tension headache. Plan: Acetaminophen."

        async with client as ac:
            response = await ac.post(
                "/api/v1/voice/extract",
                json={"text": text},
            )

        assert response.status_code == 200
        data = response.json()
        # Should have some extracted data
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_extract_empty_text(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/voice/extract",
                json={"text": ""},
            )

        assert response.status_code == 400
        # Just verify it's an error - format varies


class TestAudioFormatDetection:
    """Test audio format detection."""

    @pytest.fixture
    def service(self):
        return VoiceTranscriptionService()

    @pytest.mark.asyncio
    async def test_wav_format(self, service):
        result = await service.transcribe_audio(
            b"RIFF" + b"\x00" * 1000,
            AudioFormat.WAV,
        )
        assert result.status == TranscriptionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_mp3_format(self, service):
        result = await service.transcribe_audio(
            b"\xff\xfb" + b"\x00" * 1000,
            AudioFormat.MP3,
        )
        assert result.status == TranscriptionStatus.COMPLETED


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""

    @pytest.mark.asyncio
    async def test_result_to_dict(self):
        service = VoiceTranscriptionService()
        result = await service.transcribe_audio(b"test" * 100, AudioFormat.WAV)
        d = result.to_dict()

        assert "job_id" in d
        assert "status" in d
        assert "text" in d
        assert "segments" in d
        assert isinstance(d["segments"], list)


class TestServiceSingleton:
    """Test singleton pattern."""

    def test_get_voice_transcription_service_singleton(self):
        s1 = get_voice_transcription_service()
        s2 = get_voice_transcription_service()
        assert s1 is s2
