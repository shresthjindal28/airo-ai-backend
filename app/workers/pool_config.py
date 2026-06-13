"""Worker pool job-type routing for airo-ai."""

from app.models.enums import AIJobType

REALTIME_JOB_TYPES: frozenset[AIJobType] = frozenset({
    AIJobType.transcription,
    AIJobType.transcript_finalize,
})

CLINICAL_JOB_TYPES: frozenset[AIJobType] = frozenset({
    AIJobType.soap_generation,
    AIJobType.prescription_generation,
})

BACKGROUND_JOB_TYPES: frozenset[AIJobType] = frozenset({
    AIJobType.memory_ingestion,
    AIJobType.timeline_generation,
    AIJobType.patient_briefing_generation,
    AIJobType.summary_generation,
    AIJobType.clinical_insights,
    AIJobType.memory_reindex,
})

POOL_SPECS: list[tuple[str, frozenset[AIJobType]]] = [
    ("realtime", REALTIME_JOB_TYPES),
    ("clinical", CLINICAL_JOB_TYPES),
    ("background", BACKGROUND_JOB_TYPES),
]
