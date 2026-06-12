import enum


class ConsultationStatus(str, enum.Enum):
    scheduled = "scheduled"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class SessionStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    ended = "ended"
    failed = "failed"


class ChunkStatus(str, enum.Enum):
    pending = "pending"
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class AIJobType(str, enum.Enum):
    transcription = "transcription"
    transcript_finalize = "transcript_finalize"
    soap_generation = "soap_generation"
    prescription_generation = "prescription_generation"
    summary_generation = "summary_generation"
    clinical_insights = "clinical_insights"
    memory_ingestion = "memory_ingestion"


class MemorySourceType(str, enum.Enum):
    transcript = "transcript"
    soap_note = "soap_note"
    prescription = "prescription"
    consultation_document = "consultation_document"
    clinical_summary = "clinical_summary"
    doctor_note = "doctor_note"


class AIJobStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"
