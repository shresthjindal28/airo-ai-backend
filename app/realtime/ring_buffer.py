from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class RingBuffer(Generic[T]):
    """Fixed-size ring buffer for the last N transcript segments in memory."""

    capacity: int

    def __post_init__(self) -> None:
        self._items: deque[T] = deque(maxlen=self.capacity)
        self._lock = Lock()

    def append(self, item: T) -> None:
        with self._lock:
            self._items.append(item)

    def snapshot(self) -> list[T]:
        with self._lock:
            return list(self._items)
