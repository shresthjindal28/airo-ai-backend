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
    summary_generation = "summary_generation"
    clinical_insights = "clinical_insights"


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
