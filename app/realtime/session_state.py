import uuid
from threading import Lock

from app.realtime.merge_buffer import OrderedMergeBuffer
from app.realtime.missing_chunk_tracker import MissingChunkTracker
from app.realtime.ring_buffer import RingBuffer
from app.realtime.segment_index import SegmentIndex
from app.schemas.transcript_segment import TranscriptSegmentResponse

DEFAULT_RING_CAPACITY = 200


class SessionRealtimeState:
    """Per-session in-memory DSA state for realtime transcription."""

    def __init__(self, session_id: uuid.UUID, ring_capacity: int = DEFAULT_RING_CAPACITY) -> None:
        self.session_id = session_id
        self.segment_index = SegmentIndex[int, TranscriptSegmentResponse]()
        self.merge_buffer = OrderedMergeBuffer()
        self.missing_tracker = MissingChunkTracker()
        self.ring_buffer = RingBuffer[TranscriptSegmentResponse](capacity=ring_capacity)


class SessionStateRegistry:
    """Thread-safe registry of per-session realtime state."""

    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, SessionRealtimeState] = {}
        self._lock = Lock()

    def get(self, session_id: uuid.UUID) -> SessionRealtimeState:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                state = SessionRealtimeState(session_id)
                self._sessions[session_id] = state
            return state

    def clear(self, session_id: uuid.UUID) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


session_state_registry = SessionStateRegistry()
