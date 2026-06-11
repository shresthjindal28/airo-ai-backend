from app.realtime.min_heap import MinHeap


class MissingChunkTracker:
    """
    Tracks missing chunk numbers using a min-heap.
    Example: received 1,2,3,5,6,7 -> heap contains [4].
    """

    def __init__(self, expected_last_chunk: int = 0) -> None:
        self._expected_last_chunk = expected_last_chunk
        self._received: set[int] = set()
        self._missing = MinHeap[int]()

    def register_received(self, chunk_number: int) -> None:
        if chunk_number in self._received:
            return

        self._received.add(chunk_number)

        if chunk_number > self._expected_last_chunk:
            self._expected_last_chunk = chunk_number

        self._rebuild_missing()

    def set_expected_last_chunk(self, last_chunk_number: int) -> None:
        self._expected_last_chunk = max(
            self._expected_last_chunk,
            last_chunk_number,
        )
        self._rebuild_missing()

    def _rebuild_missing(self) -> None:
        self._missing = MinHeap[int]()
        for chunk_number in range(1, self._expected_last_chunk + 1):
            if chunk_number not in self._received:
                self._missing.push(chunk_number)

    def missing_chunks(self) -> list[int]:
        return self._missing.to_sorted_list()

    def next_missing(self) -> int | None:
        return self._missing.peek()
