import json
import re
from datetime import date, datetime
from typing import Any

SYMPTOM_TERMS = {
    "fever", "headache", "cough", "nausea", "vomiting", "fatigue",
    "dizziness", "chest pain", "shortness of breath", "abdominal pain",
    "sore throat", "body ache", "chills", "rash", "weakness",
}

CONDITION_TERMS = {
    "diabetes", "hypertension", "asthma", "anemia", "arthritis",
    "migraine", "eczema", "hypothyroidism", "gerd", "copd",
}

MEDICATION_TERMS = {
    "paracetamol", "ibuprofen", "amoxicillin", "metformin", "atorvastatin",
    "omeprazole", "azithromycin", "cetirizine", "salbutamol", "levothyroxine",
    "amlodipine", "pantoprazole", "dolo", "crocin",
}

SECTION_PATTERNS = {
    "subjective": re.compile(r"subjective:\s*(.+?)(?=\n\w+:|$)", re.I | re.S),
    "objective": re.compile(r"objective:\s*(.+?)(?=\n\w+:|$)", re.I | re.S),
    "assessment": re.compile(r"assessment:\s*(.+?)(?=\n\w+:|$)", re.I | re.S),
    "plan": re.compile(r"plan:\s*(.+?)(?=\n\w+:|$)", re.I | re.S),
}


def _empty_profile() -> dict[str, Any]:
    return {
        "conditions": [],
        "symptoms": [],
        "medications": [],
        "diagnoses": [],
        "recommendations": [],
        "most_recent_consultation_date": None,
    }


def parse_profile(summary: str) -> dict[str, Any]:
    if not summary or not summary.strip():
        return _empty_profile()
    try:
        data = json.loads(summary)
        if isinstance(data, dict):
            profile = _empty_profile()
            profile.update(data)
            return profile
    except json.JSONDecodeError:
        pass
    return {
        **_empty_profile(),
        "recommendations": [line.lstrip("- ").strip() for line in summary.splitlines() if line.strip()],
    }


def _find_terms(text: str, terms: set[str]) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for term in sorted(terms, key=len, reverse=True):
        if term in lowered and term not in found:
            found.append(term)
    return found


def _extract_medications(text: str) -> list[str]:
    found = _find_terms(text, MEDICATION_TERMS)
    for match in re.findall(r"\b([A-Za-z]{4,}(?:\s\d+\s?mg)?)\b", text):
        token = match.lower()
        if "mg" in token or token in MEDICATION_TERMS:
            if token not in found:
                found.append(token)
    return found


def _extract_diagnoses(text: str) -> list[str]:
    diagnoses: list[str] = []
    for match in re.findall(
        r"(?:diagnosed with|diagnosis[:\s]+|assessment[:\s]+)([^.\n]+)",
        text,
        re.I,
    ):
        value = match.strip(" :-")
        if value and value.lower() not in diagnoses:
            diagnoses.append(value)
    assessment = SECTION_PATTERNS["assessment"].search(text)
    if assessment:
        line = assessment.group(1).strip().split("\n")[0]
        if line and line.lower() not in [d.lower() for d in diagnoses]:
            diagnoses.append(line)
    return diagnoses


def _extract_recommendations(text: str) -> list[str]:
    recommendations: list[str] = []
    plan = SECTION_PATTERNS["plan"].search(text)
    if plan:
        for line in plan.group(1).split("\n"):
            cleaned = re.sub(r"^[-*\d.]+\s*", "", line).strip()
            if cleaned:
                recommendations.append(cleaned)
    for match in re.findall(r"(?:advised|recommended|prescribed)\s+([^.\n]+)", text, re.I):
        value = match.strip()
        if value and value not in recommendations:
            recommendations.append(value)
    return recommendations


def extract_from_content(content: str, source_type: str) -> dict[str, list[str]]:
    subjective = SECTION_PATTERNS["subjective"].search(content)
    objective = SECTION_PATTERNS["objective"].search(content)
    combined = content
    if subjective:
        combined += "\n" + subjective.group(1)
    if objective:
        combined += "\n" + objective.group(1)

    return {
        "conditions": _find_terms(combined, CONDITION_TERMS),
        "symptoms": _find_terms(combined, SYMPTOM_TERMS),
        "medications": _extract_medications(content),
        "diagnoses": _extract_diagnoses(content),
        "recommendations": _extract_recommendations(content),
    }


def merge_profile(
    existing_summary: str,
    *,
    document_title: str,
    content: str,
    source_type: str,
    consultation_date: date | datetime | None = None,
) -> str:
    profile = parse_profile(existing_summary)
    extracted = extract_from_content(content, source_type)

    for key in ("conditions", "symptoms", "medications", "diagnoses", "recommendations"):
        bucket: list[str] = profile[key]
        for item in extracted[key]:
            if item.lower() not in [x.lower() for x in bucket]:
                bucket.append(item)

    if consultation_date is not None:
        if isinstance(consultation_date, datetime):
            date_value = consultation_date.date().isoformat()
        else:
            date_value = consultation_date.isoformat()
        profile["most_recent_consultation_date"] = date_value

    if not any(profile[k] for k in ("conditions", "symptoms", "medications", "diagnoses", "recommendations")):
        snippet = content.strip().replace("\n", " ")[:200]
        if snippet:
            profile["recommendations"].append(f"{document_title}: {snippet}")

    return json.dumps(profile, indent=2)
