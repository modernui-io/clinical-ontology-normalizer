"""Voice API endpoints.

Provides audio transcription and clinical note extraction.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.services.voice_transcription_service import (
    AudioFormat,
    get_voice_transcription_service,
    TranscriptionStatus,
)


router = APIRouter(prefix="/voice", tags=["Voice"])


class TranscriptionResponse(BaseModel):
    """Response model for transcription result."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: pending, processing, completed, failed")
    text: str = Field(default="", description="Transcribed text")
    language: str = Field(default="en", description="Detected/specified language")
    duration_seconds: float = Field(default=0.0, description="Audio duration in seconds")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")
    error: str | None = Field(default=None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "tr-abc123-1705596000",
                "status": "completed",
                "text": "Patient presents with chief complaint of headache.",
                "language": "en",
                "duration_seconds": 30.5,
                "processing_time_ms": 1250,
                "error": None,
            }
        }


class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timing."""

    id: int = Field(..., description="Segment index")
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Segment text")
    confidence: float = Field(default=1.0, description="Confidence score 0-1")
    speaker: str | None = Field(default=None, description="Speaker identifier if available")


class DetailedTranscriptionResponse(TranscriptionResponse):
    """Response with segment-level details."""

    segments: list[TranscriptionSegment] = Field(
        default_factory=list, description="Text segments with timing"
    )
    model: str = Field(default="whisper-1", description="Model used for transcription")


class ExtractedClinicalData(BaseModel):
    """Structured clinical data extracted from transcript."""

    chief_complaint: str | None = Field(default=None, description="Chief complaint")
    history_present_illness: list[str] = Field(
        default_factory=list, description="HPI findings"
    )
    review_of_systems: dict[str, list[str]] = Field(
        default_factory=dict, description="ROS by system"
    )
    physical_exam: dict[str, str] = Field(
        default_factory=dict, description="PE findings by section"
    )
    assessment: list[str] = Field(default_factory=list, description="Assessment items")
    plan: list[str] = Field(default_factory=list, description="Plan items")
    medications_mentioned: list[str] = Field(
        default_factory=list, description="Medications mentioned"
    )
    diagnoses_mentioned: list[str] = Field(
        default_factory=list, description="Diagnoses mentioned"
    )
    follow_up: str | None = Field(default=None, description="Follow-up instructions")

    class Config:
        json_schema_extra = {
            "example": {
                "chief_complaint": "headache for two days",
                "history_present_illness": [
                    "Onset two days ago",
                    "Throbbing in nature",
                    "Frontal location",
                ],
                "review_of_systems": {
                    "neurological": ["headache", "no visual changes"],
                    "constitutional": ["no fever"],
                },
                "physical_exam": {
                    "general": "Alert and oriented",
                    "vitals": "Stable",
                },
                "assessment": ["Tension headache"],
                "plan": ["Acetaminophen PRN", "Hydration", "Follow up if persists"],
                "medications_mentioned": ["Acetaminophen"],
                "diagnoses_mentioned": ["Tension headache"],
                "follow_up": "Return if symptoms persist beyond one week",
            }
        }


class TranscriptionWithExtractionResponse(DetailedTranscriptionResponse):
    """Response including both transcription and clinical extraction."""

    extracted_data: ExtractedClinicalData | None = Field(
        default=None, description="Extracted clinical data"
    )


class ExtractRequest(BaseModel):
    """Request to extract clinical data from text."""

    text: str = Field(..., description="Transcript text to extract from")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Chief complaint: headache for two days. History of present illness: "
                "The patient reports onset of throbbing headache starting two days ago. "
                "Physical exam: Alert and oriented. Assessment: Tension headache. "
                "Plan: Acetaminophen as needed."
            }
        }


@router.post(
    "/transcribe",
    response_model=TranscriptionWithExtractionResponse,
    summary="Transcribe audio file",
    description="Upload an audio file for transcription. Optionally extract clinical data.",
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form(default="en", description="Expected language (ISO code)"),
    extract_clinical: bool = Form(
        default=True, description="Extract structured clinical data"
    ),
) -> TranscriptionWithExtractionResponse:
    """Transcribe an audio file and optionally extract clinical data."""
    # Validate file type
    content_type = file.content_type or ""
    filename = file.filename or ""

    # Determine audio format
    format_map = {
        "audio/wav": AudioFormat.WAV,
        "audio/x-wav": AudioFormat.WAV,
        "audio/mpeg": AudioFormat.MP3,
        "audio/mp3": AudioFormat.MP3,
        "audio/mp4": AudioFormat.M4A,
        "audio/x-m4a": AudioFormat.M4A,
        "audio/ogg": AudioFormat.OGG,
        "audio/webm": AudioFormat.WEBM,
        "audio/flac": AudioFormat.FLAC,
    }

    audio_format = format_map.get(content_type)
    if not audio_format:
        # Try to determine from extension
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        ext_map = {
            "wav": AudioFormat.WAV,
            "mp3": AudioFormat.MP3,
            "m4a": AudioFormat.M4A,
            "ogg": AudioFormat.OGG,
            "webm": AudioFormat.WEBM,
            "flac": AudioFormat.FLAC,
        }
        audio_format = ext_map.get(ext, AudioFormat.WAV)

    # Read audio content
    audio_content = await file.read()
    if not audio_content:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Validate file size (max 25MB for Whisper API)
    max_size = 25 * 1024 * 1024
    if len(audio_content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size // (1024*1024)}MB",
        )

    service = get_voice_transcription_service()

    # Perform transcription
    result = await service.transcribe_audio(
        audio_content=audio_content,
        audio_format=audio_format,
        language=language,
    )

    # Build response
    response = TranscriptionWithExtractionResponse(
        job_id=result.job_id,
        status=result.status.value,
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
        processing_time_ms=result.processing_time_ms,
        model=result.model,
        segments=[
            TranscriptionSegment(
                id=seg.id,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                confidence=seg.confidence,
                speaker=seg.speaker,
            )
            for seg in result.segments
        ],
        error=result.error,
    )

    # Extract clinical data if requested and transcription succeeded
    if extract_clinical and result.status == TranscriptionStatus.COMPLETED:
        extracted = service.extract_clinical_data(result.text)
        response.extracted_data = ExtractedClinicalData(
            chief_complaint=extracted.chief_complaint,
            history_present_illness=extracted.history_present_illness,
            review_of_systems=extracted.review_of_systems,
            physical_exam=extracted.physical_exam,
            assessment=extracted.assessment,
            plan=extracted.plan,
            medications_mentioned=extracted.medications_mentioned,
            diagnoses_mentioned=extracted.diagnoses_mentioned,
            follow_up=extracted.follow_up,
        )

    return response


@router.get(
    "/transcribe/{job_id}",
    response_model=TranscriptionResponse,
    summary="Get transcription status",
    description="Check the status of a transcription job.",
)
async def get_transcription_status(
    job_id: str,
) -> TranscriptionResponse:
    """Get the status of a transcription job."""
    service = get_voice_transcription_service()
    result = service.get_transcription_status(job_id)

    if not result:
        raise HTTPException(status_code=404, detail="Transcription job not found")

    return TranscriptionResponse(
        job_id=result.job_id,
        status=result.status.value,
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
        processing_time_ms=result.processing_time_ms,
        error=result.error,
    )


@router.post(
    "/extract",
    response_model=ExtractedClinicalData,
    summary="Extract clinical data from text",
    description="Extract structured clinical data from transcript text.",
)
async def extract_clinical_data(
    request: ExtractRequest,
) -> ExtractedClinicalData:
    """Extract clinical data from transcript text."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    service = get_voice_transcription_service()
    extracted = service.extract_clinical_data(request.text)

    return ExtractedClinicalData(
        chief_complaint=extracted.chief_complaint,
        history_present_illness=extracted.history_present_illness,
        review_of_systems=extracted.review_of_systems,
        physical_exam=extracted.physical_exam,
        assessment=extracted.assessment,
        plan=extracted.plan,
        medications_mentioned=extracted.medications_mentioned,
        diagnoses_mentioned=extracted.diagnoses_mentioned,
        follow_up=extracted.follow_up,
    )


class SupportedFormatsResponse(BaseModel):
    """Response for supported audio formats."""

    formats: list[str] = Field(..., description="Supported audio formats")
    max_file_size_mb: int = Field(..., description="Maximum file size in MB")
    max_duration_minutes: int = Field(..., description="Maximum audio duration in minutes")


@router.get(
    "/formats",
    response_model=SupportedFormatsResponse,
    summary="List supported audio formats",
    description="Get list of supported audio file formats.",
)
async def list_supported_formats() -> SupportedFormatsResponse:
    """List supported audio formats."""
    return SupportedFormatsResponse(
        formats=[f.value for f in AudioFormat],
        max_file_size_mb=25,
        max_duration_minutes=120,
    )
