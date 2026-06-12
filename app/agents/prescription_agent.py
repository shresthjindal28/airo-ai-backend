from app.providers.prescription.base import PrescriptionContext, PrescriptionProvider
from app.providers.prescription.registry import get_prescription_provider


class PrescriptionAgent:

    def __init__(self, provider: PrescriptionProvider | None = None) -> None:
        self._provider = provider or get_prescription_provider()

    def generate(self, context: PrescriptionContext) -> tuple[str, str]:
        html = self._provider.generate_html(context)
        return html, self._provider.provider_name
