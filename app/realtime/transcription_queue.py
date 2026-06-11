import uuid
from dataclasses import dataclass, field
from queue import PriorityQueue
from threading import Lock

from app.models.enums import JobPriority


@dataclass(order=True)
class QueuedTranscription:
    priority_rank: int
    created_at_ts: float
    job_id: uuid.UUID = field(compare=False, default_factory=uuid.uuid4)
    chunk_id: uuid.UUID = field(compare=False, default_factory=uuid.uuid4)
    chunk_number: int = field(compare=False, default=0)


class TranscriptionQueue:
    """
    In-process priority queue for transcription job dispatch ordering.
    The database ai_jobs table remains the durable queue; this layer
    provides O(log n) priority dispatch within worker processes.
    """

    _PRIORITY_RANK = {
        JobPriority.critical: 0,
        JobPriority.high: 1,
        JobPriority.normal: 2,
        JobPriority.low: 3,
    }

    def __init__(self) -> None:
        self._queue: PriorityQueue[QueuedTranscription] = PriorityQueue()
        self._lock = Lock()

    def enqueue(
        self,
        *,
        job_id: uuid.UUID,
        chunk_id: uuid.UUID,
        chunk_number: int,
        priority: JobPriority,
        created_at_ts: float,
    ) -> None:
        item = QueuedTranscription(
            priority_rank=self._PRIORITY_RANK[priority],
            created_at_ts=created_at_ts,
            job_id=job_id,
            chunk_id=chunk_id,
            chunk_number=chunk_number,
        )
        with self._lock:
            self._queue.put(item)

    def dequeue(self) -> QueuedTranscription | None:
        with self._lock:
            if self._queue.empty():
                return None
            return self._queue.get()

    def __len__(self) -> int:
        return self._queue.qsize()
