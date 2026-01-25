"""Voice Transcription Service.

Provides audio transcription and structured extraction for clinical notes.
Designed for integration with Whisper-compatible transcription services.
"""

import asyncio
import hashlib
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TranscriptionStatus(str, Enum):
    """Status of a transcription job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioFormat(str, Enum):
    """Supported audio formats."""

    WAV = "wav"
    MP3 = "mp3"
    M4A = "m4a"
    OGG = "ogg"
    WEBM = "webm"
    FLAC = "flac"


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text with timing."""

    id: int
    start_time: float  # seconds
    end_time: float  # seconds
    text: str
    confidence: float = 1.0
    speaker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "confidence": self.confidence,
            "speaker": self.speaker,
        }


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""

    job_id: str
    status: TranscriptionStatus
    text: str = ""
    segments: list[TranscriptionSegment] = field(default_factory=list)
    language: str = "en"
    duration_seconds: float = 0.0
    processing_time_ms: int = 0
    model: str = "whisper-1"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "text": self.text,
            "segments": [s.to_dict() for s in self.segments],
            "language": self.language,
            "duration_seconds": self.duration_seconds,
            "processing_time_ms": self.processing_time_ms,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "error": self.error,
        }


@dataclass
class ExtractedClinicalData:
    """Structured clinical data extracted from transcription."""

    chief_complaint: str | None = None
    history_present_illness: list[str] = field(default_factory=list)
    review_of_systems: dict[str, list[str]] = field(default_factory=dict)
    physical_exam: dict[str, str] = field(default_factory=dict)
    assessment: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    medications_mentioned: list[str] = field(default_factory=list)
    diagnoses_mentioned: list[str] = field(default_factory=list)
    procedures_mentioned: list[str] = field(default_factory=list)
    labs_ordered: list[str] = field(default_factory=list)
    follow_up: str | None = None
    raw_sections: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chief_complaint": self.chief_complaint,
            "history_present_illness": self.history_present_illness,
            "review_of_systems": self.review_of_systems,
            "physical_exam": self.physical_exam,
            "assessment": self.assessment,
            "plan": self.plan,
            "medications_mentioned": self.medications_mentioned,
            "diagnoses_mentioned": self.diagnoses_mentioned,
            "procedures_mentioned": self.procedures_mentioned,
            "labs_ordered": self.labs_ordered,
            "follow_up": self.follow_up,
            "raw_sections": self.raw_sections,
        }


