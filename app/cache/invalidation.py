import uuid

from app.cache import keys
from app.cache.redis_client import redis_delete_pattern, redis_incr


def invalidate_patient_caches(patient_id: uuid.UUID) -> int:
    redis_delete_pattern(keys.patient_cache_prefix(patient_id))
    redis_delete_pattern(keys.patient_retrieval_prefix(patient_id))
    redis_delete_pattern(keys.patient_response_prefix(patient_id))
    return redis_incr(keys.patient_memory_version(patient_id)) or 1
