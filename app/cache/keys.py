import uuid


def patient_memory_version(patient_id: uuid.UUID) -> str:
    return f"airo:meta:patient:{patient_id}:memory_version"


def patient_timeline(patient_id: uuid.UUID) -> str:
    return f"airo:cache:patient:{patient_id}:timeline"


def patient_briefing(patient_id: uuid.UUID) -> str:
    return f"airo:cache:patient:{patient_id}:briefing"


def patient_memory_bundle(patient_id: uuid.UUID) -> str:
    return f"airo:cache:patient:{patient_id}:memory_bundle"


def patient_cache_prefix(patient_id: uuid.UUID) -> str:
    return f"airo:cache:patient:{patient_id}:"


def patient_retrieval_prefix(patient_id: uuid.UUID) -> str:
    return f"airo:cache:retrieval:{patient_id}:"


def patient_response_prefix(patient_id: uuid.UUID) -> str:
    return f"airo:cache:response:{patient_id}:"
