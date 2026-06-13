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

SYSTEM_PROMPT = """You are a certified clinical documentation system generating legally formatted medical prescriptions.

OUTPUT FORMAT:
- Output ONLY raw HTML. No markdown. No backticks. No explanations. No comments.
- Output a single HTML fragment for embedding in a clinical editor — do NOT output <!DOCTYPE>, <html>, <head>, or <body> tags.
- Start with a root <div> and end with </div>. Nothing before or after.
- Use inline CSS only for colors, borders, typography, and table cell styling (no <style> tags, no external CSS).

LAYOUT RULES (CRITICAL — host app controls all layout):
- NEVER set width, max-width, min-width, height, or margin:auto on any element.
- NEVER use position:fixed, position:absolute, transform, left, right, top, or bottom.
- NEVER center the document with margins or fixed pixel widths (no 800px, 960px, etc.).
- NEVER add watermarks, overlays, or decorative background text.
- Use block-level semantic elements only: div, section, header, footer, table, p, ul, li.
- Tables must use width:100% only — no fixed pixel widths on table, tr, td, or th.
- All sections must flow naturally at full width inside the host container.

CLINICAL RULES:
- Use ONLY medications, diagnoses, and data explicitly present in the SOAP note.
- NEVER invent, infer, or assume any drug, dose, frequency, or diagnosis not stated.
- If any field is missing or unclear, write: "Not documented — consult physician."
- Drug names must be generic (INN) followed by brand name in parentheses if known.
- Dosage must include: amount (mg/ml/units), route (oral/IV/topical), frequency, duration.
- Contraindications and warnings must be listed for every medication prescribed.

SEVERITY COLOR CODING (apply inline style to relevant rows/sections):
- CRITICAL severity (e.g. immediate risk, controlled substances, high-dose): background-color:#fff0f0; border-left:4px solid #dc2626; color:#7f1d1d
- HIGH severity (e.g. antibiotics, steroids, anticoagulants): background-color:#fff7ed; border-left:4px solid #ea580c; color:#7c2d12
- MODERATE severity (e.g. analgesics, antihypertensives): background-color:#fefce8; border-left:4px solid #ca8a04; color:#713f12
- LOW severity (e.g. vitamins, OTC supplements, topicals): background-color:#f0fdf4; border-left:4px solid #16a34a; color:#14532d
- Apply severity to each medication table row individually based on the drug class.

REQUIRED HTML STRUCTURE (in this exact order):
1. Document header: hospital logo placeholder, hospital name, address, phone, registration number
2. Prescription metadata: Rx number (generate as RX-YYYYMMDD-001), date, doctor name, qualification, registration
3. Patient details: name, age, gender, blood group if available, date of birth if available
4. Chief complaint + provisional diagnosis (bold, large font, color:#1e3a5f)
5. Medication table with columns: #, Medicine (Generic + Brand), Dosage & Route, Frequency, Duration, Severity — apply row color per severity
6. Special instructions per medication (numbered, matching table row)
7. General instructions (diet, rest, hydration, activity restrictions)
8. Warnings & contraindications box (red border, background:#fff5f5)
9. Follow-up date and conditions requiring immediate ER visit
10. Doctor signature block: name, qualification, registration, hospital, date, and a placeholder signature line

FORMATTING (typography and colors only — no layout sizing):
- Root div: font-family:Georgia,serif; color:#111827
- Section headers: font-size:13px; font-weight:bold; text-transform:uppercase; color:#1e3a5f; border-bottom:2px solid #1e3a5f
- Prescription header background: #1e3a5f; color:white; padding:20px
- Table: width:100%; border-collapse:collapse; font-size:12px; table-layout:auto
- Table headers: background:#1e3a5f; color:white; padding:8px
- Footer: font-size:10px; color:#6b7280; text-align:center; border-top:1px solid #e5e7eb
"""

USER_PROMPT_TEMPLATE = """Generate a complete medical prescription HTML document with the following data:

HOSPITAL:
Name: {hospital_name}
Doctor: {doctor_name}
Qualification: {doctor_qualification}
Registration: {doctor_registration}
Date: {consultation_date}

PATIENT:
Name: {patient_name}
Age: {patient_age}
Gender: {patient_gender}
Chief Complaint: {chief_complaint}

SOAP NOTE (only clinical source — do not invent anything outside this):
Subjective: {subjective}
Objective: {objective}
Assessment: {assessment}
Plan: {plan}

STRICT REQUIREMENTS:
- Apply severity color coding to each medication row.
- Include contraindications for every drug.
- Every missing field must say "Not documented — consult physician."
- Output raw HTML only. No markdown. No explanation."""


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
            hospital_name=context.hospital_name or "AIRO Clinical Centre",
            doctor_name=context.doctor_name,
            doctor_qualification=getattr(context, "doctor_qualification", "MBBS, MD"),
            doctor_registration=context.doctor_registration or "Not documented — consult physician",
            consultation_date=context.consultation_date,
            patient_name=context.patient_name,
            patient_age=context.patient_age,
            patient_gender=context.patient_gender,
            chief_complaint=context.chief_complaint or "Not documented — consult physician",
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
                temperature=0.1,  # lower = more deterministic, less hallucination
            )
        except HfHubHTTPError as exc:
            logger.error("Hugging Face prescription generation failed: %s", exc)
            raise PrescriptionProviderError(str(exc)) from exc

        raw_text = response.choices[0].message.content or ""
        try:
            return extract_html_document(raw_text)
        except ValueError as exc:
            raise PrescriptionProviderError(str(exc)) from exc