from dataclasses import dataclass


@dataclass(frozen=True)
class SoapNoteContent:
    subjective: str
    objective: str
    assessment: str
    plan: str


class LLMProviderError(Exception):
    pass
