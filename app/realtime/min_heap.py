import heapq
from typing import Generic, TypeVar

T = TypeVar("T")


class MinHeap(Generic[T]):
    """Binary min-heap for O(log n) missing-chunk tracking."""

    def __init__(self) -> None:
        self._heap: list[T] = []

    def push(self, value: T) -> None:
        heapq.heappush(self._heap, value)

    def pop(self) -> T:
        return heapq.heappop(self._heap)

    def peek(self) -> T | None:
        return self._heap[0] if self._heap else None

    def remove(self, value: T) -> None:
        self._heap.remove(value)
        heapq.heapify(self._heap)

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)

    def to_sorted_list(self) -> list[T]:
        return sorted(self._heap)
