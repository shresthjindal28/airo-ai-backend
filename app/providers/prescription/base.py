from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PrescriptionContext:
    patient_name: str
    patient_age: str
    patient_gender: str
    doctor_name: str
    doctor_registration: str
    hospital_name: str
    consultation_date: str
    chief_complaint: str
    subjective: str
    objective: str
    assessment: str
    plan: str


class PrescriptionProviderError(Exception):
    pass


class PrescriptionProvider(ABC):

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_html(self, context: PrescriptionContext) -> str:
        raise NotImplementedError
