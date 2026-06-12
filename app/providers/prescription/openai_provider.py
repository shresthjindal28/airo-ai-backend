from openai import OpenAI

from app.core.config import settings
from app.providers.prescription.base import (
    PrescriptionContext,
    PrescriptionProvider,
    PrescriptionProviderError,
)
from app.providers.prescription.huggingface_provider import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from app.providers.prescription.html_utils import extract_html_document


class OpenAIPrescriptionProvider(PrescriptionProvider):

    @property
    def provider_name(self) -> str:
        return f"openai:{settings.PRESCRIPTION_LLM_MODEL}"

    def generate_html(self, context: PrescriptionContext) -> str:
        if not settings.OPENAI_API_KEY:
            raise PrescriptionProviderError("OPENAI_API_KEY is required")

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = USER_PROMPT_TEMPLATE.format(
            hospital_name=context.hospital_name or "AIRO Clinical",
            doctor_name=context.doctor_name,
            doctor_registration=context.doctor_registration or "—",
            consultation_date=context.consultation_date,
            patient_name=context.patient_name,
            patient_age=context.patient_age,
            patient_gender=context.patient_gender,
            chief_complaint=context.chief_complaint or "—",
            subjective=context.subjective or "Not documented.",
            objective=context.objective or "Not documented.",
            assessment=context.assessment or "Not documented.",
            plan=context.plan or "Not documented.",
        )

        try:
            response = client.chat.completions.create(
                model=settings.PRESCRIPTION_LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.PRESCRIPTION_LLM_MAX_TOKENS,
                temperature=0.2,
            )
        except Exception as exc:
            raise PrescriptionProviderError(str(exc)) from exc

        raw_text = response.choices[0].message.content or ""
        try:
            return extract_html_document(raw_text)
        except ValueError as exc:
            raise PrescriptionProviderError(str(exc)) from exc