class VoiceTranscriptionService:
    """Service for transcribing audio and extracting clinical data."""

    # Common clinical section markers
    SECTION_MARKERS = {
        "chief_complaint": [
            "chief complaint",
            "cc",
            "reason for visit",
            "presenting complaint",
        ],
        "hpi": [
            "history of present illness",
            "hpi",
            "present illness",
            "history present illness",
        ],
        "ros": [
            "review of systems",
            "ros",
            "systems review",
        ],
        "physical_exam": [
            "physical exam",
            "physical examination",
            "pe",
            "exam",
            "on exam",
        ],
        "assessment": [
            "assessment",
            "impression",
            "diagnosis",
            "diagnoses",
        ],
        "plan": [
            "plan",
            "treatment plan",
            "management",
        ],
        "medications": [
            "medications",
            "meds",
            "current medications",
            "medication list",
        ],
        "follow_up": [
            "follow up",
            "follow-up",
            "return",
            "next appointment",
        ],
    }

    # Review of systems categories
    ROS_CATEGORIES = [
        "constitutional",
        "eyes",
        "ears",
        "nose",
        "throat",
        "cardiovascular",
        "respiratory",
        "gastrointestinal",
        "genitourinary",
        "musculoskeletal",
        "skin",
        "neurological",
        "psychiatric",
        "endocrine",
        "hematologic",
        "allergic",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = "https://api.openai.com/v1/audio/transcriptions",
        model: str = "whisper-1",
    ) -> None:
        """Initialize the voice transcription service.

        Args:
            api_key: API key for transcription service (Whisper-compatible)
            api_url: URL for transcription API
            model: Model name to use for transcription
        """
        self._api_key = api_key
        self._api_url = api_url
        self._model = model
        self._job_store: dict[str, TranscriptionResult] = {}

    def _generate_job_id(self, audio_content: bytes) -> str:
        """Generate a unique job ID based on audio content hash."""
        hash_obj = hashlib.sha256(audio_content[:1024])  # Hash first 1KB
        timestamp = datetime.now(UTC).timestamp()
        return f"tr-{hash_obj.hexdigest()[:12]}-{int(timestamp)}"

    async def transcribe_audio(
        self,
        audio_content: bytes,
        audio_format: AudioFormat = AudioFormat.WAV,
        language: str = "en",
    ) -> TranscriptionResult:
        """Transcribe audio content.

        Args:
            audio_content: Raw audio bytes
            audio_format: Format of the audio file
            language: Expected language of the audio

        Returns:
            TranscriptionResult with status and text
        """
        job_id = self._generate_job_id(audio_content)
        start_time = datetime.now(UTC)

        # Create initial result
        result = TranscriptionResult(
            job_id=job_id,
            status=TranscriptionStatus.PROCESSING,
            language=language,
            model=self._model,
        )
        self._job_store[job_id] = result

        try:
            # In production, this would call the actual transcription API
            # For now, simulate transcription
            transcript = await self._simulate_transcription(audio_content, language)

            end_time = datetime.now(UTC)
            processing_time = int((end_time - start_time).total_seconds() * 1000)

            result.status = TranscriptionStatus.COMPLETED
            result.text = transcript["text"]
            result.segments = [
                TranscriptionSegment(**seg) for seg in transcript.get("segments", [])
            ]
            result.duration_seconds = transcript.get("duration", 0.0)
            result.processing_time_ms = processing_time

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            result.status = TranscriptionStatus.FAILED
            result.error = str(e)

        self._job_store[job_id] = result
        return result

    async def _simulate_transcription(
        self, audio_content: bytes, language: str
    ) -> dict[str, Any]:
        """Simulate transcription for testing.

        In production, replace with actual API call.
        """
        # Simulate processing time
        await asyncio.sleep(0.1)

        # Estimate duration from audio size (rough approximation)
        # Assume ~16KB per second for typical audio
        estimated_duration = len(audio_content) / 16000.0

        # Return simulated transcript
        return {
            "text": "Patient presents with chief complaint of headache for two days. "
            "History of present illness: The patient reports onset of throbbing "
            "headache starting two days ago. Pain is located in the frontal region. "
            "Physical exam: Alert and oriented. Vitals stable. "
            "Assessment: Tension headache. "
            "Plan: Recommend acetaminophen as needed, hydration, follow up if symptoms persist.",
            "duration": estimated_duration,
            "segments": [
                {
                    "id": 0,
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "text": "Patient presents with chief complaint of headache for two days.",
                    "confidence": 0.95,
                },
                {
                    "id": 1,
                    "start_time": 5.0,
                    "end_time": 15.0,
                    "text": "History of present illness: The patient reports onset of throbbing headache starting two days ago.",
                    "confidence": 0.92,
                },
                {
                    "id": 2,
                    "start_time": 15.0,
                    "end_time": 20.0,
                    "text": "Pain is located in the frontal region.",
                    "confidence": 0.98,
                },
            ],
        }

    def get_transcription_status(self, job_id: str) -> TranscriptionResult | None:
        """Get status of a transcription job.

        Args:
            job_id: Job identifier

        Returns:
            TranscriptionResult if found, None otherwise
        """
        return self._job_store.get(job_id)

    def extract_clinical_data(
        self, transcript_text: str
    ) -> ExtractedClinicalData:
        """Extract structured clinical data from transcript text.

        Args:
            transcript_text: Transcribed text to parse

        Returns:
            ExtractedClinicalData with extracted fields
        """
        extracted = ExtractedClinicalData()
        text_lower = transcript_text.lower()

        # Find section boundaries
        sections = self._identify_sections(transcript_text)
        extracted.raw_sections = sections

        # Extract chief complaint
        if "chief_complaint" in sections:
            extracted.chief_complaint = sections["chief_complaint"].strip()

        # Extract HPI
        if "hpi" in sections:
            hpi_text = sections["hpi"]
            # Split into sentences
            sentences = [s.strip() for s in hpi_text.split(".") if s.strip()]
            extracted.history_present_illness = sentences

        # Extract ROS
        if "ros" in sections:
            ros_text = sections["ros"]
            extracted.review_of_systems = self._parse_ros(ros_text)

        # Extract physical exam
        if "physical_exam" in sections:
            pe_text = sections["physical_exam"]
            extracted.physical_exam = self._parse_physical_exam(pe_text)

        # Extract assessment
        if "assessment" in sections:
            assessment_text = sections["assessment"]
            assessments = [a.strip() for a in assessment_text.split(".") if a.strip()]
            extracted.assessment = assessments
            # Also capture as diagnoses
            extracted.diagnoses_mentioned = assessments

        # Extract plan
        if "plan" in sections:
            plan_text = sections["plan"]
            plans = [p.strip() for p in plan_text.split(".") if p.strip()]
            extracted.plan = plans

        # Extract medications mentioned anywhere
        extracted.medications_mentioned = self._extract_medications(transcript_text)

        # Extract follow-up
        if "follow_up" in sections:
            extracted.follow_up = sections["follow_up"].strip()

        return extracted

    def _identify_sections(self, text: str) -> dict[str, str]:
        """Identify clinical note sections in text."""
        sections: dict[str, str] = {}
        text_lower = text.lower()

        # Find positions of section markers
        marker_positions: list[tuple[int, str, str]] = []

        for section_key, markers in self.SECTION_MARKERS.items():
            for marker in markers:
                pos = text_lower.find(marker)
                if pos != -1:
                    # Find the actual text after the marker
                    marker_end = pos + len(marker)
                    # Skip common separators
                    while marker_end < len(text) and text[marker_end] in ":. \n":
                        marker_end += 1
                    marker_positions.append((pos, section_key, text[marker_end:]))
                    break

        # Sort by position
        marker_positions.sort(key=lambda x: x[0])

        # Extract text between markers
        for i, (pos, key, remaining) in enumerate(marker_positions):
            if i + 1 < len(marker_positions):
                next_pos = marker_positions[i + 1][0]
                # Extract text from current marker to next marker
                section_text = text[pos:next_pos]
                # Remove the marker itself
                for marker in self.SECTION_MARKERS[key]:
                    if section_text.lower().startswith(marker):
                        section_text = section_text[len(marker):].lstrip(":. \n")
                        break
                sections[key] = section_text.strip()
            else:
                # Last section - take rest of text
                sections[key] = remaining.strip()

        return sections

    def _parse_ros(self, ros_text: str) -> dict[str, list[str]]:
        """Parse review of systems text into categories."""
        ros_data: dict[str, list[str]] = {}
        text_lower = ros_text.lower()

        for category in self.ROS_CATEGORIES:
            if category in text_lower:
                # Find the text after the category
                pos = text_lower.find(category)
                end = len(ros_text)
                # Find next category
                for other_cat in self.ROS_CATEGORIES:
                    if other_cat != category:
                        other_pos = text_lower.find(other_cat, pos + len(category))
                        if other_pos != -1 and other_pos < end:
                            end = other_pos

                category_text = ros_text[pos + len(category):end].strip()
                if category_text:
                    # Clean up the text
                    category_text = category_text.lstrip(":- ")
                    findings = [f.strip() for f in category_text.split(",") if f.strip()]
                    if findings:
                        ros_data[category] = findings

        return ros_data

    def _parse_physical_exam(self, pe_text: str) -> dict[str, str]:
        """Parse physical exam findings."""
        pe_data: dict[str, str] = {}

        # Common exam sections
        exam_sections = [
            "general",
            "vitals",
            "heent",
            "head",
            "eyes",
            "ears",
            "neck",
            "lungs",
            "heart",
            "cardiac",
            "cardiovascular",
            "abdomen",
            "abdominal",
            "extremities",
            "skin",
            "neuro",
            "neurological",
        ]

        text_lower = pe_text.lower()

        for section in exam_sections:
            if section in text_lower:
                pos = text_lower.find(section)
                # Find end of this section
                end = len(pe_text)
                for other in exam_sections:
                    if other != section:
                        other_pos = text_lower.find(other, pos + len(section))
                        if other_pos != -1 and other_pos < end:
                            end = other_pos

                finding = pe_text[pos + len(section):end].strip()
                if finding:
                    finding = finding.lstrip(":- ")
                    pe_data[section] = finding

        return pe_data

    def _extract_medications(self, text: str) -> list[str]:
        """Extract medication names from text."""
        medications = []
        text_lower = text.lower()

        # Common medication keywords that indicate a medication mention
        med_indicators = [
            "acetaminophen",
            "ibuprofen",
            "aspirin",
            "lisinopril",
            "metformin",
            "atorvastatin",
            "omeprazole",
            "amlodipine",
            "metoprolol",
            "losartan",
            "hydrochlorothiazide",
            "gabapentin",
            "levothyroxine",
            "prednisone",
            "albuterol",
            "amoxicillin",
            "azithromycin",
            "ciprofloxacin",
            "sertraline",
            "fluoxetine",
            "tramadol",
        ]

        for med in med_indicators:
            if med in text_lower:
                # Capitalize properly
                medications.append(med.capitalize())

        return list(set(medications))


# Singleton instance
_service_instance: VoiceTranscriptionService | None = None


def get_voice_transcription_service() -> VoiceTranscriptionService:
    """Get the voice transcription service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = VoiceTranscriptionService()
    return _service_instance
