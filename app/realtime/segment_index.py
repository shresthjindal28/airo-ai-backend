from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class SegmentIndex(Generic[K, V]):
    """Hash map for O(1) chunk_number -> transcript segment lookup."""

    def __init__(self) -> None:
        self._store: dict[K, V] = {}

    def put(self, key: K, value: V) -> None:
        self._store[key] = value

    def get(self, key: K) -> V | None:
        return self._store.get(key)

    def contains(self, key: K) -> bool:
        return key in self._store

    def keys(self) -> list[K]:
        return list(self._store.keys())

    def values(self) -> list[V]:
        return list(self._store.values())

    def items(self) -> list[tuple[K, V]]:
        return list(self._store.items())

    def __len__(self) -> int:
        return len(self._store)
