# import json
# import re

# from huggingface_hub import InferenceClient
# from huggingface_hub.errors import HfHubHTTPError

# from app.core.config import settings
# from app.core.logging import get_logger
# from app.providers.llm.base import LLMProviderError, SoapNoteContent

# logger = get_logger(__name__)

# SYSTEM_PROMPT = """You are a clinical documentation assistant.
# Given a doctor-patient consultation transcript, produce a SOAP note.

# Rules:
# - Use only information present in the transcript.
# - Do not invent vitals, labs, diagnoses, or medications.
# - If a section has no supporting information, write a brief note such as "Not documented in transcript."
# - Write in professional clinical English.
# - Return ONLY valid JSON with exactly these keys: subjective, objective, assessment, plan.
# """

# USER_PROMPT_TEMPLATE = """Chief complaint: {chief_complaint}

# Consultation transcript:
# {transcript}

# Return the SOAP note as JSON."""


# class HuggingFaceLLMProvider:

#     def __init__(self) -> None:
#         if not settings.HF_TOKEN:
#             raise LLMProviderError("HF_TOKEN is required for SOAP generation")

#         self._client = InferenceClient(
#             token=settings.HF_TOKEN,
#             provider=settings.SOAP_LLM_PROVIDER,
#         )
#         self._model = settings.SOAP_LLM_MODEL

#     def generate_soap_note(
#         self,
#         *,
#         transcript: str,
#         chief_complaint: str | None = None,
#     ) -> SoapNoteContent:
#         transcript = transcript.strip()
#         if not transcript:
#             raise LLMProviderError("Transcript is empty — cannot generate SOAP note")

#         prompt = USER_PROMPT_TEMPLATE.format(
#             chief_complaint=chief_complaint or "Not specified",
#             transcript=transcript[:12000],
#         )

#         try:
#             response = self._client.chat_completion(
#                 model=self._model,
#                 messages=[
#                     {"role": "system", "content": SYSTEM_PROMPT},
#                     {"role": "user", "content": prompt},
#                 ],
#                 max_tokens=settings.SOAP_LLM_MAX_TOKENS,
#                 temperature=0.2,
#             )
#         except HfHubHTTPError as exc:
#             logger.error("Hugging Face SOAP generation failed: %s", exc)
#             raise LLMProviderError(str(exc)) from exc

#         raw_text = response.choices[0].message.content or ""
#         parsed = _parse_soap_json(raw_text)
#         return SoapNoteContent(**parsed)


# def _parse_soap_json(raw_text: str) -> dict[str, str]:
#     text = raw_text.strip()

#     fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
#     if fenced:
#         text = fenced.group(1)

#     start = text.find("{")
#     end = text.rfind("}")
#     if start == -1 or end == -1:
#         raise LLMProviderError("Model response did not contain JSON")

#     try:
#         payload = json.loads(text[start : end + 1])
#     except json.JSONDecodeError as exc:
#         raise LLMProviderError("Model returned invalid JSON") from exc

#     sections: dict[str, str] = {}
#     for key in ("subjective", "objective", "assessment", "plan"):
#         value = payload.get(key, "")
#         sections[key] = str(value).strip() if value is not None else ""

#     if not any(sections.values()):
#         raise LLMProviderError("Model returned empty SOAP sections")

#     return sections


import json
import re

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.llm.base import LLMProviderError, SoapNoteContent

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an experienced clinical documentation specialist with deep knowledge of medical terminology, clinical workflows, and healthcare documentation standards.

Your task is to generate a structured SOAP note from a doctor-patient consultation transcript.

## Output Format
Return ONLY valid JSON with exactly these four keys: subjective, objective, assessment, plan.

## Section Guidelines

**Subjective**
- Chief complaint in the patient's own words (quoted if possible)
- History of present illness: onset, location, duration, character, aggravating/relieving factors, radiation, timing, severity (OLDCARTS)
- Relevant past medical history, surgical history, family history, social history
- Current medications and allergies if mentioned
- Review of systems findings reported by the patient

**Objective**
- Vital signs (only if explicitly stated)
- Physical examination findings as reported by the clinician
- Diagnostic results mentioned (labs, imaging, ECG, etc.)
- If no objective data is present in the transcript, write: "Not documented in transcript."

**Assessment**
- Primary diagnosis or differential diagnoses as discussed
- Clinical reasoning and acuity if mentioned
- Relevant ICD-10 diagnostic labels if inferable from context
- If no assessment is documented, write: "Not documented in transcript."

**Plan**
- Medications prescribed or adjusted (name, dose, route, frequency, duration)
- Investigations ordered
- Referrals or specialist consultations
- Patient education and counseling points
- Follow-up instructions and timeline
- If no plan is documented, write: "Not documented in transcript."

## Strict Rules
- Use ONLY information explicitly present in the transcript — do not infer, assume, or fabricate clinical details.
- Do not invent vitals, lab values, diagnoses, or medications under any circumstances.
- Preserve clinical accuracy: use correct medical terminology and standard abbreviations (e.g., bid, PRN, SOB, HTN).
- Write in professional, concise clinical English suitable for a medical record.
- Each section should be a single cohesive string (no nested JSON objects or arrays).
- If a section lacks supporting information, write: "Not documented in transcript."
"""

USER_PROMPT_TEMPLATE = """Chief complaint: {chief_complaint}

Consultation transcript:
{transcript}

Return the SOAP note as JSON."""


class HuggingFaceLLMProvider:

    def __init__(self) -> None:
        if not settings.HF_TOKEN:
            raise LLMProviderError("HF_TOKEN is required for SOAP generation")

        self._client = InferenceClient(
            token=settings.HF_TOKEN,
            provider=settings.SOAP_LLM_PROVIDER,
        )
        self._model = settings.SOAP_LLM_MODEL

    def generate_soap_note(
        self,
        *,
        transcript: str,
        chief_complaint: str | None = None,
    ) -> SoapNoteContent:
        transcript = transcript.strip()
        if not transcript:
            raise LLMProviderError("Transcript is empty — cannot generate SOAP note")

        prompt = USER_PROMPT_TEMPLATE.format(
            chief_complaint=chief_complaint or "Not specified",
            transcript=transcript[:12000],
        )

        try:
            response = self._client.chat_completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.SOAP_LLM_MAX_TOKENS,
                temperature=0.2,
            )
        except HfHubHTTPError as exc:
            logger.error("Hugging Face SOAP generation failed: %s", exc)
            raise LLMProviderError(str(exc)) from exc

        raw_text = response.choices[0].message.content or ""
        parsed = _parse_soap_json(raw_text)
        return SoapNoteContent(**parsed)


def _parse_soap_json(raw_text: str) -> dict[str, str]:
    text = raw_text.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMProviderError("Model response did not contain JSON")

    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMProviderError("Model returned invalid JSON") from exc

    sections: dict[str, str] = {}
    for key in ("subjective", "objective", "assessment", "plan"):
        value = payload.get(key, "")
        sections[key] = str(value).strip() if value is not None else ""

    if not any(sections.values()):
        raise LLMProviderError("Model returned empty SOAP sections")

    return sections