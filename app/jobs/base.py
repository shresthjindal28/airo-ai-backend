from abc import ABC, abstractmethod

from app.models.ai_job import AIJob


class JobHandler(ABC):

    @abstractmethod
    def run(self, job: AIJob) -> None:
        """Execute the job. Raise on failure."""
