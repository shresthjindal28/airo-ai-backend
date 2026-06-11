from collections.abc import Callable

from app.realtime.segment_index import SegmentIndex


class OrderedMergeBuffer:
    """
    Ordered merge buffer — emits transcript text only when contiguous
    chunks are available starting from the next expected chunk number.
    """

    def __init__(self) -> None:
        self._buffer = SegmentIndex[int, str]()
        self._next_expected = 1
        self._emitted_parts: list[str] = []

    @property
    def next_expected(self) -> int:
        return self._next_expected

    def add(self, chunk_number: int, text: str) -> list[str]:
        if chunk_number < self._next_expected:
            return []

        self._buffer.put(chunk_number, text)
        return self._drain_contiguous()

    def _drain_contiguous(self) -> list[str]:
        emitted: list[str] = []

        while self._buffer.contains(self._next_expected):
            text = self._buffer.get(self._next_expected)
            if text is None:
                break

            emitted.append(text)
            self._emitted_parts.append(text)
            self._next_expected += 1

        return emitted

    def merged_text(self, joiner: Callable[[list[str]], str] | None = None) -> str:
        parts = list(self._emitted_parts)
        for chunk_number in sorted(self._buffer.keys()):
            if chunk_number >= self._next_expected:
                value = self._buffer.get(chunk_number)
                if value is not None:
                    parts.append(value)

        if joiner is None:
            return " ".join(part.strip() for part in parts if part.strip())

        return joiner(parts)
