from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.prescription.base import (
    PrescriptionContext,
    PrescriptionProvider,
    PrescriptionProviderError,
)
from app.providers.prescription.html_utils import extract_html_document

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a clinical prescription documentation assistant.
Generate a medical prescription as STRICT HTML only.

Rules:
- Output ONLY valid HTML. No markdown. No JSON. No explanations.
- Use only medications and clinical details present in the SOAP note.
- Do not invent drugs, doses, or diagnoses not supported by the SOAP note.
- If a section lacks data, write a brief clinically appropriate placeholder.
- Use semantic HTML: header, section, table, p, strong, ul, li.
- Include these sections in order:
  1. Hospital header
  2. Patient details (name, age, gender, date)
  3. Diagnosis
  4. Medication table with columns: Medicine, Dosage, Frequency, Duration
  5. Instructions
  6. Warnings
  7. Follow-up
  8. Doctor signature block
"""

USER_PROMPT_TEMPLATE = """Hospital: {hospital_name}
Doctor: {doctor_name}
Registration: {doctor_registration}
Date: {consultation_date}

Patient: {patient_name}
Age: {patient_age}
Gender: {patient_gender}
Chief complaint: {chief_complaint}

SOAP NOTE (sole clinical source):
Subjective: {subjective}
Objective: {objective}
Assessment: {assessment}
Plan: {plan}

Return the prescription as HTML only."""


class HuggingFacePrescriptionProvider(PrescriptionProvider):

    @property
    def provider_name(self) -> str:
        return f"huggingface:{settings.PRESCRIPTION_LLM_PROVIDER}"

    def generate_html(self, context: PrescriptionContext) -> str:
        if not settings.HF_TOKEN:
            raise PrescriptionProviderError("HF_TOKEN is required for prescription generation")

        client = InferenceClient(
            token=settings.HF_TOKEN,
            provider=settings.PRESCRIPTION_LLM_PROVIDER,
        )

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
            response = client.chat_completion(
                model=settings.PRESCRIPTION_LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.PRESCRIPTION_LLM_MAX_TOKENS,
                temperature=0.2,
            )
        except HfHubHTTPError as exc:
            logger.error("Hugging Face prescription generation failed: %s", exc)
            raise PrescriptionProviderError(str(exc)) from exc

        raw_text = response.choices[0].message.content or ""
        try:
            return extract_html_document(raw_text)
        except ValueError as exc:
            raise PrescriptionProviderError(str(exc)) from exc
